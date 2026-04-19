from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from jobtracker.models import CompanyRecord, NormalizedJobPosting, RawJobPosting
from jobtracker.storage.orm import CompanyORM, JobObservationORM, JobORM, SearchRunORM, SourceORM


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
