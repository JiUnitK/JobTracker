from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from jobtracker.models import NormalizedCompanyDiscovery, RawCompanyDiscovery
from jobtracker.storage import (
    CompanyDiscoveryObservationRepository,
    CompanyDiscoveryRepository,
    CompanyResolutionRepository,
    SearchRunRepository,
    create_db_engine,
    get_database_settings,
    initialize_database,
)


def test_company_discovery_repositories_persist_records(sqlite_database_url: str) -> None:
    engine = create_db_engine(get_database_settings(sqlite_database_url))
    initialize_database(engine)

    with Session(engine) as session:
        run_repo = SearchRunRepository(session)
        search_run = run_repo.start(trigger_type="company_discovery")

        discovery_repo = CompanyDiscoveryRepository(session)
        discovery = discovery_repo.upsert(
            NormalizedCompanyDiscovery(
                source_name="company_search",
                normalized_name="example",
                display_name="Example",
                source_url="https://example.com/search/example",
                careers_url="https://boards.greenhouse.io/example",
                job_title="Backend Engineer",
                location_text="Austin, TX",
                workplace_type="hybrid",
                evidence_kind="job_result",
            ),
            discovered_at=datetime(2026, 4, 19, 20, 0, tzinfo=timezone.utc),
        )

        observation_repo = CompanyDiscoveryObservationRepository(session)
        observation = observation_repo.create(
            company_discovery_id=discovery.id,
            search_run_id=search_run.id,
            raw_discovery=RawCompanyDiscovery(
                source_name="company_search",
                source_type="search",
                source_url="https://example.com/search/example",
                company_name="Example",
                careers_url="https://boards.greenhouse.io/example",
                job_title="Backend Engineer",
                location_text="Austin, TX",
                workplace_type="hybrid",
                evidence_kind="job_result",
                raw_payload={"result_id": "1"},
            ),
            observed_at=datetime(2026, 4, 19, 20, 0, tzinfo=timezone.utc),
        )

        resolution_repo = CompanyResolutionRepository(session)
        resolution = resolution_repo.upsert_candidate(
            company_discovery_id=discovery.id,
            resolution_type="ats_board",
            platform="greenhouse",
            identifier="example",
            url="https://boards.greenhouse.io/example",
            confidence=0.9,
            observed_at=datetime(2026, 4, 19, 20, 0, tzinfo=timezone.utc),
        )
        session.commit()

        assert discovery.id is not None
        assert discovery.last_discovered_at == datetime(2026, 4, 19, 20, 0)
        assert observation.id is not None
        assert observation.source_name == "company_search"
        assert resolution.id is not None
        assert discovery.resolution_status == "resolved"
