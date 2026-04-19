from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from jobtracker.storage.orm import CompanyORM, JobORM
from jobtracker.storage.repositories import CompanyActivityRepository, to_utc_naive


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class JobReportFilters:
    location: str | None = None
    remote_only: bool = False
    recent_days: int | None = None
    min_score: int | None = None
    status: str | None = None
    limit: int = 20
    sort_by: str = "priority"


def _sort_key(job: JobORM, sort_by: str) -> tuple:
    if sort_by == "fit":
        return (job.fit_score or 0, job.priority_score or 0, job.id)
    if sort_by == "hiring":
        return (job.hiring_score or 0, job.priority_score or 0, job.id)
    if sort_by == "recent":
        return (to_utc_naive(job.last_seen_at) or datetime.min, job.priority_score or 0, job.id)
    return (job.priority_score or 0, job.fit_score or 0, job.id)


class ReportingService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_jobs(self, filters: JobReportFilters) -> list[JobORM]:
        jobs = list(
            self.session.scalars(
                select(JobORM)
                .options(selectinload(JobORM.company))
                .join(CompanyORM)
                .order_by(JobORM.id)
            )
        )
        filtered = [job for job in jobs if self._job_matches(job, filters)]
        filtered.sort(key=lambda job: _sort_key(job, filters.sort_by), reverse=True)
        return filtered[: filters.limit]

    def list_companies(self, *, recent_days: int = 14, limit: int = 20) -> list[dict[str, object]]:
        recent_since = utc_now() - timedelta(days=recent_days)
        summaries = CompanyActivityRepository(self.session).summarize(recent_since=recent_since)
        summaries.sort(
            key=lambda item: (
                int(item["active_relevant_job_count"]),
                int(item["recent_relevant_job_count"]),
                item["display_name"],
            ),
            reverse=True,
        )
        return summaries[:limit]

    def export_jobs_csv(self, output_path: Path, filters: JobReportFilters) -> None:
        jobs = self.list_jobs(filters)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "company",
                    "title",
                    "location",
                    "workplace_type",
                    "status",
                    "fit_score",
                    "hiring_score",
                    "priority_score",
                    "best_source_url",
                ],
            )
            writer.writeheader()
            for job in jobs:
                writer.writerow(self._job_row(job))

    def export_jobs_markdown(self, output_path: Path, filters: JobReportFilters) -> None:
        jobs = self.list_jobs(filters)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# JobTracker Report", "", "| Company | Title | Location | Status | Priority |", "| --- | --- | --- | --- | --- |"]
        for job in jobs:
            company = job.company.display_name if job.company is not None else "Unknown"
            lines.append(
                f"| {company} | {job.title} | {job.location_text or '-'} | "
                f"{job.current_status} | {job.priority_score or 0} |"
            )
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _job_matches(self, job: JobORM, filters: JobReportFilters) -> bool:
        if filters.location and filters.location.lower() not in (job.location_text or "").lower():
            return False
        if filters.remote_only and (job.workplace_type or "").lower() != "remote":
            return False
        if filters.min_score is not None and (job.priority_score or 0) < filters.min_score:
            return False
        if filters.status and (job.current_status or "").lower() != filters.status.lower():
            return False
        if filters.recent_days is not None:
            cutoff = to_utc_naive(utc_now() - timedelta(days=filters.recent_days))
            last_seen = to_utc_naive(job.last_seen_at)
            if last_seen is None or cutoff is None or last_seen < cutoff:
                return False
        return True

    def _job_row(self, job: JobORM) -> dict[str, object]:
        company = job.company.display_name if job.company is not None else "Unknown"
        return {
            "company": company,
            "title": job.title,
            "location": job.location_text or "",
            "workplace_type": job.workplace_type,
            "status": job.current_status,
            "fit_score": job.fit_score or 0,
            "hiring_score": job.hiring_score or 0,
            "priority_score": job.priority_score or 0,
            "best_source_url": job.best_source_url or "",
        }
