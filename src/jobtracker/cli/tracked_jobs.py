from __future__ import annotations

from pathlib import Path

import typer

from jobtracker.cli.common import session_factory_for_reporting
from jobtracker.config.loader import load_app_config
from jobtracker.job_tracking.sources.runner import RunCoordinator
from jobtracker.reporting import JobReportFilters, ReportingService


jobs_app = typer.Typer(help="Inspect and rank tracked jobs.")
companies_app = typer.Typer(help="Inspect company hiring activity.")
export_app = typer.Typer(help="Export tracked data.")


def register_run_command(app: typer.Typer) -> None:
    app.command("run")(run_collection)


def run_collection(
    config_dir: Path = typer.Option(
        Path("config"),
        "--config-dir",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Directory containing JobTracker YAML config files.",
    ),
    database_url: str = typer.Option(
        "",
        "--database-url",
        help="Database URL to use for the collection run.",
    ),
) -> None:
    """Run collection across enabled sources and persist the results."""
    app_config = load_app_config(config_dir)
    summary = RunCoordinator().run(app_config, database_url or None)
    typer.echo(
        "Run complete: "
        f"status={summary.status}, "
        f"search_run_id={summary.search_run_id}, "
        f"raw_jobs={summary.total_raw_jobs}, "
        f"persisted_jobs={summary.total_persisted_jobs}, "
        f"observations={summary.total_observations}"
    )


@jobs_app.command("list")
def list_jobs(
    database_url: str = typer.Option("", "--database-url", help="Database URL to read from."),
    company: str = typer.Option("", "--company", help="Filter jobs by company substring."),
    location: str = typer.Option("", "--location", help="Filter jobs by location substring."),
    remote_only: bool = typer.Option(False, "--remote-only", help="Show remote-only jobs."),
    recent_days: int = typer.Option(0, "--recent-days", help="Only include jobs seen in the last N days."),
    min_score: int = typer.Option(0, "--min-score", help="Minimum priority score."),
    status: str = typer.Option("", "--status", help="Filter by lifecycle status: active, stale, closed, unknown."),
    sort_by: str = typer.Option("priority", "--sort-by", help="Sort by priority, fit, hiring, or recent."),
    limit: int = typer.Option(20, "--limit", help="Maximum number of jobs to display."),
) -> None:
    """List tracked jobs with scores and lifecycle status."""
    session_factory = session_factory_for_reporting(database_url or None)
    filters = JobReportFilters(
        company=company or None,
        location=location or None,
        remote_only=remote_only,
        recent_days=recent_days or None,
        min_score=min_score or None,
        status=status or None,
        limit=limit,
        sort_by=sort_by,
    )
    with session_factory() as session:
        jobs = ReportingService(session).list_jobs(filters)
    if not jobs:
        typer.echo("No jobs found.")
        return
    for job in jobs:
        company_name = job.company.display_name if job.company is not None else "Unknown"
        typer.echo(
            " | ".join(
                [
                    company_name,
                    job.title,
                    job.location_text or "-",
                    job.current_status,
                    f"priority={job.priority_score or 0}",
                    f"fit={job.fit_score or 0}",
                    f"hiring={job.hiring_score or 0}",
                ]
            )
        )


@jobs_app.command("top")
def top_jobs(
    database_url: str = typer.Option("", "--database-url", help="Database URL to read from."),
    company: str = typer.Option("", "--company", help="Filter jobs by company substring."),
    remote_only: bool = typer.Option(False, "--remote-only", help="Show remote-only jobs."),
    recent_days: int = typer.Option(0, "--recent-days", help="Only include jobs seen in the last N days."),
    min_score: int = typer.Option(0, "--min-score", help="Minimum priority score."),
    status: str = typer.Option("", "--status", help="Filter by lifecycle status: active, stale, closed, unknown."),
    sort_by: str = typer.Option("priority", "--sort-by", help="Sort by priority, fit, hiring, or recent."),
    limit: int = typer.Option(10, "--limit", help="Maximum number of jobs to display."),
) -> None:
    """Show the top-ranked jobs by priority score."""
    session_factory = session_factory_for_reporting(database_url or None)
    filters = JobReportFilters(
        company=company or None,
        remote_only=remote_only,
        recent_days=recent_days or None,
        min_score=min_score or None,
        status=status or None,
        limit=limit,
        sort_by=sort_by,
    )
    with session_factory() as session:
        jobs = ReportingService(session).list_jobs(filters)
    if not jobs:
        typer.echo("No jobs found.")
        return
    for index, job in enumerate(jobs, start=1):
        company_name = job.company.display_name if job.company is not None else "Unknown"
        typer.echo(
            f"{index}. {company_name} | {job.title} | {job.location_text or '-'} | "
            f"priority={job.priority_score or 0}"
        )


@companies_app.command("list")
def list_companies(
    database_url: str = typer.Option("", "--database-url", help="Database URL to read from."),
    recent_days: int = typer.Option(14, "--recent-days", help="Recent activity window in days."),
    limit: int = typer.Option(20, "--limit", help="Maximum number of companies to display."),
) -> None:
    """List companies ordered by active and recent relevant openings."""
    session_factory = session_factory_for_reporting(database_url or None)
    with session_factory() as session:
        companies = ReportingService(session).list_companies(recent_days=recent_days, limit=limit)
    if not companies:
        typer.echo("No companies found.")
        return
    for company in companies:
        typer.echo(
            " | ".join(
                [
                    str(company["display_name"]),
                    f"active={company['active_relevant_job_count']}",
                    f"recent={company['recent_relevant_job_count']}",
                    f"last_seen={company['last_relevant_opening_seen_at'] or '-'}",
                ]
            )
        )


@export_app.command("csv")
def export_csv(
    output: Path = typer.Option(..., "--output", file_okay=True, dir_okay=False, resolve_path=True),
    database_url: str = typer.Option("", "--database-url", help="Database URL to read from."),
    remote_only: bool = typer.Option(False, "--remote-only", help="Export remote-only jobs."),
    min_score: int = typer.Option(0, "--min-score", help="Minimum priority score."),
    limit: int = typer.Option(100, "--limit", help="Maximum number of jobs to export."),
) -> None:
    """Export filtered jobs to CSV."""
    session_factory = session_factory_for_reporting(database_url or None)
    filters = JobReportFilters(
        remote_only=remote_only,
        min_score=min_score or None,
        limit=limit,
    )
    with session_factory() as session:
        ReportingService(session).export_jobs_csv(output, filters)
    typer.echo(f"Exported CSV: {output}")


@export_app.command("markdown")
def export_markdown(
    output: Path = typer.Option(..., "--output", file_okay=True, dir_okay=False, resolve_path=True),
    database_url: str = typer.Option("", "--database-url", help="Database URL to read from."),
    remote_only: bool = typer.Option(False, "--remote-only", help="Export remote-only jobs."),
    min_score: int = typer.Option(0, "--min-score", help="Minimum priority score."),
    limit: int = typer.Option(20, "--limit", help="Maximum number of jobs to export."),
) -> None:
    """Export filtered jobs to a Markdown review report."""
    session_factory = session_factory_for_reporting(database_url or None)
    filters = JobReportFilters(
        remote_only=remote_only,
        min_score=min_score or None,
        limit=limit,
    )
    with session_factory() as session:
        ReportingService(session).export_jobs_markdown(output, filters)
    typer.echo(f"Exported Markdown: {output}")
