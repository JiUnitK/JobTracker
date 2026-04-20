from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from jobtracker.models import NormalizedJobPosting, RawJobPosting
from jobtracker.storage.company_repository import CompanyRepository
from jobtracker.storage.orm import JobObservationORM, JobORM, SearchRunORM
from jobtracker.storage.repository_utils import to_utc_naive, utc_now


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
