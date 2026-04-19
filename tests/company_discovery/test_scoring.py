from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from jobtracker.company_discovery.scoring import CompanyDiscoveryScoringService
from jobtracker.config.loader import load_app_config
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


def test_company_discovery_scoring_generates_explainable_scores(sqlite_database_url: str) -> None:
    engine = create_db_engine(get_database_settings(sqlite_database_url))
    initialize_database(engine)
    with Session(engine) as session:
        run = SearchRunRepository(session).start(
            trigger_type="company_discovery",
            started_at=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        )
        discovery = CompanyDiscoveryRepository(session).upsert(
            NormalizedCompanyDiscovery(
                source_name="company_search",
                normalized_name="pulse-labs",
                display_name="Pulse Labs",
                source_url="https://example-search.com/results/pulse",
                careers_url="https://boards.greenhouse.io/pulselabs",
                job_title="Backend Engineer",
                location_text="Austin, TX",
                workplace_type="hybrid",
                evidence_kind="job_result",
            ),
            discovered_at=run.started_at,
        )
        observation_repo = CompanyDiscoveryObservationRepository(session)
        for idx in range(2):
            observation_repo.create(
                company_discovery_id=discovery.id,
                search_run_id=run.id,
                raw_discovery=RawCompanyDiscovery(
                    source_name="company_search",
                    source_type="search",
                    source_url=f"https://example-search.com/results/pulse-{idx}",
                    company_name="Pulse Labs",
                    careers_url="https://boards.greenhouse.io/pulselabs",
                    job_title="Backend Engineer",
                    location_text="Austin, TX",
                    workplace_type="hybrid",
                    evidence_kind="job_result",
                    raw_payload={"tags": ["python", "distributed systems"]},
                ),
                observed_at=run.started_at,
            )
        CompanyResolutionRepository(session).upsert_candidate(
            company_discovery_id=discovery.id,
            resolution_type="ats_board",
            platform="greenhouse",
            identifier="pulselabs",
            url="https://boards.greenhouse.io/pulselabs",
            confidence=0.9,
            observed_at=run.started_at,
        )

        config = load_app_config(Path("config"))
        result = CompanyDiscoveryScoringService(session, config).score_discovery(
            discovery,
            now=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        )

        assert result.fit_score >= 75
        assert result.hiring_score >= 80
        assert result.discovery_score >= 78
        assert "observed roles closely match target titles" in result.payload["fit_reasons"]
        assert "company resolves to a high-confidence ATS" in result.payload["hiring_reasons"]
        assert result.payload["best_resolution"]["platform"] == "greenhouse"
        assert result.payload["resolution_candidate_count"] == 1
