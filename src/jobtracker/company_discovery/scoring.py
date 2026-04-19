from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from jobtracker.config.models import AppConfig
from jobtracker.job_tracking.normalize import normalize_job_title
from jobtracker.storage.orm import (
    CompanyDiscoveryObservationORM,
    CompanyDiscoveryORM,
    CompanyResolutionORM,
)


def to_utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(slots=True)
class CompanyDiscoveryScoreResult:
    fit_score: int
    hiring_score: int
    discovery_score: int
    payload: dict[str, object]


class CompanyDiscoveryScoringService:
    def __init__(self, session: Session, config: AppConfig) -> None:
        self.session = session
        self.config = config

    def score_all_discoveries(self, *, now: datetime) -> list[CompanyDiscoveryORM]:
        discoveries = list(
            self.session.scalars(
                select(CompanyDiscoveryORM)
                .options(
                    selectinload(CompanyDiscoveryORM.observations),
                    selectinload(CompanyDiscoveryORM.resolutions),
                )
                .order_by(CompanyDiscoveryORM.id)
            )
        )
        for discovery in discoveries:
            result = self.score_discovery(discovery, now=now)
            discovery.fit_score = result.fit_score
            discovery.hiring_score = result.hiring_score
            discovery.discovery_score = result.discovery_score
            discovery.score_payload = result.payload
        self.session.flush()
        return discoveries

    def score_discovery(
        self,
        discovery: CompanyDiscoveryORM,
        *,
        now: datetime,
    ) -> CompanyDiscoveryScoreResult:
        observations = list(discovery.observations)
        resolutions = list(discovery.resolutions)
        signal_values = self._compute_signal_values(discovery, observations, resolutions, now=now)

        fit_weights = self.config.company_discovery.scoring.fit_weights
        hiring_weights = self.config.company_discovery.scoring.hiring_weights
        fit_score = self._weighted_percentage(signal_values, fit_weights)
        hiring_score = self._weighted_percentage(signal_values, hiring_weights)
        priority_mix = self.config.company_discovery.scoring.priority_mix
        discovery_score = round(
            fit_score * priority_mix.get("fit_score", 0.5)
            + hiring_score * priority_mix.get("hiring_score", 0.5)
        )
        payload = self._build_payload(discovery, signal_values, fit_score, hiring_score, discovery_score)
        return CompanyDiscoveryScoreResult(
            fit_score=fit_score,
            hiring_score=hiring_score,
            discovery_score=discovery_score,
            payload=payload,
        )

    def _weighted_percentage(self, signals: dict[str, float], weights) -> int:
        weight_values = {
            "title_match": weights.title_match,
            "skill_match": weights.skill_match,
            "location_match": weights.location_match,
            "repeated_appearance": weights.repeated_appearance,
            "ats_confidence": weights.ats_confidence,
            "fresh_evidence": weights.fresh_evidence,
        }
        total_weight = sum(weight for weight in weight_values.values() if weight > 0)
        if total_weight <= 0:
            return 0
        total = sum(signals[name] * weight_values[name] for name in weight_values)
        return round((total / total_weight) * 100)

    def _compute_signal_values(
        self,
        discovery: CompanyDiscoveryORM,
        observations: list[CompanyDiscoveryObservationORM],
        resolutions: list[CompanyResolutionORM],
        *,
        now: datetime,
    ) -> dict[str, float]:
        profile = self.config.profile
        target_titles = [normalize_job_title(title) for title in profile.target_titles]
        observation_titles = [
            normalize_job_title(ob.job_title or "")
            for ob in observations
            if (ob.job_title or "").strip()
        ]
        title_match = 0.0
        if not target_titles:
            title_match = 1.0
        elif observation_titles:
            title_match = max(self._title_match_score(title, target_titles) for title in observation_titles)

        searchable_text = " ".join(
            filter(
                None,
                [
                    discovery.display_name.lower(),
                    " ".join((ob.job_title or "").lower() for ob in observations),
                    " ".join(
                        str(item).lower()
                        for ob in observations
                        for item in (ob.raw_payload.get("tags", []) if isinstance(ob.raw_payload, dict) else [])
                    ),
                    " ".join(
                        str(item).lower()
                        for ob in observations
                        for item in (ob.raw_payload.get("role_focus", []) if isinstance(ob.raw_payload, dict) else [])
                    ),
                    " ".join(
                        str((ob.raw_payload or {}).get("summary", "")).lower()
                        for ob in observations
                        if isinstance(ob.raw_payload, dict)
                    ),
                ],
            )
        )
        preferred_skills = [skill.lower() for skill in profile.preferred_skills]
        matched_skills = sum(1 for skill in preferred_skills if skill in searchable_text)
        skill_match = 1.0 if not preferred_skills else clamp_score(matched_skills / len(preferred_skills))

        preferred_locations = [location.lower() for location in profile.preferred_locations]
        preferred_workplaces = [workplace.lower() for workplace in profile.target_workplace_types]
        location_match = self._location_match_score(
            observations,
            preferred_locations=preferred_locations,
            preferred_workplaces=preferred_workplaces,
        )
        repeated_appearance = self._repeated_appearance_score(observations)
        ats_confidence = self._ats_confidence_score(discovery, resolutions)
        fresh_evidence = self._fresh_evidence_score(discovery, observations, now=now)

        return {
            "title_match": title_match,
            "skill_match": skill_match,
            "location_match": location_match,
            "repeated_appearance": repeated_appearance,
            "ats_confidence": ats_confidence,
            "fresh_evidence": fresh_evidence,
        }

    def _title_match_score(self, normalized_title: str, target_titles: list[str]) -> float:
        if normalized_title in target_titles:
            return 1.0
        normalized_tokens = set(normalized_title.split())
        best_overlap = 0.0
        for title in target_titles:
            target_tokens = set(title.split())
            if not target_tokens:
                continue
            overlap = len(normalized_tokens & target_tokens) / len(target_tokens)
            best_overlap = max(best_overlap, overlap)
        return clamp_score(best_overlap)

    def _location_match_score(
        self,
        observations: list[CompanyDiscoveryObservationORM],
        *,
        preferred_locations: list[str],
        preferred_workplaces: list[str],
    ) -> float:
        if not preferred_locations and not preferred_workplaces:
            return 1.0
        best = 0.0
        for observation in observations:
            location_text = (observation.location_text or "").lower()
            workplace_type = (observation.workplace_type or "").lower()
            location_hit = any(location in location_text for location in preferred_locations) if preferred_locations else False
            workplace_hit = workplace_type in preferred_workplaces if preferred_workplaces else False
            score = 0.0
            if location_hit and workplace_hit:
                score = 1.0
            elif location_hit or workplace_hit:
                score = 0.75
            elif workplace_type == "remote" and any("remote" in location for location in preferred_locations):
                score = 1.0
            best = max(best, score)
        return best

    def _repeated_appearance_score(self, observations: list[CompanyDiscoveryObservationORM]) -> float:
        count = len(observations)
        if count >= 3:
            return 1.0
        if count == 2:
            return 0.75
        if count == 1:
            return 0.4
        return 0.0

    def _ats_confidence_score(
        self,
        discovery: CompanyDiscoveryORM,
        resolutions: list[CompanyResolutionORM],
    ) -> float:
        selected = next((resolution for resolution in resolutions if resolution.is_selected), None)
        if selected is None and resolutions:
            selected = max(resolutions, key=lambda resolution: float(resolution.confidence or 0))
        if selected is None:
            return 0.2
        if selected.platform in {"greenhouse", "lever", "ashby"}:
            return 1.0
        if discovery.resolution_status == "partial":
            return 0.6
        if discovery.resolution_status == "conflicted":
            return 0.4
        return 0.5

    def _fresh_evidence_score(
        self,
        discovery: CompanyDiscoveryORM,
        observations: list[CompanyDiscoveryObservationORM],
        *,
        now: datetime,
    ) -> float:
        reference = max(
            (to_utc_naive(ob.observed_at) for ob in observations if to_utc_naive(ob.observed_at) is not None),
            default=to_utc_naive(discovery.last_discovered_at),
        )
        if reference is None:
            return 0.0
        age_days = max((to_utc_naive(now) - reference).days, 0)
        if age_days <= 7:
            return 1.0
        if age_days <= 14:
            return 0.8
        if age_days <= 30:
            return 0.5
        return 0.2

    def _build_payload(
        self,
        discovery: CompanyDiscoveryORM,
        signal_values: dict[str, float],
        fit_score: int,
        hiring_score: int,
        discovery_score: int,
    ) -> dict[str, object]:
        fit_reasons: list[str] = []
        if signal_values["title_match"] >= 0.8:
            fit_reasons.append("observed roles closely match target titles")
        elif signal_values["title_match"] > 0:
            fit_reasons.append("observed roles partially match target titles")
        if signal_values["skill_match"] >= 0.5:
            fit_reasons.append("discovery evidence matches preferred skills")
        if signal_values["location_match"] >= 0.75:
            fit_reasons.append("location/workplace evidence fits profile preferences")

        hiring_reasons: list[str] = []
        if signal_values["repeated_appearance"] >= 0.75:
            hiring_reasons.append("company appeared across multiple discovery signals")
        if signal_values["ats_confidence"] >= 1.0:
            hiring_reasons.append("company resolves to a high-confidence ATS")
        elif signal_values["ats_confidence"] >= 0.6:
            hiring_reasons.append("company has a plausible careers surface")
        if signal_values["fresh_evidence"] >= 0.8:
            hiring_reasons.append("discovery evidence is recent")

        return {
            "fit_score": fit_score,
            "fit_reasons": fit_reasons,
            "hiring_score": hiring_score,
            "hiring_reasons": hiring_reasons,
            "discovery_score": discovery_score,
            "signals": {name: round(value, 3) for name, value in signal_values.items()},
            "resolution_status": discovery.resolution_status,
            "primary_location": next(
                (ob.location_text for ob in discovery.observations if ob.location_text),
                None,
            ),
            "primary_workplace_type": next(
                (ob.workplace_type for ob in discovery.observations if ob.workplace_type),
                None,
            ),
            "source_names": sorted(
                {
                    ob.source_name
                    for ob in discovery.observations
                    if (ob.source_name or "").strip()
                }
            ),
            "observation_count": len(discovery.observations),
            "best_resolution": self._best_resolution_payload(discovery.resolutions),
            "resolution_candidate_count": len(discovery.resolutions),
        }

    def _best_resolution_payload(
        self,
        resolutions: list[CompanyResolutionORM],
    ) -> dict[str, object] | None:
        if not resolutions:
            return None
        selected = next((resolution for resolution in resolutions if resolution.is_selected), None)
        best = selected or max(
            resolutions,
            key=lambda resolution: (
                1 if resolution.platform in {"greenhouse", "lever", "ashby"} else 0,
                float(resolution.confidence or 0),
            ),
        )
        return {
            "platform": best.platform,
            "identifier": best.identifier,
            "url": best.url,
            "confidence": float(best.confidence or 0),
            "selected": bool(best.is_selected),
        }
