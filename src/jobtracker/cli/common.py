from __future__ import annotations

from jobtracker.storage import create_session_factory
from jobtracker.storage.db import get_database_settings
from jobtracker.storage.migrations import upgrade_database


def session_factory_for_reporting(database_url: str | None = None):
    settings = get_database_settings(database_url)
    upgrade_database(settings.url)
    return create_session_factory(settings)
