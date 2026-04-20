from __future__ import annotations

import typer

from jobtracker.storage.db import get_database_settings
from jobtracker.storage.migrations import upgrade_database


db_app = typer.Typer(help="Manage the local JobTracker database.")


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
