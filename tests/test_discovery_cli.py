from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from jobtracker.cli.app import app
from jobtracker.company_discovery.scoring import CompanyDiscoveryScoringService
from jobtracker.config.loader import load_app_config
from jobtracker.models import CompanyRecord, NormalizedCompanyDiscovery, NormalizedJobPosting, RawCompanyDiscovery
from jobtracker.storage import (
    CompanyDiscoveryObservationRepository,
    CompanyDiscoveryRepository,
    CompanyResolutionRepository,
    CompanyResolutionORM,
    JobRepository,
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
                company_url="https://pulselabs.dev",
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
                company_url="https://pulselabs.dev",
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
    assert "sources=company_search" in list_result.stdout
    assert "best=greenhouse:pulselabs" in list_result.stdout
    assert "next=promote" in list_result.stdout
    assert "Lakeside Robotics" not in list_result.stdout
    assert top_result.exit_code == 0
    assert "1. Pulse Labs | resolution=resolved | discovery=" in top_result.stdout
    assert "sources=company_search" in top_result.stdout
    assert "best=greenhouse:pulselabs" in top_result.stdout
    assert "next=promote" in top_result.stdout


def test_discovery_cli_inbox_is_company_first_entrypoint(sqlite_database_url: str) -> None:
    _seed_discovery_data(sqlite_database_url)

    result = runner.invoke(
        app,
        ["discover", "companies", "inbox", "--database-url", sqlite_database_url],
    )

    assert result.exit_code == 0
    assert "Discovery Inbox" in result.stdout
    assert "Summary: 2 candidates, 1 ready to promote, 1 need resolution, 0 tracked" in result.stdout
    assert "1. Pulse Labs" in result.stdout
    assert "Site:       https://pulselabs.dev" in result.stdout
    assert "Next:       Promote" in result.stdout
    assert "Resolution: resolved | best greenhouse:pulselabs" in result.stdout
    assert "Sources:    company_search" in result.stdout
    assert 'Review:     python -m jobtracker discover companies review --company "Pulse Labs"' in result.stdout


def test_discovery_cli_review_command_shows_next_action_and_candidates(sqlite_database_url: str) -> None:
    _seed_discovery_data(sqlite_database_url)

    result = runner.invoke(
        app,
        ["discover", "companies", "review", "--database-url", sqlite_database_url, "--company", "Pulse Labs"],
    )

    assert result.exit_code == 0
    assert "Pulse Labs | status=candidate | resolution=resolved" in result.stdout
    assert "best=greenhouse:pulselabs" in result.stdout
    assert "next=promote" in result.stdout
    assert 'Recommended command: python -m jobtracker discover companies promote --company "Pulse Labs"' in result.stdout
    assert "Resolution candidates:" in result.stdout
    assert "greenhouse:pulselabs | confidence=0.90 | selected=yes" in result.stdout


def test_discovery_cli_review_command_bridges_into_tracked_jobs(sqlite_database_url: str) -> None:
    _seed_discovery_data(sqlite_database_url)
    engine = create_db_engine(get_database_settings(sqlite_database_url))

    with Session(engine) as session:
        discovery_repo = CompanyDiscoveryRepository(session)
        resolution_repo = CompanyResolutionRepository(session)
        pulse = discovery_repo.get_by_selector("Pulse Labs")
        assert pulse is not None
        selected = resolution_repo.get_selected_for_discovery(pulse.id)
        assert selected is not None
        discovery_repo.promote_to_tracked("Pulse Labs", selected_resolution=selected)

        run = SearchRunRepository(session).start(
            started_at=datetime(2026, 4, 19, 13, 0, tzinfo=timezone.utc)
        )
        job = JobRepository(session).upsert(
            NormalizedJobPosting(
                source="greenhouse",
                source_job_id="pulse-job-1",
                source_url="https://boards.greenhouse.io/pulselabs/jobs/1",
                canonical_key="pulselabs:backend-engineer:remote",
                title="Backend Engineer",
                company=CompanyRecord(normalized_name="pulse-labs", display_name="Pulse Labs"),
                location_text="Remote",
                workplace_type="remote",
                status="active",
            ),
            seen_at=run.started_at,
            source="greenhouse",
            source_job_id="pulse-job-1",
        )
        job.fit_score = 84
        job.hiring_score = 78
        job.priority_score = 82
        session.commit()

    result = runner.invoke(
        app,
        ["discover", "companies", "review", "--database-url", sqlite_database_url, "--company", "Pulse Labs"],
    )

    assert result.exit_code == 0
    assert "Pulse Labs | status=tracked | resolution=resolved" in result.stdout
    assert "next=review_jobs" in result.stdout
    assert 'Recommended command: python -m jobtracker jobs top --company "Pulse Labs" --limit 5' in result.stdout
    assert "Tracked jobs:" in result.stdout
    assert "Pulse Labs | Backend Engineer | Remote | active | priority=82" in result.stdout


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
