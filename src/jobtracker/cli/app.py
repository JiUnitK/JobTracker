from __future__ import annotations

import typer

from jobtracker import __version__
from jobtracker.cli.company_discovery import discover_app
from jobtracker.cli.config import config_app
from jobtracker.cli.database import db_app
from jobtracker.cli.job_search import search_app
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
app.add_typer(search_app, name="search")
register_run_command(app)


@app.callback()
def main_callback() -> None:
    configure_logging()


@app.command()
def version() -> None:
    """Print the current JobTracker version."""
    typer.echo(f"jobtracker {__version__}")


@app.command("web")
def run_web(
    config_dir: str = typer.Option(
        "config",
        "--config-dir",
        help="Directory containing JobTracker YAML config files.",
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Host interface for the local web UI."),
    port: int = typer.Option(8765, "--port", help="Port for the local web UI."),
) -> None:
    """Start the local browser UI."""
    import uvicorn

    from jobtracker.web.app import create_app

    typer.echo(f"Starting JobTracker web UI at http://{host}:{port}")
    uvicorn.run(create_app(config_dir=config_dir), host=host, port=port)


def main() -> None:
    app()
