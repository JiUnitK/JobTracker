from __future__ import annotations

from pathlib import Path

import typer

from jobtracker import __version__
from jobtracker.config.loader import load_app_config
from jobtracker.logging import configure_logging
from jobtracker.reporting import JobReportFilters, ReportingService
from jobtracker.sources.registry import build_default_registry
from jobtracker.sources.runner import RunCoordinator
from jobtracker.storage import SourceRepository, create_session_factory
from jobtracker.storage.db import get_database_settings
from jobtracker.storage.migrations import upgrade_database

app = typer.Typer(
    help="Track job opportunities, companies, and hiring activity.",
    no_args_is_help=True,
)
config_app = typer.Typer(help="Inspect and validate configuration files.")
db_app = typer.Typer(help="Manage the local JobTracker database.")
sources_app = typer.Typer(help="Inspect configured collection sources.")
jobs_app = typer.Typer(help="Inspect and rank tracked jobs.")
companies_app = typer.Typer(help="Inspect company hiring activity.")
export_app = typer.Typer(help="Export tracked data.")
app.add_typer(config_app, name="config")
app.add_typer(db_app, name="db")
app.add_typer(sources_app, name="sources")
app.add_typer(jobs_app, name="jobs")
app.add_typer(companies_app, name="companies")
app.add_typer(export_app, name="export")


@app.callback()
def main_callback() -> None:
    configure_logging()


@app.command()
def version() -> None:
    """Print the current JobTracker version."""
    typer.echo(f"jobtracker {__version__}")


@config_app.command("validate")
def validate_config(
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
) -> None:
    """Validate the config directory against typed models."""
    app_config = load_app_config(config_dir)
    typer.echo(f"Configuration valid: {app_config.summary()}")


def _sync_configured_sources(config_dir: Path, database_url: str | None = None) -> tuple:
    app_config = load_app_config(config_dir)
    settings = get_database_settings(database_url)
    upgrade_database(settings.url)
    session_factory = create_session_factory(settings)
    registry = build_default_registry()

    with session_factory() as session:
        source_repo = SourceRepository(session)
        for source_definition in app_config.sources.sources:
            source_repo.upsert(
                name=source_definition.name,
                reliability_tier=source_definition.reliability_tier,
                enabled=source_definition.enabled,
                base_url=str(source_definition.base_url) if source_definition.base_url else None,
            )
        session.commit()

        db_sources = {source.name: source for source in source_repo.list_all()}
        lines = []
        for source_definition in app_config.sources.sources:
            source = db_sources[source_definition.name]
            has_adapter = registry.get(source_definition.name) is not None
            lines.append(
                " | ".join(
                    [
                        source_definition.name,
                        f"type={source_definition.type}",
                        f"enabled={'yes' if source.enabled else 'no'}",
                        f"tier={source.reliability_tier}",
                        f"adapter={'yes' if has_adapter else 'no'}",
                        f"last_success={source.last_success_at.isoformat() if source.last_success_at else '-'}",
                        f"last_error={source.last_error_at.isoformat() if source.last_error_at else '-'}",
                    ]
                )
            )
    return app_config, lines


def _session_for_reporting(database_url: str | None = None):
    settings = get_database_settings(database_url)
    upgrade_database(settings.url)
    return create_session_factory(settings)


@app.command("run")
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


@sources_app.command("list")
def list_sources(
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
        help="Database URL to use for source status inspection.",
    ),
) -> None:
    """List configured sources and their adapter/health status."""
    _, lines = _sync_configured_sources(config_dir, database_url or None)
    if not lines:
        typer.echo("No sources configured.")
        return
    for line in lines:
        typer.echo(line)


@jobs_app.command("list")
def list_jobs(
    database_url: str = typer.Option("", "--database-url", help="Database URL to read from."),
    location: str = typer.Option("", "--location", help="Filter jobs by location substring."),
    remote_only: bool = typer.Option(False, "--remote-only", help="Show remote-only jobs."),
    recent_days: int = typer.Option(0, "--recent-days", help="Only include jobs seen in the last N days."),
    min_score: int = typer.Option(0, "--min-score", help="Minimum priority score."),
    status: str = typer.Option("", "--status", help="Filter by lifecycle status: active, stale, closed, unknown."),
    sort_by: str = typer.Option("priority", "--sort-by", help="Sort by priority, fit, hiring, or recent."),
    limit: int = typer.Option(20, "--limit", help="Maximum number of jobs to display."),
) -> None:
    """List tracked jobs with scores and lifecycle status."""
    session_factory = _session_for_reporting(database_url or None)
    filters = JobReportFilters(
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
        company = job.company.display_name if job.company is not None else "Unknown"
        typer.echo(
            " | ".join(
                [
                    company,
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
    remote_only: bool = typer.Option(False, "--remote-only", help="Show remote-only jobs."),
    recent_days: int = typer.Option(0, "--recent-days", help="Only include jobs seen in the last N days."),
    min_score: int = typer.Option(0, "--min-score", help="Minimum priority score."),
    status: str = typer.Option("", "--status", help="Filter by lifecycle status: active, stale, closed, unknown."),
    sort_by: str = typer.Option("priority", "--sort-by", help="Sort by priority, fit, hiring, or recent."),
    limit: int = typer.Option(10, "--limit", help="Maximum number of jobs to display."),
) -> None:
    """Show the top-ranked jobs by priority score."""
    session_factory = _session_for_reporting(database_url or None)
    filters = JobReportFilters(
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
        company = job.company.display_name if job.company is not None else "Unknown"
        typer.echo(
            f"{index}. {company} | {job.title} | {job.location_text or '-'} | "
            f"priority={job.priority_score or 0}"
        )


@companies_app.command("list")
def list_companies(
    database_url: str = typer.Option("", "--database-url", help="Database URL to read from."),
    recent_days: int = typer.Option(14, "--recent-days", help="Recent activity window in days."),
    limit: int = typer.Option(20, "--limit", help="Maximum number of companies to display."),
) -> None:
    """List companies ordered by active and recent relevant openings."""
    session_factory = _session_for_reporting(database_url or None)
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
    session_factory = _session_for_reporting(database_url or None)
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
    session_factory = _session_for_reporting(database_url or None)
    filters = JobReportFilters(
        remote_only=remote_only,
        min_score=min_score or None,
        limit=limit,
    )
    with session_factory() as session:
        ReportingService(session).export_jobs_markdown(output, filters)
    typer.echo(f"Exported Markdown: {output}")


@db_app.command("upgrade")
def db_upgrade(
    database_url: str = typer.Option(
        "",
        "--database-url",
        help="Database URL to upgrade. Defaults to JOBTRACKER_DATABASE_URL or sqlite:///jobtracker.db.",
    ),
) -> None:
    """Apply database migrations up to the latest revision."""
    settings = get_database_settings(database_url or None)
    upgrade_database(settings.url)
    typer.echo(f"Database upgraded: {settings.url}")


def main() -> None:
    app()
