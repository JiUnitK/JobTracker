from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from jobtracker.company_discovery.registry import build_default_company_discovery_registry
from jobtracker.company_discovery.runner import CompanyDiscoveryRunner
from jobtracker.config.loader import load_app_config
from jobtracker.storage import (
    CompanyDiscoveryObservationORM,
    CompanyDiscoveryORM,
    CompanyResolutionORM,
    SearchRunORM,
    create_db_engine,
    get_database_settings,
)


def test_company_discovery_runner_persists_discovery_records(sqlite_database_url: str) -> None:
    app_config = load_app_config(Path("config"))
    app_config.company_discovery.sources[0].enabled = True
    app_config.company_discovery.sources[1].enabled = True
    app_config.company_discovery.sources[0].params["results"] = json.loads(
        Path("tests/fixtures/company_search_results.json").read_text(encoding="utf-8")
    )
    app_config.company_discovery.sources[1].params["entries"] = json.loads(
        Path("tests/fixtures/austin_ecosystem_entries.json").read_text(encoding="utf-8")
    )

    runner = CompanyDiscoveryRunner(registry=build_default_company_discovery_registry())

    summary = runner.run(
        app_config,
        sqlite_database_url,
        started_at=datetime(2026, 4, 19, 21, 0, tzinfo=timezone.utc),
    )

    engine = create_db_engine(get_database_settings(sqlite_database_url))
    with Session(engine) as session:
        search_runs = session.scalars(select(SearchRunORM)).all()
        discoveries = session.scalars(select(CompanyDiscoveryORM)).all()
        observations = session.scalars(select(CompanyDiscoveryObservationORM)).all()
        resolutions = session.scalars(select(CompanyResolutionORM)).all()
        pulse_observations = session.scalar(
            select(func.count(CompanyDiscoveryObservationORM.id)).join(CompanyDiscoveryORM).where(
                CompanyDiscoveryORM.normalized_name == "pulse-labs"
            )
        )

    assert summary.status == "success"
    assert summary.total_raw_discoveries == 3
    assert summary.total_persisted_discoveries == 3
    assert summary.total_observations == 3
    assert summary.total_resolutions == 3
    assert len(search_runs) == 1
    assert len(discoveries) == 2
    assert len(observations) == 3
    assert len(resolutions) == 2
    assert pulse_observations == 2
