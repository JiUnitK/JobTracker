from __future__ import annotations

from datetime import datetime, timezone

from jobtracker.models import CompanyRecord, NormalizedJobPosting, RawJobPosting
from jobtracker.storage import (
    JobObservationRepository,
    JobRepository,
    SearchRunRepository,
    SourceRepository,
    create_db_engine,
    get_database_settings,
    initialize_database,
)


def test_repositories_can_insert_and_update_records(sqlite_database_url: str) -> None:
    engine = create_db_engine(get_database_settings(sqlite_database_url))
    initialize_database(engine)

    from sqlalchemy.orm import Session

    with Session(engine) as session:
        source_repo = SourceRepository(session)
        source = source_repo.upsert(
            name="greenhouse",
            reliability_tier="tier1",
            base_url="https://boards.greenhouse.io/",
        )

        run_repo = SearchRunRepository(session)
        search_run = run_repo.start(trigger_type="manual")

        job_repo = JobRepository(session)
        job = job_repo.upsert(
            NormalizedJobPosting(
                source="greenhouse",
                source_job_id="job-1",
                source_url="https://boards.greenhouse.io/example/jobs/1",
                canonical_key="example:backend-engineer:austin",
                title="Backend Engineer",
                company=CompanyRecord(
                    normalized_name="example",
                    display_name="Example",
                    careers_url="https://example.com/careers",
                ),
                location_text="Austin, TX",
                workplace_type="hybrid",
                description_snippet="Build backend systems.",
                status="active",
            ),
            seen_at=datetime(2026, 4, 18, 23, 0, tzinfo=timezone.utc),
        )

        observation_repo = JobObservationRepository(session)
        observation = observation_repo.create(
            job_id=job.id,
            search_run_id=search_run.id,
            raw_job=RawJobPosting(
                source="greenhouse",
                source_job_id="job-1",
                source_url="https://boards.greenhouse.io/example/jobs/1",
                title="Backend Engineer",
                company_name="Example",
                location_text="Austin, TX",
                raw_payload={"id": "job-1"},
            ),
        )

        updated = job_repo.upsert(
            NormalizedJobPosting(
                source="greenhouse",
                source_job_id="job-1",
                source_url="https://boards.greenhouse.io/example/jobs/1?updated=true",
                canonical_key="example:backend-engineer:austin",
                title="Senior Backend Engineer",
                company=CompanyRecord(
                    normalized_name="example",
                    display_name="Example, Inc.",
                    careers_url="https://example.com/careers",
                ),
                location_text="Austin, TX",
                workplace_type="hybrid",
                description_snippet="Build backend systems at scale.",
                status="active",
            ),
            seen_at=datetime(2026, 4, 19, 1, 0, tzinfo=timezone.utc),
        )
        completed_run = run_repo.complete(search_run, status="success", summary={"jobs_seen": 1})
        session.commit()

        assert source.id is not None
        assert observation.id is not None
        assert updated.id == job.id
        assert updated.title == "Senior Backend Engineer"
        assert updated.last_seen_at == datetime(2026, 4, 19, 1, 0)
        assert completed_run.status == "success"
        assert completed_run.summary_json["jobs_seen"] == 1
