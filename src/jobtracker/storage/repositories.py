from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from jobtracker.models import (
    CompanyRecord,
    NormalizedCompanyDiscovery,
    NormalizedJobPosting,
    RawCompanyDiscovery,
    RawJobPosting,
)
from jobtracker.storage.orm import (
    CompanyDiscoveryObservationORM,
    CompanyDiscoveryORM,
    CompanyORM,
    CompanyResolutionORM,
    JobObservationORM,
    JobORM,
    SearchRunORM,
    SourceORM,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class SourceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(
        self,
        *,
        name: str,
        reliability_tier: str,
        enabled: bool = True,
        base_url: str | None = None,
    ) -> SourceORM:
        source = self.session.scalar(select(SourceORM).where(SourceORM.name == name))
        if source is None:
            source = SourceORM(
                name=name,
                reliability_tier=reliability_tier,
                enabled=enabled,
                base_url=base_url,
            )
            self.session.add(source)
        else:
            source.reliability_tier = reliability_tier
            source.enabled = enabled
            source.base_url = base_url
        self.session.flush()
        return source

    def mark_success(self, name: str) -> SourceORM:
        source = self.session.scalar(select(SourceORM).where(SourceORM.name == name))
        if source is None:
            raise ValueError(f"Source '{name}' is not registered")
        source.last_success_at = utc_now()
        self.session.flush()
        return source

    def mark_error(self, name: str) -> SourceORM:
        source = self.session.scalar(select(SourceORM).where(SourceORM.name == name))
        if source is None:
            raise ValueError(f"Source '{name}' is not registered")
        source.last_error_at = utc_now()
        self.session.flush()
        return source

    def list_all(self) -> list[SourceORM]:
        return list(self.session.scalars(select(SourceORM).order_by(SourceORM.name)))


class CompanyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, company: CompanyRecord) -> CompanyORM:
        existing = self.session.scalar(
            select(CompanyORM).where(CompanyORM.normalized_name == company.normalized_name)
        )
        if existing is None:
            existing = CompanyORM(
                normalized_name=company.normalized_name,
                display_name=company.display_name,
                careers_url=str(company.careers_url) if company.careers_url else None,
                headquarters=company.headquarters,
                company_type=company.company_type,
                notes=company.notes,
            )
            self.session.add(existing)
        else:
            existing.display_name = company.display_name
            existing.careers_url = (
                str(company.careers_url) if company.careers_url else existing.careers_url
            )
            existing.headquarters = company.headquarters
            existing.company_type = company.company_type
            existing.notes = company.notes
        self.session.flush()
        return existing


class SearchRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def start(
        self,
        trigger_type: str = "manual",
        *,
        started_at: datetime | None = None,
    ) -> SearchRunORM:
        search_run = SearchRunORM(
            trigger_type=trigger_type,
            status="running",
            started_at=started_at or utc_now(),
        )
        self.session.add(search_run)
        self.session.flush()
        return search_run

    def complete(
        self,
        search_run: SearchRunORM,
        *,
        status: str,
        summary: dict,
        completed_at: datetime | None = None,
    ) -> SearchRunORM:
        search_run.status = status
        search_run.summary_json = summary
        search_run.completed_at = completed_at or utc_now()
        self.session.flush()
        return search_run


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.companies = CompanyRepository(session)

    def upsert(
        self,
        job: NormalizedJobPosting,
        *,
        seen_at: datetime | None = None,
        source: str | None = None,
        source_job_id: str | None = None,
    ) -> JobORM:
        seen_at = seen_at or utc_now()
        company = self.companies.upsert(job.company)
        existing = None
        if source and source_job_id:
            existing = self.find_by_source_job(source, source_job_id)
        if existing is None:
            existing = self.find_by_canonical_key(job.canonical_key)
        if existing is None:
            existing = JobORM(
                company_id=company.id,
                canonical_key=job.canonical_key,
                title=job.title,
                location_text=job.location_text,
                workplace_type=job.workplace_type,
                employment_type=job.employment_type,
                seniority=job.seniority,
                description_snippet=job.description_snippet,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                salary_currency=job.salary_currency,
                first_seen_at=seen_at,
                last_seen_at=seen_at,
                current_status=job.status,
                best_source_url=str(job.source_url),
            )
            self.session.add(existing)
        else:
            existing.company_id = company.id
            existing.title = job.title
            existing.location_text = job.location_text
            existing.workplace_type = job.workplace_type
            existing.employment_type = job.employment_type
            existing.seniority = job.seniority
            existing.description_snippet = job.description_snippet
            existing.salary_min = job.salary_min
            existing.salary_max = job.salary_max
            existing.salary_currency = job.salary_currency
            existing.last_seen_at = seen_at
            existing.current_status = job.status
            existing.best_source_url = self._preferred_source_url(
                existing.best_source_url,
                str(job.source_url),
                existing_source=self._infer_source_from_url(existing.best_source_url),
                incoming_source=job.source,
            )
        self.session.flush()
        return existing

    def list_all(self) -> list[JobORM]:
        return list(self.session.scalars(select(JobORM).order_by(JobORM.id)))

    def infer_statuses(
        self,
        *,
        current_run: SearchRunORM,
        stale_after_runs: int,
        closed_after_runs: int,
    ) -> dict[str, int]:
        status_counts = {"active": 0, "stale": 0, "closed": 0, "unknown": 0}
        jobs = self.list_all()
        current_started_at = to_utc_naive(current_run.started_at)
        for job in jobs:
            last_seen_at = to_utc_naive(job.last_seen_at)
            if last_seen_at and current_started_at and last_seen_at >= current_started_at:
                job.current_status = "active"
            else:
                missed_runs = self._count_missed_runs(job, current_run)
                if missed_runs >= closed_after_runs:
                    job.current_status = "closed"
                elif missed_runs >= stale_after_runs:
                    job.current_status = "stale"
                elif missed_runs > 0:
                    job.current_status = "active"
                else:
                    job.current_status = "unknown"
            status_counts[job.current_status] += 1
        self.session.flush()
        return status_counts

    def _count_missed_runs(self, job: JobORM, current_run: SearchRunORM) -> int:
        job_last_seen_at = to_utc_naive(job.last_seen_at)
        current_started_at = to_utc_naive(current_run.started_at)
        statement = select(func.count(SearchRunORM.id)).where(
            and_(
                SearchRunORM.status.in_(["success", "partial_success"]),
                SearchRunORM.started_at > job_last_seen_at,
                SearchRunORM.started_at <= current_started_at,
            )
        )
        return int(self.session.scalar(statement) or 0)

    def find_by_source_job(self, source: str, source_job_id: str) -> JobORM | None:
        statement = (
            select(JobORM)
            .join(JobObservationORM, JobObservationORM.job_id == JobORM.id)
            .where(
                and_(
                    JobObservationORM.source == source,
                    JobObservationORM.source_job_id == source_job_id,
                )
            )
            .order_by(JobObservationORM.id.desc())
        )
        return self.session.scalar(statement)

    def find_by_canonical_key(self, canonical_key: str) -> JobORM | None:
        return self.session.scalar(select(JobORM).where(JobORM.canonical_key == canonical_key))

    def _preferred_source_url(
        self,
        existing_url: str | None,
        incoming_url: str,
        *,
        existing_source: str | None,
        incoming_source: str,
    ) -> str:
        if not existing_url:
            return incoming_url
        existing_rank = self._source_rank(existing_source)
        incoming_rank = self._source_rank(incoming_source)
        if incoming_rank < existing_rank:
            return incoming_url
        if incoming_rank == existing_rank and len(incoming_url) < len(existing_url):
            return incoming_url
        return existing_url

    def _source_rank(self, source: str | None) -> int:
        order = {
            "greenhouse": 1,
            "lever": 2,
            "ashby": 3,
            "linkedin": 10,
        }
        return order.get(source or "", 50)

    def _infer_source_from_url(self, url: str | None) -> str | None:
        if not url:
            return None
        lowered = url.lower()
        if "greenhouse" in lowered:
            return "greenhouse"
        if "lever.co" in lowered:
            return "lever"
        if "ashbyhq.com" in lowered:
            return "ashby"
        if "linkedin.com" in lowered:
            return "linkedin"
        return None


class CompanyActivityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def summarize(self, *, recent_since: datetime) -> list[dict[str, object]]:
        recent_since = to_utc_naive(recent_since) or recent_since
        statement = (
            select(CompanyORM)
            .outerjoin(JobORM, JobORM.company_id == CompanyORM.id)
            .order_by(CompanyORM.display_name)
        )
        companies = list(self.session.scalars(statement).unique())
        summaries: list[dict[str, object]] = []
        for company in companies:
            jobs = company.jobs
            summaries.append(
                {
                    "company_id": company.id,
                    "display_name": company.display_name,
                    "normalized_name": company.normalized_name,
                    "active_relevant_job_count": sum(
                        1 for job in jobs if job.current_status == "active"
                    ),
                    "recent_relevant_job_count": sum(
                        1
                        for job in jobs
                        if to_utc_naive(job.last_seen_at) is not None
                        and to_utc_naive(job.last_seen_at) >= recent_since
                    ),
                    "last_relevant_opening_seen_at": max(
                        (
                            to_utc_naive(job.last_seen_at)
                            for job in jobs
                            if to_utc_naive(job.last_seen_at) is not None
                        ),
                        default=None,
                    ),
                }
            )
        return summaries


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


class JobObservationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        job_id: int,
        search_run_id: int,
        raw_job: RawJobPosting,
        parse_status: str = "parsed",
        observed_at: datetime | None = None,
    ) -> JobObservationORM:
        observation = JobObservationORM(
            job_id=job_id,
            search_run_id=search_run_id,
            source=raw_job.source,
            source_job_id=raw_job.source_job_id,
            source_url=str(raw_job.source_url),
            observed_posted_at=raw_job.posted_at,
            observed_at=observed_at or utc_now(),
            parse_status=parse_status,
            raw_payload=raw_job.raw_payload,
        )
        self.session.add(observation)
        self.session.flush()
        return observation
