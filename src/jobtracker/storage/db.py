from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from jobtracker.config.models import DatabaseSettings
from jobtracker.storage.base import Base


DEFAULT_DATABASE_URL = "sqlite:///jobtracker.db"


def get_database_settings(database_url: str | None = None, echo: bool = False) -> DatabaseSettings:
    url = database_url or os.environ.get("JOBTRACKER_DATABASE_URL", DEFAULT_DATABASE_URL)
    return DatabaseSettings(url=url, echo=echo)


def ensure_database_path(settings: DatabaseSettings) -> None:
    path = settings.sqlite_path
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)


def create_db_engine(settings: DatabaseSettings) -> Engine:
    ensure_database_path(settings)
    connect_args = {"check_same_thread": False} if settings.is_sqlite else {}
    return create_engine(settings.url, echo=settings.echo, future=True, connect_args=connect_args)


def create_session_factory(settings: DatabaseSettings) -> sessionmaker[Session]:
    engine = create_db_engine(settings)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def initialize_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)
