from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from jobtracker.models import NormalizedCompanyDiscovery
from jobtracker.storage import (
    CompanyDiscoveryRepository,
    CompanyResolutionRepository,
    create_db_engine,
    get_database_settings,
    initialize_database,
)


def test_resolution_repository_marks_conflicted_when_top_candidates_tie(sqlite_database_url: str) -> None:
    engine = create_db_engine(get_database_settings(sqlite_database_url))
    initialize_database(engine)
    with Session(engine) as session:
        discovery = CompanyDiscoveryRepository(session).upsert(
            NormalizedCompanyDiscovery(
                source_name="company_search",
                normalized_name="example",
                display_name="Example",
                source_url="https://example.com/result",
            ),
            discovered_at=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        )
        repo = CompanyResolutionRepository(session)
        repo.upsert_candidate(
            company_discovery_id=discovery.id,
            resolution_type="ats_board",
            platform="greenhouse",
            identifier="example-gh",
            url="https://boards.greenhouse.io/example",
            confidence=0.8,
            observed_at=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        )
        repo.upsert_candidate(
            company_discovery_id=discovery.id,
            resolution_type="ats_board",
            platform="lever",
            identifier="example-lever",
            url="https://jobs.lever.co/example",
            confidence=0.8,
            observed_at=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        )
        session.refresh(discovery)

        assert discovery.resolution_status == "conflicted"


def test_resolution_repository_prefers_higher_confidence_ats_candidate(sqlite_database_url: str) -> None:
    engine = create_db_engine(get_database_settings(sqlite_database_url))
    initialize_database(engine)
    with Session(engine) as session:
        discovery = CompanyDiscoveryRepository(session).upsert(
            NormalizedCompanyDiscovery(
                source_name="company_search",
                normalized_name="orbitworks",
                display_name="OrbitWorks",
                source_url="https://example.com/orbitworks",
            ),
            discovered_at=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        )
        repo = CompanyResolutionRepository(session)
        repo.upsert_candidate(
            company_discovery_id=discovery.id,
            resolution_type="careers_page",
            platform="direct",
            identifier="orbitworks",
            url="https://orbitworks.dev/careers",
            confidence=0.72,
            observed_at=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        )
        selected = repo.upsert_candidate(
            company_discovery_id=discovery.id,
            resolution_type="ats_board",
            platform="lever",
            identifier="orbitworks",
            url="https://jobs.lever.co/orbitworks",
            confidence=0.92,
            observed_at=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        )
        session.refresh(discovery)

        assert discovery.resolution_status == "resolved"
        assert selected.is_selected is True
