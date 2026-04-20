from __future__ import annotations

from pathlib import Path

import typer

from jobtracker.config.loader import load_app_config
from jobtracker.job_search.brave_adapter import BraveSearchError
from jobtracker.job_search.planner import JobSearchOverrides
from jobtracker.job_search.reporting import (
    format_instant_job_search_json,
    format_instant_job_search_markdown,
    format_instant_job_search_summary,
)
from jobtracker.job_search.runner import InstantJobSearchRunner


search_app = typer.Typer(help="Search for fresh open-web job postings.")


@search_app.command("jobs")
def search_jobs(
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
    days: int | None = typer.Option(None, "--days", help="Maximum posting age in days."),
    query: str = typer.Option("", "--query", help="Override configured role/search query."),
    location: str = typer.Option("", "--location", help="Override configured location."),
    limit: int = typer.Option(25, "--limit", help="Maximum number of results to display."),
    include_unknown_age: bool = typer.Option(
        False,
        "--include-unknown-age",
        help="Include results whose posting age cannot be verified.",
    ),
    include_low_fit: bool = typer.Option(
        False,
        "--include-low-fit",
        help="Include results that would otherwise be skipped for low fit.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output structured JSON."),
    markdown_output: Path | None = typer.Option(
        None,
        "--markdown-output",
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Write a Markdown review report to this path.",
    ),
) -> None:
    """Search the open web for fresh matching job postings."""
    app_config = load_app_config(config_dir)
    try:
        summary = InstantJobSearchRunner().run(
            app_config,
            JobSearchOverrides(
                query=query or None,
                location=location or None,
                max_age_days=days,
                include_unknown_age=True if include_unknown_age else None,
                include_low_fit=include_low_fit,
                limit=limit,
            ),
        )
    except (BraveSearchError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if markdown_output is not None:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(
            format_instant_job_search_markdown(summary),
            encoding="utf-8",
        )
    if json_output:
        typer.echo(format_instant_job_search_json(summary))
        return
    typer.echo(format_instant_job_search_summary(summary))
