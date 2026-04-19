from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from jobtracker.cli.app import app
from jobtracker.company_discovery.scoring import CompanyDiscoveryScoringService
from jobtracker.config.loader import load_app_config
from jobtracker.models import NormalizedCompanyDiscovery, RawCompanyDiscovery
from jobtracker.storage import (
    CompanyDiscoveryObservationRepository,
    CompanyDiscoveryRepository,
    CompanyResolutionRepository,
    CompanyResolutionORM,
    SearchRunRepository,
    create_db_engine,
    get_database_settings,
)
from jobtracker.storage.migrations import upgrade_database


runner = CliRunner()


def _seed_discovery_data(sqlite_database_url: str) -> None:
    upgrade_database(sqlite_database_url)
    engine = create_db_engine(get_database_settings(sqlite_database_url))
    with Session(engine) as session:
        run = SearchRunRepository(session).start(
            trigger_type="company_discovery",
            started_at=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        )
        discovery_repo = CompanyDiscoveryRepository(session)
        observation_repo = CompanyDiscoveryObservationRepository(session)
        resolution_repo = CompanyResolutionRepository(session)

        pulse = discovery_repo.upsert(
            NormalizedCompanyDiscovery(
                source_name="company_search",
                normalized_name="pulse-labs",
                display_name="Pulse Labs",
                source_url="https://example-search.com/pulse",
                careers_url="https://boards.greenhouse.io/pulselabs",
                job_title="Backend Engineer",
                location_text="Austin, TX",
                workplace_type="hybrid",
            ),
            discovered_at=run.started_at,
        )
        observation_repo.create(
            company_discovery_id=pulse.id,
            search_run_id=run.id,
            raw_discovery=RawCompanyDiscovery(
                source_name="company_search",
                source_type="search",
                source_url="https://example-search.com/pulse",
                company_name="Pulse Labs",
                careers_url="https://boards.greenhouse.io/pulselabs",
                job_title="Backend Engineer",
                location_text="Austin, TX",
                workplace_type="hybrid",
                raw_payload={"tags": ["python", "distributed systems"]},
            ),
            observed_at=run.started_at,
        )
        resolution_repo.upsert_candidate(
            company_discovery_id=pulse.id,
            resolution_type="ats_board",
            platform="greenhouse",
            identifier="pulselabs",
            url="https://boards.greenhouse.io/pulselabs",
            confidence=0.9,
            observed_at=run.started_at,
        )

        lakeside = discovery_repo.upsert(
            NormalizedCompanyDiscovery(
                source_name="austin_ecosystem",
                normalized_name="lakeside-robotics",
                display_name="Lakeside Robotics",
                source_url="https://austin.example.com/lakeside",
                careers_url="https://lakeside.dev/careers",
                job_title="Software Engineer",
                location_text="Remote",
                workplace_type="remote",
            ),
            discovered_at=run.started_at,
        )
        observation_repo.create(
            company_discovery_id=lakeside.id,
            search_run_id=run.id,
            raw_discovery=RawCompanyDiscovery(
                source_name="austin_ecosystem",
                source_type="ecosystem",
                source_url="https://austin.example.com/lakeside",
                company_name="Lakeside Robotics",
                careers_url="https://lakeside.dev/careers",
                job_title="Software Engineer",
                location_text="Remote",
                workplace_type="remote",
                raw_payload={"role_focus": ["software engineer"]},
            ),
            observed_at=run.started_at,
        )
        resolution_repo.upsert_candidate(
            company_discovery_id=lakeside.id,
            resolution_type="company_url",
            platform="direct",
            identifier="lakeside",
            url="https://lakeside.dev/careers",
            confidence=0.6,
            observed_at=run.started_at,
        )

        CompanyDiscoveryScoringService(session, load_app_config(Path("config"))).score_all_discoveries(
            now=run.started_at,
        )
        session.commit()


def test_discovery_cli_list_and_top_commands(sqlite_database_url: str) -> None:
    _seed_discovery_data(sqlite_database_url)

    list_result = runner.invoke(
        app,
        ["discover", "companies", "list", "--database-url", sqlite_database_url, "--resolution-status", "resolved"],
    )
    top_result = runner.invoke(
        app,
        ["discover", "companies", "top", "--database-url", sqlite_database_url, "--limit", "1"],
    )

    assert list_result.exit_code == 0
    assert "Pulse Labs | candidate | resolution=resolved" in list_result.stdout
    assert "Lakeside Robotics" not in list_result.stdout
    assert top_result.exit_code == 0
    assert "1. Pulse Labs | resolution=resolved" in top_result.stdout


def test_discovery_cli_inbox_is_company_first_entrypoint(sqlite_database_url: str) -> None:
    _seed_discovery_data(sqlite_database_url)

    result = runner.invoke(
        app,
        ["discover", "companies", "inbox", "--database-url", sqlite_database_url],
    )

    assert result.exit_code == 0
    assert "Discovery inbox: candidate=2" in result.stdout
    assert "Pulse Labs | resolution=resolved" in result.stdout


def test_discovery_cli_resolve_promote_and_ignore_commands(sqlite_database_url: str) -> None:
    _seed_discovery_data(sqlite_database_url)
    engine = create_db_engine(get_database_settings(sqlite_database_url))

    with Session(engine) as session:
        conflicting = CompanyDiscoveryRepository(session).upsert(
            NormalizedCompanyDiscovery(
                source_name="company_search",
                normalized_name="conflictco",
                display_name="ConflictCo",
                source_url="https://example.com/conflictco",
            ),
            discovered_at=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        )
        resolution_repo = CompanyResolutionRepository(session)
        resolution_repo.upsert_candidate(
            company_discovery_id=conflicting.id,
            resolution_type="ats_board",
            platform="greenhouse",
            identifier="conflictco-gh",
            url="https://boards.greenhouse.io/conflictco",
            confidence=0.8,
            observed_at=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        )
        resolution_repo.upsert_candidate(
            company_discovery_id=conflicting.id,
            resolution_type="ats_board",
            platform="lever",
            identifier="conflictco-lever",
            url="https://jobs.lever.co/conflictco",
            confidence=0.8,
            observed_at=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        )
        session.commit()

    resolve_result = runner.invoke(
        app,
        [
            "discover",
            "companies",
            "resolve",
            "--database-url",
            sqlite_database_url,
            "--company",
            "ConflictCo",
            "--resolution-url",
            "https://jobs.lever.co/conflictco",
        ],
    )
    promote_result = runner.invoke(
        app,
        [
            "discover",
            "companies",
            "promote",
            "--database-url",
            sqlite_database_url,
            "--company",
            "Pulse Labs",
        ],
    )
    ignore_result = runner.invoke(
        app,
        [
            "discover",
            "companies",
            "ignore",
            "--database-url",
            sqlite_database_url,
            "--company",
            "Lakeside Robotics",
        ],
    )

    assert resolve_result.exit_code == 0
    assert "Selected resolution for ConflictCo: lever" in resolve_result.stdout
    assert promote_result.exit_code == 0
    assert "Promoted Pulse Labs into tracked monitoring via greenhouse:pulselabs" in promote_result.stdout
    assert ignore_result.exit_code == 0
    assert "Ignored discovered company: Lakeside Robotics" in ignore_result.stdout

    with Session(engine) as session:
        pulse = CompanyDiscoveryRepository(session).get_by_selector("Pulse Labs")
        lakeside = CompanyDiscoveryRepository(session).get_by_selector("Lakeside Robotics")
        conflict = CompanyDiscoveryRepository(session).get_by_selector("ConflictCo")
        selected_conflict = session.scalar(
            select(CompanyResolutionORM).where(
                CompanyResolutionORM.company_discovery_id == conflict.id,
                CompanyResolutionORM.is_selected.is_(True),
            )
        )

        assert pulse is not None
        assert pulse.discovery_status == "tracked"
        assert pulse.company_id is not None
        assert lakeside is not None
        assert lakeside.discovery_status == "ignored"
        assert conflict is not None
        assert conflict.resolution_status == "resolved"
        assert selected_conflict is not None
        assert selected_conflict.platform == "lever"
