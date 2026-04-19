from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobtracker.config.loader import load_app_config
from jobtracker.job_tracking.sources.base import SourceAdapter
from jobtracker.job_tracking.sources.registry import SourceRegistry
from jobtracker.job_tracking.sources.runner import RunCoordinator
from jobtracker.models import (
    NormalizedCompanyDiscovery,
    RawJobPosting,
    SearchQuery,
)
from jobtracker.storage import (
    CompanyDiscoveryRepository,
    CompanyResolutionRepository,
    JobORM,
    create_db_engine,
    get_database_settings,
)
from jobtracker.storage.migrations import upgrade_database


class StubGreenhouseAdapter(SourceAdapter):
    source_name = "greenhouse"

    def collect(self, source, query: SearchQuery) -> list[RawJobPosting]:
        board_tokens = source.params.get("board_tokens", [])
        assert "promotedco" in board_tokens
        return [
            RawJobPosting(
                source="greenhouse",
                source_job_id="job-1",
                source_url="https://boards.greenhouse.io/promotedco/jobs/1",
                title="Backend Engineer",
                company_name="PromotedCo",
                location_text="Austin, TX",
                workplace_type="hybrid",
                description_snippet="Python distributed systems role.",
                raw_payload={"id": "job-1"},
            )
        ]


def test_promoted_discovery_flows_into_job_tracking(sqlite_database_url: str) -> None:
    upgrade_database(sqlite_database_url)
    engine = create_db_engine(get_database_settings(sqlite_database_url))
    with Session(engine) as session:
        discovery_repo = CompanyDiscoveryRepository(session)
        resolution_repo = CompanyResolutionRepository(session)
        discovery = discovery_repo.upsert(
            NormalizedCompanyDiscovery(
                source_name="company_search",
                normalized_name="promotedco",
                display_name="PromotedCo",
                source_url="https://example.com/promotedco",
                careers_url="https://boards.greenhouse.io/promotedco",
            ),
            discovered_at=datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc),
        )
        selected = resolution_repo.upsert_candidate(
            company_discovery_id=discovery.id,
            resolution_type="ats_board",
            platform="greenhouse",
            identifier="promotedco",
            url="https://boards.greenhouse.io/promotedco",
            confidence=0.9,
            observed_at=datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc),
        )
        discovery_repo.promote_to_tracked("promotedco", selected_resolution=selected)
        session.commit()

    app_config = load_app_config(Path("config"))
    for source in app_config.sources.sources:
        source.enabled = False
        source.params = {}

    registry = SourceRegistry()
    registry.register(StubGreenhouseAdapter())
    summary = RunCoordinator(registry=registry).run(
        app_config,
        sqlite_database_url,
        run_started_at=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
    )

    with Session(engine) as session:
        jobs = session.scalars(select(JobORM)).all()

    assert summary.status == "success"
    assert summary.total_raw_jobs == 1
    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
