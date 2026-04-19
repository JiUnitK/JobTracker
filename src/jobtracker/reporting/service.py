from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from jobtracker.storage.orm import CompanyDiscoveryORM, CompanyORM, JobORM
from jobtracker.storage.repositories import CompanyActivityRepository, to_utc_naive


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class JobReportFilters:
    company: str | None = None
    location: str | None = None
    remote_only: bool = False
    recent_days: int | None = None
    min_score: int | None = None
    status: str | None = None
    limit: int = 20
    sort_by: str = "priority"


@dataclass(slots=True)
class CompanyDiscoveryReportFilters:
    location: str | None = None
    remote_only: bool = False
    recent_days: int | None = None
    min_score: int | None = None
    discovery_status: str | None = None
    resolution_status: str | None = None
    limit: int = 20
    sort_by: str = "discovery"


def _sort_key(job: JobORM, sort_by: str) -> tuple:
    if sort_by == "fit":
        return (job.fit_score or 0, job.priority_score or 0, job.id)
    if sort_by == "hiring":
        return (job.hiring_score or 0, job.priority_score or 0, job.id)
    if sort_by == "recent":
        return (to_utc_naive(job.last_seen_at) or datetime.min, job.priority_score or 0, job.id)
    return (job.priority_score or 0, job.fit_score or 0, job.id)


def _discovery_sort_key(discovery: CompanyDiscoveryORM, sort_by: str) -> tuple:
    if sort_by == "actionable":
        return (
            _discovery_action_rank(discovery),
            discovery.discovery_score or 0,
            discovery.fit_score or 0,
            to_utc_naive(discovery.last_discovered_at) or datetime.min,
            discovery.id,
        )
    if sort_by == "fit":
        return (discovery.fit_score or 0, discovery.discovery_score or 0, discovery.id)
    if sort_by == "hiring":
        return (discovery.hiring_score or 0, discovery.discovery_score or 0, discovery.id)
    if sort_by == "recent":
        return (
            to_utc_naive(discovery.last_discovered_at) or datetime.min,
            discovery.discovery_score or 0,
            discovery.id,
        )
    return (discovery.discovery_score or 0, discovery.fit_score or 0, discovery.id)


def describe_discovery_action(discovery: CompanyDiscoveryORM) -> str:
    status = (discovery.discovery_status or "candidate").lower()
    resolution = (discovery.resolution_status or "unresolved").lower()
    if status in {"ignored", "archived"}:
        return "ignored"
    if status == "tracked":
        return "review_jobs"
    if resolution == "resolved":
        return "promote"
    if resolution == "conflicted":
        return "resolve"
    if resolution == "partial":
        return "review_resolution"
    return "watch"


def _discovery_action_rank(discovery: CompanyDiscoveryORM) -> int:
    action = describe_discovery_action(discovery)
    return {
        "promote": 5,
        "resolve": 4,
        "review_resolution": 3,
        "review_jobs": 2,
        "watch": 1,
        "ignored": 0,
    }.get(action, 0)


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

    def list_discovered_companies(
        self,
        filters: CompanyDiscoveryReportFilters,
    ) -> list[CompanyDiscoveryORM]:
        discoveries = list(
            self.session.scalars(select(CompanyDiscoveryORM).order_by(CompanyDiscoveryORM.id))
        )
        filtered = [item for item in discoveries if self._discovery_matches(item, filters)]
        filtered.sort(key=lambda item: _discovery_sort_key(item, filters.sort_by), reverse=True)
        return filtered[: filters.limit]

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
        company_name = (
            job.company.display_name.lower()
            if job.company is not None and job.company.display_name
            else ""
        )
        if filters.company and filters.company.lower() not in company_name:
            return False
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

    def summarize_discovery_inbox(self) -> dict[str, int]:
        discoveries = list(self.session.scalars(select(CompanyDiscoveryORM).order_by(CompanyDiscoveryORM.id)))
        summary = {
            "candidate": 0,
            "watch": 0,
            "tracked": 0,
            "ignored": 0,
            "archived": 0,
            "resolved_actionable": 0,
            "ready_to_promote": 0,
            "needs_resolution": 0,
            "ready_for_job_review": 0,
        }
        for discovery in discoveries:
            status = (discovery.discovery_status or "candidate").lower()
            if status in summary:
                summary[status] += 1
            if status in {"candidate", "watch"} and (discovery.resolution_status or "") in {"resolved", "partial"}:
                summary["resolved_actionable"] += 1
            action = describe_discovery_action(discovery)
            if action == "promote":
                summary["ready_to_promote"] += 1
            elif action in {"resolve", "review_resolution"}:
                summary["needs_resolution"] += 1
            elif action == "review_jobs":
                summary["ready_for_job_review"] += 1
        return summary

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

    def _discovery_matches(
        self,
        discovery: CompanyDiscoveryORM,
        filters: CompanyDiscoveryReportFilters,
    ) -> bool:
        payload = discovery.score_payload if isinstance(discovery.score_payload, dict) else {}
        location_text = " ".join(
            str(item)
            for item in [
                payload.get("primary_location"),
                payload.get("primary_workplace_type"),
            ]
            if item
        ).lower()
        if filters.location and filters.location.lower() not in location_text:
            return False
        if filters.remote_only and "remote" not in location_text:
            return False
        if filters.min_score is not None and (discovery.discovery_score or 0) < filters.min_score:
            return False
        if filters.discovery_status and (discovery.discovery_status or "").lower() != filters.discovery_status.lower():
            return False
        if filters.resolution_status and (discovery.resolution_status or "").lower() != filters.resolution_status.lower():
            return False
        if filters.recent_days is not None:
            cutoff = to_utc_naive(utc_now() - timedelta(days=filters.recent_days))
            last_seen = to_utc_naive(discovery.last_discovered_at)
            if last_seen is None or cutoff is None or last_seen < cutoff:
                return False
        return True
