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
