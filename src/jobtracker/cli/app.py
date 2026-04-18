from __future__ import annotations

from pathlib import Path

import typer

from jobtracker import __version__
from jobtracker.config.loader import load_app_config
from jobtracker.logging import configure_logging

app = typer.Typer(
    help="Track job opportunities, companies, and hiring activity.",
    no_args_is_help=True,
)
config_app = typer.Typer(help="Inspect and validate configuration files.")
app.add_typer(config_app, name="config")


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


def main() -> None:
    app()
