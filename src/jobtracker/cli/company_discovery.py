from __future__ import annotations

from pathlib import Path

import typer

from jobtracker.cli.common import session_factory_for_reporting
from jobtracker.company_discovery.runner import CompanyDiscoveryRunner
from jobtracker.config.loader import load_app_config
from jobtracker.reporting import (
    CompanyDiscoveryReportFilters,
    JobReportFilters,
    ReportingService,
    describe_discovery_action,
)
from jobtracker.storage import (
    CompanyDiscoveryRepository,
    CompanyResolutionRepository,
    create_session_factory,
)
from jobtracker.storage.db import get_database_settings
from jobtracker.storage.migrations import upgrade_database


discover_app = typer.Typer(help="Discover new companies to monitor.")
discover_companies_app = typer.Typer(help="Run company discovery workflows.")
discover_app.add_typer(discover_companies_app, name="companies")


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


def _best_resolution_url(payload: dict) -> str:
    best_resolution = payload.get("best_resolution")
    if isinstance(best_resolution, dict):
        url = str(best_resolution.get("url", "") or "").strip()
        if url:
            return url
    return ""


def _company_site_text(discovery, payload: dict) -> str:
    return (
        str(discovery.company_url or "").strip()
        or str(discovery.careers_url or "").strip()
        or _best_resolution_url(payload)
        or "-"
    )


def _score_bar(score: int | None, *, width: int = 10) -> str:
    value = max(0, min(100, int(score or 0)))
    filled = round((value / 100) * width)
    return "[" + ("#" * filled) + ("-" * (width - filled)) + f"] {value:>3}"


def _action_label(action: str) -> str:
    labels = {
        "promote": "Promote",
        "resolve": "Resolve",
        "review_resolution": "Review resolution",
        "review_jobs": "Review jobs",
        "watch": "Watch",
        "ignored": "Ignored",
    }
    return labels.get(action, action.replace("_", " ").title())


def _review_command(display_name: str) -> str:
    return f'python -m jobtracker discover companies review --company "{display_name}"'


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
    session_factory = session_factory_for_reporting(database_url or None)
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
    session_factory = session_factory_for_reporting(database_url or None)
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
    typer.echo("Discovery Inbox")
    typer.echo("=" * 15)
    typer.echo(
        "Summary: "
        f"{summary['candidate']} candidates, "
        f"{summary['ready_to_promote']} ready to promote, "
        f"{summary['needs_resolution']} need resolution, "
        f"{summary['tracked']} tracked"
    )
    if new_only:
        typer.echo("Filter: new companies only")
    typer.echo("")
    if not discoveries:
        typer.echo("No candidate discoveries found.")
        return
    for index, discovery in enumerate(discoveries, start=1):
        payload = _discovery_payload(discovery)
        source_text = _source_text(payload)
        best_text = _best_resolution_text(payload)
        site_text = _company_site_text(discovery, payload)
        next_action = describe_discovery_action(discovery)
        typer.echo(f"{index}. {discovery.display_name}")
        typer.echo(f"   Site:       {site_text}")
        typer.echo(f"   Next:       {_action_label(next_action)}")
        typer.echo(
            "   Scores:     "
            f"discovery {_score_bar(discovery.discovery_score)}  "
            f"fit {_score_bar(discovery.fit_score)}  "
            f"hiring {_score_bar(discovery.hiring_score)}"
        )
        typer.echo(f"   Resolution: {discovery.resolution_status} | best {best_text}")
        typer.echo(f"   Sources:    {source_text or '-'}")
        typer.echo(f"   Review:     {_review_command(discovery.display_name)}")
        typer.echo("")


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
    session_factory = session_factory_for_reporting(database_url or None)
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
    session_factory = session_factory_for_reporting(database_url or None)
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
    session_factory = session_factory_for_reporting(database_url or None)
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
    session_factory = session_factory_for_reporting(database_url or None)
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
    session_factory = session_factory_for_reporting(database_url or None)
    with session_factory() as session:
        discovery_repo = CompanyDiscoveryRepository(session)
        try:
            discovery = discovery_repo.mark_ignored(company)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        session.commit()
        typer.echo(f"Ignored discovered company: {discovery.display_name}")
