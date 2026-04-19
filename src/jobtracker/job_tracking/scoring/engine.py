from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobtracker.config.models import AppConfig
from jobtracker.job_tracking.normalize import normalize_job_title
from jobtracker.storage.orm import CompanyORM, JobObservationORM, JobORM


def to_utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


def ratio_score(matches: int, total: int) -> float:
    if total <= 0:
        return 1.0
    return clamp_score(matches / total)


def weight_map(weights) -> dict[str, float]:
    return {
        "title_match": weights.title_match,
        "skill_match": weights.skill_match,
        "location_match": weights.location_match,
        "seniority_match": weights.seniority_match,
        "freshness": weights.freshness,
        "source_confidence": weights.source_confidence,
        "repeated_observations": weights.repeated_observations,
        "related_openings": weights.related_openings,
    }


def weighted_percentage(signals: dict[str, float], weights) -> int:
    mapped_weights = weight_map(weights)
    total_weight = sum(weight for weight in mapped_weights.values() if weight > 0)
    if total_weight <= 0:
        return 0
    total = sum(signals[name] * mapped_weights[name] for name in mapped_weights)
    return round((total / total_weight) * 100)


@dataclass(slots=True)
class JobScoreResult:
    fit_score: int
    hiring_score: int
    priority_score: int
    payload: dict[str, object]


class ScoringService:
    def __init__(self, session: Session, config: AppConfig) -> None:
        self.session = session
        self.config = config

    def score_all_jobs(self, *, now: datetime) -> list[JobORM]:
        jobs = list(self.session.scalars(select(JobORM).order_by(JobORM.id)))
        for job in jobs:
            result = self.score_job(job, now=now)
            job.fit_score = result.fit_score
            job.hiring_score = result.hiring_score
            job.priority_score = result.priority_score
            job.score_payload = result.payload
        self.session.flush()
        return jobs

    def score_job(self, job: JobORM, *, now: datetime) -> JobScoreResult:
        observations = list(job.observations)
        company_jobs = list(job.company.jobs) if job.company is not None else [job]
        signal_values = self._compute_signal_values(job, observations, company_jobs, now=now)

        fit_score = weighted_percentage(signal_values, self.config.scoring.fit_weights)
        hiring_score = weighted_percentage(signal_values, self.config.scoring.hiring_weights)
        priority_score = round(
            fit_score * self.config.scoring.priority_mix.get("fit_score", 0.65)
            + hiring_score * self.config.scoring.priority_mix.get("hiring_score", 0.35)
        )
        payload = self._build_payload(job, signal_values, fit_score, hiring_score, priority_score)
        return JobScoreResult(
            fit_score=fit_score,
            hiring_score=hiring_score,
            priority_score=priority_score,
            payload=payload,
        )

    def _compute_signal_values(
        self,
        job: JobORM,
        observations: list[JobObservationORM],
        company_jobs: list[JobORM],
        *,
        now: datetime,
    ) -> dict[str, float]:
        searchable_text = " ".join(
            filter(
                None,
                [
                    (job.title or "").lower(),
                    (job.description_snippet or "").lower(),
                    " ".join((ob.source or "").lower() for ob in observations),
                ],
            )
        )
        normalized_title = normalize_job_title(job.title or "")
        target_titles = [normalize_job_title(title) for title in self.config.profile.target_titles]
        title_match = self._title_match_score(normalized_title, target_titles)

        preferred_skills = [skill.lower() for skill in self.config.profile.preferred_skills]
        matched_skills = sum(1 for skill in preferred_skills if skill in searchable_text)
        skill_match = ratio_score(matched_skills, len(preferred_skills))

        location_match = self._location_match_score(job)
        seniority_match = self._seniority_match_score(job)
        freshness = self._freshness_score(job, observations, now=now)
        source_confidence = self._source_confidence_score(job)
        repeated_observations = self._repeated_observations_score(observations)
        related_openings = self._related_openings_score(job, company_jobs)

        return {
            "title_match": title_match,
            "skill_match": skill_match,
            "location_match": location_match,
            "seniority_match": seniority_match,
            "freshness": freshness,
            "source_confidence": source_confidence,
            "repeated_observations": repeated_observations,
            "related_openings": related_openings,
        }

    def _title_match_score(self, normalized_title: str, target_titles: list[str]) -> float:
        if not target_titles:
            return 1.0
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

    def _location_match_score(self, job: JobORM) -> float:
        preferred_locations = [location.lower() for location in self.config.profile.preferred_locations]
        preferred_workplaces = [workplace.lower() for workplace in self.config.profile.target_workplace_types]
        if not preferred_locations and not preferred_workplaces:
            return 1.0

        job_location = (job.location_text or "").lower()
        job_workplace = (job.workplace_type or "").lower()
        location_hit = any(location in job_location for location in preferred_locations) if preferred_locations else False
        workplace_hit = job_workplace in preferred_workplaces if preferred_workplaces else False
        if location_hit and workplace_hit:
            return 1.0
        if location_hit or workplace_hit:
            return 0.75
        if job_workplace == "remote" and any("remote" in location for location in preferred_locations):
            return 1.0
        return 0.0

    def _seniority_match_score(self, job: JobORM) -> float:
        desired_levels = [level.lower() for level in self.config.search_terms.seniority]
        if not desired_levels:
            return 1.0
        searchable = " ".join(filter(None, [(job.seniority or "").lower(), (job.title or "").lower()]))
        if any(level in searchable for level in desired_levels):
            return 1.0
        if not searchable.strip():
            return 0.5
        return 0.0

    def _freshness_score(
        self,
        job: JobORM,
        observations: list[JobObservationORM],
        *,
        now: datetime,
    ) -> float:
        reference = max(
            (
                to_utc_naive(ob.observed_posted_at) or to_utc_naive(ob.observed_at)
                for ob in observations
            ),
            default=to_utc_naive(job.last_seen_at),
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

    def _source_confidence_score(self, job: JobORM) -> float:
        url = (job.best_source_url or "").lower()
        if "greenhouse" in url:
            return 1.0
        if "lever.co" in url:
            return 0.95
        if "ashbyhq.com" in url:
            return 0.95
        if "linkedin.com" in url:
            return 0.6
        return 0.5

    def _repeated_observations_score(self, observations: list[JobObservationORM]) -> float:
        count = len(observations)
        if count >= 3:
            return 1.0
        if count == 2:
            return 0.7
        if count == 1:
            return 0.4
        return 0.0

    def _related_openings_score(self, job: JobORM, company_jobs: list[JobORM]) -> float:
        active_related = sum(
            1
            for company_job in company_jobs
            if company_job.current_status == "active" and company_job.id != job.id
        )
        if active_related >= 3:
            return 1.0
        if active_related == 2:
            return 0.8
        if active_related == 1:
            return 0.6
        return 0.3

    def _build_payload(
        self,
        job: JobORM,
        signal_values: dict[str, float],
        fit_score: int,
        hiring_score: int,
        priority_score: int,
    ) -> dict[str, object]:
        preferred_skills = [skill.lower() for skill in self.config.profile.preferred_skills]
        searchable_text = " ".join(
            filter(None, [(job.title or "").lower(), (job.description_snippet or "").lower()])
        )
        matched_skills = [skill for skill in preferred_skills if skill in searchable_text]
        fit_reasons: list[str] = []
        if signal_values["title_match"] >= 0.8:
            fit_reasons.append("title closely matches target roles")
        elif signal_values["title_match"] > 0:
            fit_reasons.append("title partially matches target roles")
        if matched_skills:
            fit_reasons.append(f"matched preferred skills: {', '.join(matched_skills[:3])}")
        if signal_values["location_match"] >= 0.75:
            fit_reasons.append("location/workplace fits profile preferences")
        if signal_values["seniority_match"] >= 1.0:
            fit_reasons.append("seniority aligns with desired levels")

        hiring_reasons: list[str] = []
        if signal_values["freshness"] >= 0.8:
            hiring_reasons.append("posting appears fresh")
        if signal_values["repeated_observations"] >= 0.7:
            hiring_reasons.append("role has been observed across multiple runs")
        if signal_values["related_openings"] >= 0.6:
            hiring_reasons.append("company has multiple active related openings")
        if signal_values["source_confidence"] >= 0.9:
            hiring_reasons.append("role comes from a high-confidence ATS source")

        return {
            "fit_score": fit_score,
            "fit_reasons": fit_reasons,
            "hiring_score": hiring_score,
            "hiring_reasons": hiring_reasons,
            "priority_score": priority_score,
            "signals": {name: round(value, 3) for name, value in signal_values.items()},
        }
