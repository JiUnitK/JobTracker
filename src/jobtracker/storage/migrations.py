from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from jobtracker.storage.db import ensure_database_path, get_database_settings


def get_alembic_config(database_url: str, script_location: Path | None = None) -> Config:
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    config.set_main_option(
        "script_location",
        str(script_location or (root / "alembic")),
    )
    return config


def upgrade_database(database_url: str, revision: str = "head") -> None:
    ensure_database_path(get_database_settings(database_url))
    command.upgrade(get_alembic_config(database_url), revision)
