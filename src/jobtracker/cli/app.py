from __future__ import annotations

from pathlib import Path

import typer
from sqlalchemy.orm import Session

from jobtracker import __version__
from jobtracker.config.loader import load_app_config
from jobtracker.logging import configure_logging
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
app.add_typer(config_app, name="config")
app.add_typer(db_app, name="db")
app.add_typer(sources_app, name="sources")


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
