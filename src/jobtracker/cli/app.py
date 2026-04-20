from __future__ import annotations

from pathlib import Path

import typer

from jobtracker import __version__
from jobtracker.company_discovery.runner import CompanyDiscoveryRunner
from jobtracker.config.loader import load_app_config
from jobtracker.logging import configure_logging
from jobtracker.job_tracking.sources.registry import build_default_registry
from jobtracker.job_tracking.sources.runner import RunCoordinator
from jobtracker.reporting import (
    CompanyDiscoveryReportFilters,
    JobReportFilters,
    ReportingService,
    describe_discovery_action,
)
from jobtracker.storage import (
    CompanyDiscoveryRepository,
    CompanyResolutionRepository,
    SourceRepository,
    create_session_factory,
)
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
discover_app = typer.Typer(help="Discover new companies to monitor.")
discover_companies_app = typer.Typer(help="Run company discovery workflows.")
app.add_typer(config_app, name="config")
app.add_typer(db_app, name="db")
app.add_typer(sources_app, name="sources")
app.add_typer(jobs_app, name="jobs")
app.add_typer(companies_app, name="companies")
app.add_typer(export_app, name="export")
app.add_typer(discover_app, name="discover")
discover_app.add_typer(discover_companies_app, name="companies")


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


def _discovery_payload(discovery) -> dict:
    return discovery.score_payload if isinstance(discovery.score_payload, dict) else {}


def _source_text(payload: dict) -> str:
    source_names = payload.get("source_names", [])
    return ",".join(source_names) if isinstance(source_names, list) else "-"


def _best_resolution_text(payload: dict) -> str:
    best_resolution = payload.get("best_resolution")
    if isinstance(best_resolution, dict):
        platform = str(best_resolution.get("platform", "") or "")
        identifier = str(best_resolution.get("identifier", "") or "")
        if platform and identifier:
            return f"{platform}:{identifier}"
    return "-"


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


@discover_companies_app.command("run")
def run_company_discovery(
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
        help="Database URL to use for the discovery run.",
    ),
) -> None:
    """Run company discovery across enabled discovery sources."""
    app_config = load_app_config(config_dir)
    summary = CompanyDiscoveryRunner().run(app_config, database_url or None)
    typer.echo(
        "Discovery run complete: "
        f"status={summary.status}, "
        f"search_run_id={summary.search_run_id}, "
        f"raw_discoveries={summary.total_raw_discoveries}, "
        f"persisted_discoveries={summary.total_persisted_discoveries}, "
        f"observations={summary.total_observations}, "
        f"resolutions={summary.total_resolutions}"
    )


@discover_companies_app.command("list")
def list_discovered_companies(
    database_url: str = typer.Option("", "--database-url", help="Database URL to read from."),
    location: str = typer.Option("", "--location", help="Filter discoveries by location substring."),
    remote_only: bool = typer.Option(False, "--remote-only", help="Show remote-friendly discoveries only."),
    recent_days: int = typer.Option(0, "--recent-days", help="Only include discoveries seen in the last N days."),
    min_score: int = typer.Option(0, "--min-score", help="Minimum discovery score."),
    discovery_status: str = typer.Option("", "--status", help="Filter by discovery status."),
    resolution_status: str = typer.Option("", "--resolution-status", help="Filter by resolution status."),
    sort_by: str = typer.Option("actionable", "--sort-by", help="Sort by actionable, discovery, fit, hiring, or recent."),
    limit: int = typer.Option(20, "--limit", help="Maximum number of discoveries to display."),
) -> None:
    """List discovered companies with discovery and resolution status."""
    session_factory = _session_for_reporting(database_url or None)
    filters = CompanyDiscoveryReportFilters(
        location=location or None,
        remote_only=remote_only,
        recent_days=recent_days or None,
        min_score=min_score or None,
        discovery_status=discovery_status or None,
        resolution_status=resolution_status or None,
        sort_by=sort_by,
        limit=limit,
    )
    with session_factory() as session:
        discoveries = ReportingService(session).list_discovered_companies(filters)
    if not discoveries:
        typer.echo("No discovered companies found.")
        return
    for discovery in discoveries:
        payload = _discovery_payload(discovery)
        source_text = _source_text(payload)
        best_text = _best_resolution_text(payload)
        next_action = describe_discovery_action(discovery)
        typer.echo(
            " | ".join(
                [
                    discovery.display_name,
                    discovery.discovery_status,
                    f"resolution={discovery.resolution_status}",
                    f"discovery={discovery.discovery_score or 0}",
                    f"fit={discovery.fit_score or 0}",
                    f"hiring={discovery.hiring_score or 0}",
                    f"sources={source_text or '-'}",
                    f"best={best_text}",
                    f"next={next_action}",
                ]
            )
        )


@discover_companies_app.command("inbox")
def discovery_inbox(
    database_url: str = typer.Option("", "--database-url", help="Database URL to read from."),
    new_only: bool = typer.Option(False, "--new-only", help="Show only companies discovered for the first time in the last run."),
    limit: int = typer.Option(10, "--limit", help="Maximum number of discoveries to display."),
) -> None:
    """Show the company-first discovery inbox with the most actionable discoveries."""
    session_factory = _session_for_reporting(database_url or None)
    filters = CompanyDiscoveryReportFilters(
        discovery_status="candidate",
        sort_by="actionable",
        new_only=new_only,
        limit=limit,
    )
    with session_factory() as session:
        service = ReportingService(session)
        discoveries = service.list_discovered_companies(filters)
        summary = service.summarize_discovery_inbox()
    typer.echo(
        "Discovery inbox: "
        f"candidate={summary['candidate']} | "
        f"watch={summary['watch']} | "
        f"tracked={summary['tracked']} | "
        f"ready_to_promote={summary['ready_to_promote']} | "
        f"needs_resolution={summary['needs_resolution']}"
    )
    if not discoveries:
        typer.echo("No candidate discoveries found.")
        return
    for discovery in discoveries:
        payload = _discovery_payload(discovery)
        source_text = _source_text(payload)
        best_text = _best_resolution_text(payload)
        next_action = describe_discovery_action(discovery)
        typer.echo(
            " | ".join(
                [
                    discovery.display_name,
                    f"resolution={discovery.resolution_status}",
                    f"discovery={discovery.discovery_score or 0}",
                    f"fit={discovery.fit_score or 0}",
                    f"hiring={discovery.hiring_score or 0}",
                    f"sources={source_text or '-'}",
                    f"best={best_text}",
                    f"next={next_action}",
                ]
            )
        )


@discover_companies_app.command("top")
def top_discovered_companies(
    database_url: str = typer.Option("", "--database-url", help="Database URL to read from."),
    recent_days: int = typer.Option(0, "--recent-days", help="Only include discoveries seen in the last N days."),
    min_score: int = typer.Option(0, "--min-score", help="Minimum discovery score."),
    resolution_status: str = typer.Option("", "--resolution-status", help="Filter by resolution status."),
    sort_by: str = typer.Option("actionable", "--sort-by", help="Sort by actionable, discovery, fit, hiring, or recent."),
    limit: int = typer.Option(10, "--limit", help="Maximum number of discoveries to display."),
) -> None:
    """Show the top-ranked discovered companies."""
    session_factory = _session_for_reporting(database_url or None)
    filters = CompanyDiscoveryReportFilters(
        recent_days=recent_days or None,
        min_score=min_score or None,
        resolution_status=resolution_status or None,
        sort_by=sort_by,
        limit=limit,
    )
    with session_factory() as session:
        discoveries = ReportingService(session).list_discovered_companies(filters)
    if not discoveries:
        typer.echo("No discovered companies found.")
        return
    for index, discovery in enumerate(discoveries, start=1):
        payload = _discovery_payload(discovery)
        source_text = _source_text(payload)
        best_text = _best_resolution_text(payload)
        next_action = describe_discovery_action(discovery)
        typer.echo(
            f"{index}. {discovery.display_name} | resolution={discovery.resolution_status} | "
            f"discovery={discovery.discovery_score or 0} | sources={source_text or '-'} | "
            f"best={best_text} | next={next_action}"
        )


@discover_companies_app.command("review")
def review_discovered_company(
    company: str = typer.Option(..., "--company", help="Discovery id, normalized name, or display name."),
    database_url: str = typer.Option("", "--database-url", help="Database URL to read from."),
    job_limit: int = typer.Option(5, "--job-limit", help="Maximum tracked jobs to show when the company is already tracked."),
) -> None:
    """Review one discovered company and the next action to take."""
    session_factory = _session_for_reporting(database_url or None)
    with session_factory() as session:
        discovery_repo = CompanyDiscoveryRepository(session)
        resolution_repo = CompanyResolutionRepository(session)
        discovery = discovery_repo.get_by_selector(company)
        if discovery is None:
            raise typer.BadParameter(f"Discovered company '{company}' was not found.")

        payload = _discovery_payload(discovery)
        source_text = _source_text(payload)
        best_text = _best_resolution_text(payload)
        next_action = describe_discovery_action(discovery)
        typer.echo(
            " | ".join(
                [
                    discovery.display_name,
                    f"status={discovery.discovery_status}",
                    f"resolution={discovery.resolution_status}",
                    f"discovery={discovery.discovery_score or 0}",
                    f"fit={discovery.fit_score or 0}",
                    f"hiring={discovery.hiring_score or 0}",
                    f"sources={source_text or '-'}",
                    f"best={best_text}",
                    f"next={next_action}",
                ]
            )
        )

        recommended_command = ""
        if next_action == "promote":
            recommended_command = f'python -m jobtracker discover companies promote --company "{discovery.display_name}"'
        elif next_action == "resolve":
            recommended_command = f'python -m jobtracker discover companies resolve --company "{discovery.display_name}" --resolution-url "<candidate-url>"'
        elif next_action == "review_jobs":
            recommended_command = f'python -m jobtracker jobs top --company "{discovery.display_name}" --limit {job_limit}'
        elif next_action == "review_resolution":
            recommended_command = f'python -m jobtracker discover companies review --company "{discovery.display_name}"'
        if recommended_command:
            typer.echo(f"Recommended command: {recommended_command}")

        resolutions = resolution_repo.list_for_discovery(discovery.id)
        if resolutions:
            typer.echo("Resolution candidates:")
            for resolution in resolutions:
                typer.echo(
                    " - "
                    + " | ".join(
                        [
                            f"{resolution.platform}:{resolution.identifier}",
                            f"confidence={float(resolution.confidence or 0):.2f}",
                            f"selected={'yes' if resolution.is_selected else 'no'}",
                            resolution.url,
                        ]
                    )
                )

        if discovery.discovery_status == "tracked":
            jobs = ReportingService(session).list_jobs(
                JobReportFilters(
                    company=discovery.display_name,
                    limit=job_limit,
                    sort_by="priority",
                )
            )
            if jobs:
                typer.echo("Tracked jobs:")
                for job in jobs:
                    company_name = job.company.display_name if job.company is not None else discovery.display_name
                    typer.echo(
                        " - "
                        + " | ".join(
                            [
                                company_name,
                                job.title,
                                job.location_text or "-",
                                job.current_status,
                                f"priority={job.priority_score or 0}",
                            ]
                        )
                    )
            else:
                typer.echo("Tracked jobs: none yet. Run `python -m jobtracker run` after promotion.")


@discover_companies_app.command("resolve")
def resolve_discovered_company(
    company: str = typer.Option(..., "--company", help="Discovery id, normalized name, or display name."),
    resolution_url: str = typer.Option(
        "",
        "--resolution-url",
        help="Specific resolution URL to select when multiple candidates exist.",
    ),
    database_url: str = typer.Option("", "--database-url", help="Database URL to read from."),
) -> None:
    """Accept a resolution candidate for a discovered company."""
    session_factory = _session_for_reporting(database_url or None)
    with session_factory() as session:
        discovery_repo = CompanyDiscoveryRepository(session)
        resolution_repo = CompanyResolutionRepository(session)
        discovery = discovery_repo.get_by_selector(company)
        if discovery is None:
            raise typer.BadParameter(f"Discovered company '{company}' was not found.")
        try:
            selected = resolution_repo.select_resolution(
                discovery.id,
                resolution_url=resolution_url or None,
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        session.commit()
        typer.echo(
            f"Selected resolution for {discovery.display_name}: "
            f"{selected.platform} | {selected.url}"
        )


@discover_companies_app.command("promote")
def promote_discovered_company(
    company: str = typer.Option(..., "--company", help="Discovery id, normalized name, or display name."),
    resolution_url: str = typer.Option(
        "",
        "--resolution-url",
        help="Specific resolution URL to select before promotion.",
    ),
    database_url: str = typer.Option("", "--database-url", help="Database URL to read from."),
) -> None:
    """Promote a discovered company into tracked monitoring."""
    session_factory = _session_for_reporting(database_url or None)
    with session_factory() as session:
        discovery_repo = CompanyDiscoveryRepository(session)
        resolution_repo = CompanyResolutionRepository(session)
        discovery = discovery_repo.get_by_selector(company)
        if discovery is None:
            raise typer.BadParameter(f"Discovered company '{company}' was not found.")
        try:
            selected = resolution_repo.select_resolution(
                discovery.id,
                resolution_url=resolution_url or None,
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        if selected.platform not in {"greenhouse", "lever", "ashby"}:
            raise typer.BadParameter(
                "Promotion currently requires a selected ATS resolution on greenhouse, lever, or ashby."
            )
        promoted = discovery_repo.promote_to_tracked(
            company,
            selected_resolution=selected,
        )
        session.commit()
        typer.echo(
            f"Promoted {promoted.display_name} into tracked monitoring via "
            f"{selected.platform}:{selected.identifier}"
        )


@discover_companies_app.command("fingerprint")
def fingerprint_discovered_companies(
    database_url: str = typer.Option("", "--database-url", help="Database URL to use."),
) -> None:
    """Probe Greenhouse, Lever, and Ashby for unresolved discovered companies."""
    from jobtracker.company_discovery.fingerprinting import ATSFingerprintingService

    settings = get_database_settings(database_url or None)
    upgrade_database(settings.url)
    session_factory = create_session_factory(settings)

    with session_factory() as session:
        service = ATSFingerprintingService(session)
        results = service.fingerprint_unresolved()
        session.commit()

    if not results:
        typer.echo("No new ATS boards found for unresolved companies.")
        return

    typer.echo(f"Found ATS boards for {len(results)} companies:")
    for name, hits in results.items():
        for hit in hits:
            typer.echo(f"  {name} -> {hit.platform}:{hit.slug} ({hit.board_url})")


@discover_companies_app.command("ignore")
def ignore_discovered_company(
    company: str = typer.Option(..., "--company", help="Discovery id, normalized name, or display name."),
    database_url: str = typer.Option("", "--database-url", help="Database URL to read from."),
) -> None:
    """Ignore a discovered company."""
    session_factory = _session_for_reporting(database_url or None)
    with session_factory() as session:
        discovery_repo = CompanyDiscoveryRepository(session)
        try:
            discovery = discovery_repo.mark_ignored(company)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        session.commit()
        typer.echo(f"Ignored discovered company: {discovery.display_name}")


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
    session_factory = _session_for_reporting(database_url or None)
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
    company: str = typer.Option("", "--company", help="Filter jobs by company substring."),
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
