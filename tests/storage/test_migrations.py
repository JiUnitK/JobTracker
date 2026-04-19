from __future__ import annotations

import sqlite3

from jobtracker.storage.migrations import upgrade_database


def test_alembic_upgrade_creates_expected_tables(sqlite_database_url: str) -> None:
    upgrade_database(sqlite_database_url)

    db_path = sqlite_database_url.removeprefix("sqlite:///")
    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    assert {"companies", "jobs", "job_observations", "search_runs", "sources"}.issubset(tables)
