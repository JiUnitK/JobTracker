from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from jobtracker.config.loader import load_app_config
from jobtracker.config.models import AppConfig
from jobtracker.models import CompanyRecord, NormalizedJobPosting, RawJobPosting
from jobtracker.scoring import ScoringService
from jobtracker.storage import (
    JobObservationRepository,
    JobRepository,
    SearchRunRepository,
    create_db_engine,
    get_database_settings,
    initialize_database,
)


def _base_config() -> AppConfig:
    return load_app_config(Path("config"))


def _seed_scoring_job(sqlite_database_url: str) -> tuple[Session, object]:
    engine = create_db_engine(get_database_settings(sqlite_database_url))
    initialize_database(engine)
    session = Session(engine)
    run_repo = SearchRunRepository(session)
    search_run = run_repo.start(
        started_at=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc)
    )
    job_repo = JobRepository(session)
    job = job_repo.upsert(
        NormalizedJobPosting(
            source="greenhouse",
            source_job_id="job-1",
            source_url="https://boards.greenhouse.io/example/jobs/1",
            canonical_key="example:backend-engineer:remote",
            title="Backend Engineer",
            company=CompanyRecord(normalized_name="example", display_name="Example"),
            location_text="Remote",
            workplace_type="remote",
            description_snippet="Build Python distributed systems and APIs.",
            seniority="Senior",
            status="active",
        ),
        seen_at=search_run.started_at,
        source="greenhouse",
        source_job_id="job-1",
    )
    observation_repo = JobObservationRepository(session)
    for idx in range(3):
        observation_repo.create(
            job_id=job.id,
            search_run_id=search_run.id,
            raw_job=RawJobPosting(
                source="greenhouse",
                source_job_id=f"job-1-{idx}",
                source_url="https://boards.greenhouse.io/example/jobs/1",
                title="Backend Engineer",
                company_name="Example",
                location_text="Remote",
                description_snippet="Build Python distributed systems and APIs.",
                posted_at=datetime(2026, 4, 18, 10, 0, tzinfo=timezone.utc),
                raw_payload={"id": f"job-1-{idx}"},
            ),
        )
    session.flush()
    return session, job


def test_scoring_engine_generates_explainable_scores(sqlite_database_url: str) -> None:
    session, job = _seed_scoring_job(sqlite_database_url)
    try:
        config = _base_config()
        result = ScoringService(session, config).score_job(
            job,
            now=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
        )
    finally:
        session.close()

    assert result.fit_score == 85
    assert result.hiring_score == 86
    assert result.priority_score == 85
    assert "title closely matches target roles" in result.payload["fit_reasons"]
    assert "role has been observed across multiple runs" in result.payload["hiring_reasons"]


def test_scoring_weights_change_priority_predictably(sqlite_database_url: str) -> None:
    session, job = _seed_scoring_job(sqlite_database_url)
    try:
        base_config = _base_config()
        base_result = ScoringService(session, base_config).score_job(
            job,
            now=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
        )
        hiring_heavy_config = base_config.model_copy(
            deep=True,
            update={
                "scoring": base_config.scoring.model_copy(
                    deep=True,
                    update={"priority_mix": {"fit_score": 0.1, "hiring_score": 0.9}},
                )
            },
        )
        hiring_heavy_result = ScoringService(session, hiring_heavy_config).score_job(
            job,
            now=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
        )
    finally:
        session.close()

    assert base_result.priority_score == 85
    assert hiring_heavy_result.priority_score == 86
    assert hiring_heavy_result.priority_score > base_result.priority_score


def test_scoring_engine_penalizes_weaker_matches(sqlite_database_url: str) -> None:
    engine = create_db_engine(get_database_settings(sqlite_database_url))
    initialize_database(engine)
    session = Session(engine)
    try:
        run_repo = SearchRunRepository(session)
        search_run = run_repo.start(
            started_at=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc)
        )
        job_repo = JobRepository(session)
        weak_job = job_repo.upsert(
            NormalizedJobPosting(
                source="linkedin",
                source_job_id="job-weak",
                source_url="https://www.linkedin.com/jobs/view/weak",
                canonical_key="example:designer:onsite",
                title="Product Designer",
                company=CompanyRecord(normalized_name="example", display_name="Example"),
                location_text="New York, NY",
                workplace_type="onsite",
                description_snippet="Design product visuals.",
                seniority="Mid",
                status="active",
            ),
            seen_at=search_run.started_at,
            source="linkedin",
            source_job_id="job-weak",
        )
        result = ScoringService(session, _base_config()).score_job(
            weak_job,
            now=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
        )
    finally:
        session.close()

    assert result.fit_score < 40
    assert result.hiring_score < 60
    assert result.priority_score < 50
