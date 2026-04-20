from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobtracker.models import CompanyRecord
from jobtracker.storage.orm import CompanyORM, JobORM
from jobtracker.storage.repository_utils import to_utc_naive


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
