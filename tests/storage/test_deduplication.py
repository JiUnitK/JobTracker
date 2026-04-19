from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from jobtracker.models import CompanyRecord, NormalizedJobPosting, RawJobPosting
from jobtracker.storage import (
    JobObservationRepository,
    JobRepository,
    SearchRunRepository,
    create_db_engine,
    get_database_settings,
    initialize_database,
)


def test_primary_dedupe_reuses_existing_job_for_same_source_id(sqlite_database_url: str) -> None:
    engine = create_db_engine(get_database_settings(sqlite_database_url))
    initialize_database(engine)

    with Session(engine) as session:
        run_repo = SearchRunRepository(session)
        search_run = run_repo.start()
        job_repo = JobRepository(session)
        observation_repo = JobObservationRepository(session)

        first = job_repo.upsert(
            NormalizedJobPosting(
                source="greenhouse",
                source_job_id="job-1",
                source_url="https://boards.greenhouse.io/example/jobs/1",
                canonical_key="example:backend-engineer:austin-tx",
                title="Backend Engineer",
                company=CompanyRecord(normalized_name="example", display_name="Example, Inc."),
                location_text="Austin, TX",
                workplace_type="onsite",
                status="active",
            ),
            seen_at=datetime(2026, 4, 18, 10, 0, tzinfo=timezone.utc),
            source="greenhouse",
            source_job_id="job-1",
        )
        observation_repo.create(
            job_id=first.id,
            search_run_id=search_run.id,
            raw_job=RawJobPosting(
                source="greenhouse",
                source_job_id="job-1",
                source_url="https://boards.greenhouse.io/example/jobs/1",
                title="Backend Engineer",
                company_name="Example, Inc.",
                location_text="Austin, TX",
            ),
        )

        second = job_repo.upsert(
            NormalizedJobPosting(
                source="greenhouse",
                source_job_id="job-1",
                source_url="https://boards.greenhouse.io/example/jobs/1?updated=1",
                canonical_key="example:senior-backend-engineer:austin-tx",
                title="Senior Backend Engineer",
                company=CompanyRecord(normalized_name="example", display_name="Example"),
                location_text="Austin, TX",
                workplace_type="onsite",
                status="active",
            ),
            seen_at=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
            source="greenhouse",
            source_job_id="job-1",
        )
        first_id = first.id
        second_id = second.id
        second_title = second.title
        session.commit()

    assert first_id == second_id
    assert second_title == "Senior Backend Engineer"


def test_secondary_dedupe_merges_same_role_across_sources(sqlite_database_url: str) -> None:
    engine = create_db_engine(get_database_settings(sqlite_database_url))
    initialize_database(engine)

    with Session(engine) as session:
        job_repo = JobRepository(session)

        greenhouse_job = job_repo.upsert(
            NormalizedJobPosting(
                source="greenhouse",
                source_job_id="gh-1",
                source_url="https://boards.greenhouse.io/example/jobs/1",
                canonical_key="example:backend-engineer:remote",
                title="Backend Engineer",
                company=CompanyRecord(normalized_name="example", display_name="Example"),
                location_text="Remote",
                workplace_type="remote",
                status="active",
            ),
            source="greenhouse",
            source_job_id="gh-1",
        )

        lever_job = job_repo.upsert(
            NormalizedJobPosting(
                source="lever",
                source_job_id="lv-1",
                source_url="https://jobs.lever.co/example/lv-1",
                canonical_key="example:backend-engineer:remote",
                title="Backend Engineer",
                company=CompanyRecord(normalized_name="example", display_name="Example Inc"),
                location_text="Remote",
                workplace_type="remote",
                status="active",
            ),
            source="lever",
            source_job_id="lv-1",
        )
        greenhouse_id = greenhouse_job.id
        lever_id = lever_job.id
        best_source_url = greenhouse_job.best_source_url
        session.commit()

    assert greenhouse_id == lever_id
    assert best_source_url == "https://boards.greenhouse.io/example/jobs/1"


def test_secondary_dedupe_does_not_merge_distinct_titles(sqlite_database_url: str) -> None:
    engine = create_db_engine(get_database_settings(sqlite_database_url))
    initialize_database(engine)

    with Session(engine) as session:
        job_repo = JobRepository(session)

        backend_job = job_repo.upsert(
            NormalizedJobPosting(
                source="greenhouse",
                source_job_id="gh-1",
                source_url="https://boards.greenhouse.io/example/jobs/1",
                canonical_key="example:backend-engineer:remote",
                title="Backend Engineer",
                company=CompanyRecord(normalized_name="example", display_name="Example"),
                location_text="Remote",
                workplace_type="remote",
                status="active",
            ),
            source="greenhouse",
            source_job_id="gh-1",
        )

        platform_job = job_repo.upsert(
            NormalizedJobPosting(
                source="lever",
                source_job_id="lv-2",
                source_url="https://jobs.lever.co/example/lv-2",
                canonical_key="example:platform-engineer:remote",
                title="Platform Engineer",
                company=CompanyRecord(normalized_name="example", display_name="Example"),
                location_text="Remote",
                workplace_type="remote",
                status="active",
            ),
            source="lever",
            source_job_id="lv-2",
        )
        backend_id = backend_job.id
        platform_id = platform_job.id
        session.commit()

    assert backend_id != platform_id
