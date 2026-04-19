from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from jobtracker.company_discovery.directory_adapter import CompanyDirectoryDiscoveryAdapter
from jobtracker.company_discovery.ecosystem_adapter import AustinEcosystemDiscoveryAdapter
from jobtracker.company_discovery.registry import CompanyDiscoveryRegistry, build_default_company_discovery_registry
from jobtracker.company_discovery.runner import CompanyDiscoveryRunner
from jobtracker.company_discovery.search_adapter import CompanySearchDiscoveryAdapter
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
    assert summary.total_resolutions >= 3
    assert len(search_runs) == 1
    assert len(discoveries) == 2
    assert len(observations) == 3
    assert len(resolutions) >= 2
    assert pulse_observations == 2


def test_company_discovery_runner_supports_fetched_source_material(sqlite_database_url: str) -> None:
    app_config = load_app_config(Path("config"))
    app_config.company_discovery.sources[0].enabled = True
    app_config.company_discovery.sources[1].enabled = True
    app_config.company_discovery.sources[0].params = {
        "results_urls": ["https://example.com/company-search.json"]
    }
    app_config.company_discovery.sources[1].params = {
        "entries_urls": ["https://example.com/austin-ecosystem.json"]
    }

    payload_map = {
        "https://example.com/company-search.json": json.loads(
            Path("tests/fixtures/company_search_results.json").read_text(encoding="utf-8")
        ),
        "https://example.com/austin-ecosystem.json": json.loads(
            Path("tests/fixtures/austin_ecosystem_entries.json").read_text(encoding="utf-8")
        ),
    }
    registry = CompanyDiscoveryRegistry()
    registry.register(
        CompanySearchDiscoveryAdapter(fetch_json=lambda url: payload_map[url])
    )
    registry.register(
        AustinEcosystemDiscoveryAdapter(fetch_json=lambda url: payload_map[url])
    )

    summary = CompanyDiscoveryRunner(registry=registry).run(
        app_config,
        sqlite_database_url,
        started_at=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
    )

    engine = create_db_engine(get_database_settings(sqlite_database_url))
    with Session(engine) as session:
        discoveries = session.scalars(select(CompanyDiscoveryORM)).all()

    assert summary.status == "success"
    assert summary.total_raw_discoveries == 3
    assert len(discoveries) == 2


def test_company_discovery_runner_supports_query_driven_search_sources(sqlite_database_url: str) -> None:
    app_config = load_app_config(Path("config"))
    app_config.company_discovery.sources[0].enabled = True
    app_config.company_discovery.sources[1].enabled = False
    app_config.company_discovery.queries = [
        app_config.company_discovery.queries[0].model_copy(
            update={
                "keywords": ["backend engineer"],
                "locations": ["Austin, TX"],
                "workplace_types": ["hybrid"],
                "source_names": ["company_search"],
            }
        )
    ]
    app_config.company_discovery.sources[0].params = {
        "query_url_template": (
            "https://search.example.test?q={query}&keyword={keyword}&location={location}&workplace={workplace_type}"
        ),
        "results_payload_key": "results",
    }

    search_payload = {
        "results": json.loads(
            Path("tests/fixtures/company_search_results.json").read_text(encoding="utf-8")
        )
    }
    seen_urls: list[str] = []
    registry = CompanyDiscoveryRegistry()
    registry.register(
        CompanySearchDiscoveryAdapter(
            fetch_json=lambda url: (seen_urls.append(url) or search_payload)
        )
    )

    summary = CompanyDiscoveryRunner(registry=registry).run(
        app_config,
        sqlite_database_url,
        started_at=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
    )

    engine = create_db_engine(get_database_settings(sqlite_database_url))
    with Session(engine) as session:
        discoveries = session.scalars(select(CompanyDiscoveryORM)).all()

    assert summary.status == "success"
    assert summary.total_raw_discoveries == 1
    assert len(discoveries) == 1
    assert seen_urls == [
        "https://search.example.test?q=backend+engineer+Austin%2C+TX+hybrid&keyword=backend+engineer&location=Austin%2C+TX&workplace=hybrid"
    ]


def test_company_discovery_runner_merges_cross_source_directory_evidence(sqlite_database_url: str) -> None:
    app_config = load_app_config(Path("config"))
    app_config.company_discovery.sources[0].enabled = True
    app_config.company_discovery.sources[1].enabled = True
    app_config.company_discovery.sources[2].enabled = True
    app_config.company_discovery.sources[0].params["results"] = json.loads(
        Path("tests/fixtures/company_search_results.json").read_text(encoding="utf-8")
    )
    app_config.company_discovery.sources[1].params["entries"] = json.loads(
        Path("tests/fixtures/austin_ecosystem_entries.json").read_text(encoding="utf-8")
    )
    app_config.company_discovery.sources[2].params["entries"] = json.loads(
        Path("tests/fixtures/company_directory_entries.json").read_text(encoding="utf-8")
    )

    runner = CompanyDiscoveryRunner(registry=build_default_company_discovery_registry())
    summary = runner.run(
        app_config,
        sqlite_database_url,
        started_at=datetime(2026, 4, 21, 9, 0, tzinfo=timezone.utc),
    )

    engine = create_db_engine(get_database_settings(sqlite_database_url))
    with Session(engine) as session:
        discoveries = session.scalars(select(CompanyDiscoveryORM)).all()
        pulse = session.scalar(
            select(CompanyDiscoveryORM).where(CompanyDiscoveryORM.normalized_name == "pulse-labs")
        )

    assert summary.status == "success"
    assert summary.total_raw_discoveries == 5
    assert len(discoveries) == 3
    assert pulse is not None
    assert pulse.score_payload["source_names"] == [
        "austin_ecosystem",
        "company_directory",
        "company_search",
    ]
    assert pulse.score_payload["best_resolution"]["platform"] == "greenhouse"


def test_company_discovery_runner_resolves_ats_pattern_results(sqlite_database_url: str) -> None:
    app_config = load_app_config(Path("config"))
    app_config.company_discovery.sources[0].enabled = True
    app_config.company_discovery.sources[1].enabled = False
    app_config.company_discovery.sources[2].enabled = False
    app_config.company_discovery.queries = [
        app_config.company_discovery.queries[0].model_copy(
            update={
                "keywords": ["platform engineer"],
                "locations": ["Remote"],
                "workplace_types": ["remote"],
                "source_names": ["company_search"],
            }
        )
    ]
    app_config.company_discovery.sources[0].params["results"] = json.loads(
        Path("tests/fixtures/company_search_ats_pattern_results.json").read_text(encoding="utf-8")
    )

    summary = CompanyDiscoveryRunner(registry=build_default_company_discovery_registry()).run(
        app_config,
        sqlite_database_url,
        started_at=datetime(2026, 4, 21, 11, 0, tzinfo=timezone.utc),
    )

    engine = create_db_engine(get_database_settings(sqlite_database_url))
    with Session(engine) as session:
        orbitworks = session.scalar(
            select(CompanyDiscoveryORM).where(CompanyDiscoveryORM.normalized_name == "orbitworks")
        )
        selected = session.scalar(
            select(CompanyResolutionORM).join(CompanyDiscoveryORM).where(
                CompanyDiscoveryORM.normalized_name == "orbitworks",
                CompanyResolutionORM.is_selected.is_(True),
            )
        )

    assert summary.status == "success"
    assert summary.total_raw_discoveries == 1
    assert orbitworks is not None
    assert orbitworks.resolution_status == "resolved"
    assert selected is not None
    assert selected.platform == "lever"
    assert selected.identifier == "orbitworks"
