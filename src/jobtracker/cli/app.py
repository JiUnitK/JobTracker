from __future__ import annotations

import typer

from jobtracker import __version__
from jobtracker.cli.company_discovery import discover_app
from jobtracker.cli.config import config_app
from jobtracker.cli.database import db_app
from jobtracker.cli.sources import sources_app
from jobtracker.cli.tracked_jobs import (
    companies_app,
    export_app,
    jobs_app,
    register_run_command,
)
from jobtracker.logging import configure_logging


app = typer.Typer(
    help="Track job opportunities, companies, and hiring activity.",
    no_args_is_help=True,
)
app.add_typer(config_app, name="config")
app.add_typer(db_app, name="db")
app.add_typer(sources_app, name="sources")
app.add_typer(jobs_app, name="jobs")
app.add_typer(companies_app, name="companies")
app.add_typer(export_app, name="export")
app.add_typer(discover_app, name="discover")
register_run_command(app)


@app.callback()
def main_callback() -> None:
    configure_logging()


@app.command()
def version() -> None:
    """Print the current JobTracker version."""
    typer.echo(f"jobtracker {__version__}")


def main() -> None:
    app()
