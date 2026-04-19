from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobtracker.models import CompanyRecord, NormalizedJobPosting, RawJobPosting
from jobtracker.storage.orm import CompanyORM, JobObservationORM, JobORM, SearchRunORM, SourceORM


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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

    def start(self, trigger_type: str = "manual") -> SearchRunORM:
        search_run = SearchRunORM(trigger_type=trigger_type, status="running")
        self.session.add(search_run)
        self.session.flush()
        return search_run

    def complete(self, search_run: SearchRunORM, *, status: str, summary: dict) -> SearchRunORM:
        search_run.status = status
        search_run.summary_json = summary
        search_run.completed_at = utc_now()
        self.session.flush()
        return search_run


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.companies = CompanyRepository(session)

    def upsert(self, job: NormalizedJobPosting, seen_at: datetime | None = None) -> JobORM:
        seen_at = seen_at or utc_now()
        company = self.companies.upsert(job.company)
        existing = self.session.scalar(
            select(JobORM).where(JobORM.canonical_key == job.canonical_key)
        )
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
            existing.best_source_url = str(job.source_url)
        self.session.flush()
        return existing

    def list_all(self) -> list[JobORM]:
        return list(self.session.scalars(select(JobORM).order_by(JobORM.id)))


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
