from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from jobtracker.models import CompanyRecord, NormalizedCompanyDiscovery, RawCompanyDiscovery
from jobtracker.storage.company_repository import CompanyRepository
from jobtracker.storage.orm import (
    CompanyDiscoveryObservationORM,
    CompanyDiscoveryORM,
    CompanyResolutionORM,
)
from jobtracker.storage.repository_utils import to_utc_naive, utc_now


class CompanyDiscoveryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.companies = CompanyRepository(session)

    def upsert(
        self,
        discovery: NormalizedCompanyDiscovery,
        *,
        discovered_at: datetime | None = None,
    ) -> CompanyDiscoveryORM:
        discovered_at = to_utc_naive(discovered_at) or utc_now()
        existing = self.session.scalar(
            select(CompanyDiscoveryORM).where(
                CompanyDiscoveryORM.normalized_name == discovery.normalized_name
            )
        )
        if existing is None:
            existing = CompanyDiscoveryORM(
                normalized_name=discovery.normalized_name,
                display_name=discovery.display_name,
                company_url=str(discovery.company_url) if discovery.company_url else None,
                careers_url=str(discovery.careers_url) if discovery.careers_url else None,
                discovery_status=discovery.discovery_status,
                resolution_status=discovery.resolution_status,
                first_discovered_at=discovered_at,
                last_discovered_at=discovered_at,
            )
            self.session.add(existing)
        else:
            existing.display_name = discovery.display_name
            existing.company_url = (
                str(discovery.company_url) if discovery.company_url else existing.company_url
            )
            existing.careers_url = (
                str(discovery.careers_url) if discovery.careers_url else existing.careers_url
            )
            existing.discovery_status = discovery.discovery_status
            existing.resolution_status = discovery.resolution_status
            existing.last_discovered_at = discovered_at
        self.session.flush()
        return existing

    def list_all(self) -> list[CompanyDiscoveryORM]:
        return list(
            self.session.scalars(
                select(CompanyDiscoveryORM).order_by(CompanyDiscoveryORM.display_name)
            )
        )

    def get_by_selector(self, selector: str) -> CompanyDiscoveryORM | None:
        cleaned = selector.strip()
        if not cleaned:
            return None
        if cleaned.isdigit():
            return self.session.get(CompanyDiscoveryORM, int(cleaned))
        lowered = cleaned.lower()
        return self.session.scalar(
            select(CompanyDiscoveryORM).where(
                or_(
                    CompanyDiscoveryORM.normalized_name == lowered,
                    func.lower(CompanyDiscoveryORM.display_name) == lowered,
                )
            )
        )

    def mark_ignored(
        self,
        selector: str,
        *,
        ignored_at: datetime | None = None,
    ) -> CompanyDiscoveryORM:
        discovery = self.get_by_selector(selector)
        if discovery is None:
            raise ValueError(f"Discovered company '{selector}' was not found")
        discovery.discovery_status = "ignored"
        discovery.ignored_at = to_utc_naive(ignored_at) or utc_now()
        self.session.flush()
        return discovery

    def promote_to_tracked(
        self,
        selector: str,
        *,
        selected_resolution: CompanyResolutionORM,
        promoted_at: datetime | None = None,
    ) -> CompanyDiscoveryORM:
        discovery = self.get_by_selector(selector)
        if discovery is None:
            raise ValueError(f"Discovered company '{selector}' was not found")
        company = self.companies.upsert(
            CompanyRecord(
                normalized_name=discovery.normalized_name,
                display_name=discovery.display_name,
                careers_url=selected_resolution.url,
            )
        )
        discovery.company_id = company.id
        discovery.discovery_status = "tracked"
        discovery.promoted_at = to_utc_naive(promoted_at) or utc_now()
        discovery.ignored_at = None
        self.session.flush()
        return discovery

    def list_promoted_resolutions(self) -> list[tuple[CompanyDiscoveryORM, CompanyResolutionORM]]:
        rows = self.session.execute(
            select(CompanyDiscoveryORM, CompanyResolutionORM)
            .join(
                CompanyResolutionORM,
                CompanyResolutionORM.company_discovery_id == CompanyDiscoveryORM.id,
            )
            .where(
                CompanyDiscoveryORM.discovery_status == "tracked",
                CompanyResolutionORM.is_selected.is_(True),
            )
            .order_by(CompanyDiscoveryORM.display_name)
        ).all()
        return [(row[0], row[1]) for row in rows]


class CompanyDiscoveryObservationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        company_discovery_id: int,
        search_run_id: int | None,
        raw_discovery: RawCompanyDiscovery,
        observed_at: datetime | None = None,
    ) -> CompanyDiscoveryObservationORM:
        observation = CompanyDiscoveryObservationORM(
            company_discovery_id=company_discovery_id,
            search_run_id=search_run_id,
            source_type=raw_discovery.source_type,
            source_name=raw_discovery.source_name,
            source_url=str(raw_discovery.source_url),
            company_url=str(raw_discovery.company_url) if raw_discovery.company_url else None,
            careers_url=str(raw_discovery.careers_url) if raw_discovery.careers_url else None,
            job_url=str(raw_discovery.job_url) if raw_discovery.job_url else None,
            job_title=raw_discovery.job_title,
            location_text=raw_discovery.location_text,
            workplace_type=raw_discovery.workplace_type,
            evidence_kind=raw_discovery.evidence_kind,
            observed_at=to_utc_naive(observed_at) or utc_now(),
            raw_payload=raw_discovery.raw_payload,
        )
        self.session.add(observation)
        self.session.flush()
        return observation


class CompanyResolutionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_candidate(
        self,
        *,
        company_discovery_id: int,
        resolution_type: str,
        platform: str,
        identifier: str,
        url: str,
        confidence: float,
        observed_at: datetime | None = None,
        is_selected: bool = False,
    ) -> CompanyResolutionORM:
        existing = self.session.scalar(
            select(CompanyResolutionORM).where(
                CompanyResolutionORM.company_discovery_id == company_discovery_id,
                CompanyResolutionORM.url == url,
                CompanyResolutionORM.resolution_type == resolution_type,
            )
        )
        if existing is None:
            existing = CompanyResolutionORM(
                company_discovery_id=company_discovery_id,
                resolution_type=resolution_type,
                platform=platform,
                identifier=identifier,
                url=url,
                confidence=confidence,
                is_selected=is_selected,
                observed_at=to_utc_naive(observed_at) or utc_now(),
            )
            self.session.add(existing)
        else:
            existing.platform = platform
            existing.identifier = identifier
            existing.confidence = confidence
            existing.is_selected = is_selected
            existing.observed_at = to_utc_naive(observed_at) or utc_now()

        self.session.flush()
        self.refresh_resolution_state(company_discovery_id)
        self.session.flush()
        return existing

    def refresh_resolution_state(self, company_discovery_id: int) -> None:
        discovery = self.session.get(CompanyDiscoveryORM, company_discovery_id)
        if discovery is None:
            return

        resolutions = list(
            self.session.scalars(
                select(CompanyResolutionORM)
                .where(CompanyResolutionORM.company_discovery_id == company_discovery_id)
                .order_by(CompanyResolutionORM.id)
            )
        )
        if not resolutions:
            discovery.resolution_status = "unresolved"
            self.session.flush()
            return

        top_confidence = max(float(resolution.confidence or 0) for resolution in resolutions)
        top_resolutions = [
            resolution
            for resolution in resolutions
            if float(resolution.confidence or 0) == top_confidence
        ]

        selected_id = None
        if len(top_resolutions) == 1:
            selected_id = top_resolutions[0].id
            platform = top_resolutions[0].platform
            discovery.resolution_status = "resolved" if platform in {"greenhouse", "lever", "ashby"} else "partial"
        else:
            discovery.resolution_status = "conflicted"

        for resolution in resolutions:
            resolution.is_selected = resolution.id == selected_id
        self.session.flush()

    def list_for_discovery(self, company_discovery_id: int) -> list[CompanyResolutionORM]:
        return list(
            self.session.scalars(
                select(CompanyResolutionORM)
                .where(CompanyResolutionORM.company_discovery_id == company_discovery_id)
                .order_by(
                    CompanyResolutionORM.is_selected.desc(),
                    CompanyResolutionORM.confidence.desc(),
                    CompanyResolutionORM.id.asc(),
                )
            )
        )

    def get_selected_for_discovery(self, company_discovery_id: int) -> CompanyResolutionORM | None:
        return self.session.scalar(
            select(CompanyResolutionORM).where(
                CompanyResolutionORM.company_discovery_id == company_discovery_id,
                CompanyResolutionORM.is_selected.is_(True),
            )
        )

    def select_resolution(
        self,
        company_discovery_id: int,
        *,
        resolution_url: str | None = None,
    ) -> CompanyResolutionORM:
        resolutions = list(
            self.session.scalars(
                select(CompanyResolutionORM)
                .where(CompanyResolutionORM.company_discovery_id == company_discovery_id)
                .order_by(CompanyResolutionORM.id)
            )
        )
        if not resolutions:
            raise ValueError("No resolution candidates are available for this company")

        selected: CompanyResolutionORM | None = None
        if resolution_url:
            selected = next((item for item in resolutions if item.url == resolution_url), None)
            if selected is None:
                raise ValueError(f"No resolution candidate matched '{resolution_url}'")
        elif len(resolutions) == 1:
            selected = resolutions[0]
        else:
            ats_resolutions = [item for item in resolutions if item.platform in {"greenhouse", "lever", "ashby"}]
            if len(ats_resolutions) == 1:
                selected = ats_resolutions[0]
            else:
                raise ValueError(
                    "Multiple resolution candidates exist; provide --resolution-url to choose one"
                )

        for resolution in resolutions:
            resolution.is_selected = resolution.id == selected.id

        discovery = self.session.get(CompanyDiscoveryORM, company_discovery_id)
        if discovery is not None:
            if selected.platform in {"greenhouse", "lever", "ashby"}:
                discovery.resolution_status = "resolved"
            else:
                discovery.resolution_status = "partial"
        self.session.flush()
        return selected
