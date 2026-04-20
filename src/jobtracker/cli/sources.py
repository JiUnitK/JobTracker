from __future__ import annotations

from pathlib import Path

import typer

from jobtracker.config.loader import load_app_config
from jobtracker.job_tracking.sources.registry import build_default_registry
from jobtracker.storage import SourceRepository, create_session_factory
from jobtracker.storage.db import get_database_settings
from jobtracker.storage.migrations import upgrade_database


sources_app = typer.Typer(help="Inspect configured collection sources.")


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
