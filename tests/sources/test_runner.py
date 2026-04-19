from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobtracker.config.loader import load_app_config
from jobtracker.job_tracking.normalize import normalize_raw_job
from jobtracker.job_tracking.sources.base import SourceAdapter
from jobtracker.job_tracking.sources.ashby import AshbyAdapter
from jobtracker.job_tracking.sources.greenhouse import GreenhouseAdapter
from jobtracker.job_tracking.sources.lever import LeverAdapter
from jobtracker.job_tracking.sources.registry import SourceRegistry
from jobtracker.job_tracking.sources.runner import RunCoordinator
from jobtracker.storage import JobObservationORM, JobORM, SearchRunORM, SourceORM, create_db_engine, get_database_settings


class FakeGreenhouseAdapter(SourceAdapter):
    source_name = "greenhouse"

    def __init__(self, jobs):
        self.jobs = jobs

    def collect(self, source, query):
        return list(self.jobs)


class FailingAdapter(SourceAdapter):
    source_name = "broken"

    def collect(self, source, query):
        raise RuntimeError("boom")


def _write_config(config_dir: Path, sources_content: str) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "search_terms.yaml").write_text(
        Path("config/search_terms.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (config_dir / "scoring.yaml").write_text(
        Path("config/scoring.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (config_dir / "profile.yaml").write_text(
        Path("config/profile.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (config_dir / "sources.yaml").write_text(sources_content, encoding="utf-8")
    return config_dir


def test_run_coordinator_persists_jobs_from_mocked_adapter(
    scratch_dir: Path,
    sqlite_database_url: str,
) -> None:
    sources_yaml = """\
defaults:
  timeout_seconds: 20
  max_results_per_query: 100
sources:
  - name: greenhouse
    type: ats
    enabled: true
    reliability_tier: tier1
    base_url: https://boards.greenhouse.io/
    params:
      board_tokens:
        - exampleco
"""
    config_dir = _write_config(scratch_dir / "config", sources_yaml)
    app_config = load_app_config(config_dir)

    from jobtracker.models import RawJobPosting

    registry = SourceRegistry()
    registry.register(
        FakeGreenhouseAdapter(
            [
                RawJobPosting(
                    source="greenhouse",
                    source_job_id="job-1",
                    source_url="https://boards.greenhouse.io/exampleco/jobs/1",
                    title="Backend Engineer",
                    company_name="Exampleco",
                    location_text="Austin, TX",
                    workplace_type="hybrid",
                    description_snippet="Python platform role",
                    raw_payload={"id": "job-1"},
                )
            ]
        )
    )

    summary = RunCoordinator(registry=registry).run(app_config, sqlite_database_url)

    assert summary.status == "success"
    assert summary.total_raw_jobs == 1
    assert summary.total_persisted_jobs == 1
    assert summary.total_observations == 1

    engine = create_db_engine(get_database_settings(sqlite_database_url))
    with Session(engine) as session:
        jobs = list(session.scalars(select(JobORM)))
        observations = list(session.scalars(select(JobObservationORM)))
        runs = list(session.scalars(select(SearchRunORM)))
        sources = list(session.scalars(select(SourceORM)))

    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].fit_score is not None
    assert jobs[0].hiring_score is not None
    assert jobs[0].priority_score is not None
    assert jobs[0].score_payload["fit_score"] == jobs[0].fit_score
    assert len(observations) == 1
    assert runs[0].status == "success"
    assert sources[0].last_success_at is not None


def test_run_coordinator_reports_partial_success_for_failing_source(
    scratch_dir: Path,
    sqlite_database_url: str,
) -> None:
    sources_yaml = """\
defaults:
  timeout_seconds: 20
  max_results_per_query: 100
sources:
  - name: greenhouse
    type: ats
    enabled: true
    reliability_tier: tier1
    base_url: https://boards.greenhouse.io/
    params:
      board_tokens:
        - exampleco
  - name: broken
    type: other
    enabled: true
    reliability_tier: tier2
"""
    config_dir = _write_config(scratch_dir / "config", sources_yaml)
    app_config = load_app_config(config_dir)

    from jobtracker.models import RawJobPosting

    registry = SourceRegistry()
    registry.register(
        FakeGreenhouseAdapter(
            [
                RawJobPosting(
                    source="greenhouse",
                    source_job_id="job-1",
                    source_url="https://boards.greenhouse.io/exampleco/jobs/1",
                    title="Backend Engineer",
                    company_name="Exampleco",
                    location_text="Austin, TX",
                    workplace_type="hybrid",
                    description_snippet="Python platform role",
                    raw_payload={"id": "job-1"},
                )
            ]
        )
    )
    registry.register(FailingAdapter())

    summary = RunCoordinator(registry=registry).run(app_config, sqlite_database_url)

    assert summary.status == "partial_success"
    assert summary.source_summaries["greenhouse"]["raw_jobs"] == 1
    assert summary.source_summaries["broken"]["errors"] == ["RuntimeError: boom"]

    engine = create_db_engine(get_database_settings(sqlite_database_url))
    with Session(engine) as session:
        sources = {source.name: source for source in session.scalars(select(SourceORM))}
        run = session.scalar(select(SearchRunORM))

    assert sources["greenhouse"].last_success_at is not None
    assert sources["broken"].last_error_at is not None
    assert run is not None
    assert run.status == "partial_success"


def test_real_adapters_run_end_to_end_across_three_structured_sources(
    scratch_dir: Path,
    sqlite_database_url: str,
) -> None:
    sources_yaml = """\
defaults:
  timeout_seconds: 20
  max_results_per_query: 100
sources:
  - name: greenhouse
    type: ats
    enabled: true
    reliability_tier: tier1
    base_url: https://boards.greenhouse.io/
    params:
      board_tokens:
        - exampleco
  - name: lever
    type: ats
    enabled: true
    reliability_tier: tier1
    base_url: https://jobs.lever.co/
    params:
      account_names:
        - exampleco
  - name: ashby
    type: ats
    enabled: true
    reliability_tier: tier1
    base_url: https://jobs.ashbyhq.com/
    params:
      job_board_names:
        - ExampleCo
"""
    config_dir = _write_config(scratch_dir / "config", sources_yaml)
    app_config = load_app_config(config_dir)

    import json

    greenhouse_payload = json.loads(
        Path("tests/fixtures/greenhouse_board.json").read_text(encoding="utf-8")
    )
    lever_payload = json.loads(
        Path("tests/fixtures/lever_postings.json").read_text(encoding="utf-8")
    )
    ashby_payload = json.loads(
        Path("tests/fixtures/ashby_jobs.json").read_text(encoding="utf-8")
    )

    registry = SourceRegistry()
    registry.register(GreenhouseAdapter(fetch_json=lambda _: greenhouse_payload))
    registry.register(LeverAdapter(fetch_json=lambda _: lever_payload))
    registry.register(AshbyAdapter(fetch_json=lambda _: ashby_payload))

    summary = RunCoordinator(registry=registry).run(app_config, sqlite_database_url)

    assert summary.status == "success"
    assert summary.total_raw_jobs == 3
    assert summary.total_observations == 3
    assert set(summary.source_summaries) == {"greenhouse", "lever", "ashby"}

    engine = create_db_engine(get_database_settings(sqlite_database_url))
    with Session(engine) as session:
        jobs = list(session.scalars(select(JobORM).order_by(JobORM.id)))
        sources = {source.name: source for source in session.scalars(select(SourceORM))}

    assert len(jobs) == 3
    assert all(source.last_success_at is not None for source in sources.values())
    normalized_keys = {job.canonical_key for job in jobs}
    assert len(normalized_keys) == 3


def test_repeated_runs_update_seen_timestamps_and_infer_statuses(
    scratch_dir: Path,
    sqlite_database_url: str,
) -> None:
    sources_yaml = """\
defaults:
  timeout_seconds: 20
  max_results_per_query: 100
  stale_after_runs: 1
  closed_after_runs: 2
  recent_activity_days: 30
sources:
  - name: greenhouse
    type: ats
    enabled: true
    reliability_tier: tier1
    base_url: https://boards.greenhouse.io/
    params:
      board_tokens:
        - exampleco
"""
    config_dir = _write_config(scratch_dir / "config", sources_yaml)
    app_config = load_app_config(config_dir)

    from jobtracker.models import RawJobPosting

    first_registry = SourceRegistry()
    first_registry.register(
        FakeGreenhouseAdapter(
            [
                RawJobPosting(
                    source="greenhouse",
                    source_job_id="job-1",
                    source_url="https://boards.greenhouse.io/exampleco/jobs/1",
                    title="Backend Engineer",
                    company_name="Exampleco",
                    location_text="Austin, TX",
                    workplace_type="hybrid",
                    description_snippet="Python platform role",
                    posted_at=datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc),
                    raw_payload={"id": "job-1"},
                )
            ]
        )
    )
    second_registry = SourceRegistry()
    second_registry.register(FakeGreenhouseAdapter([]))
    third_registry = SourceRegistry()
    third_registry.register(FakeGreenhouseAdapter([]))

    first_summary = RunCoordinator(registry=first_registry).run(
        app_config,
        sqlite_database_url,
        run_started_at=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
    )
    second_summary = RunCoordinator(registry=second_registry).run(
        app_config,
        sqlite_database_url,
        run_started_at=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
    )
    third_summary = RunCoordinator(registry=third_registry).run(
        app_config,
        sqlite_database_url,
        run_started_at=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
    )

    engine = create_db_engine(get_database_settings(sqlite_database_url))
    with Session(engine) as session:
        job = session.scalar(select(JobORM))
        run = session.scalar(select(SearchRunORM).order_by(SearchRunORM.id.desc()))

    assert first_summary.status_counts["active"] == 1
    assert second_summary.status_counts["stale"] == 1
    assert third_summary.status_counts["closed"] == 1
    assert job is not None
    assert job.first_seen_at == datetime(2026, 4, 19, 10, 0)
    assert job.last_seen_at == datetime(2026, 4, 19, 10, 0)
    assert job.current_status == "closed"
    assert run is not None
    assert run.summary_json["status_counts"]["closed"] == 1


def test_company_rollups_summarize_recent_and_active_jobs(
    scratch_dir: Path,
    sqlite_database_url: str,
) -> None:
    sources_yaml = """\
defaults:
  timeout_seconds: 20
  max_results_per_query: 100
  stale_after_runs: 2
  closed_after_runs: 4
  recent_activity_days: 7
sources:
  - name: greenhouse
    type: ats
    enabled: true
    reliability_tier: tier1
    base_url: https://boards.greenhouse.io/
    params:
      board_tokens:
        - exampleco
"""
    config_dir = _write_config(scratch_dir / "config", sources_yaml)
    app_config = load_app_config(config_dir)

    from jobtracker.models import RawJobPosting

    registry = SourceRegistry()
    registry.register(
        FakeGreenhouseAdapter(
            [
                RawJobPosting(
                    source="greenhouse",
                    source_job_id="job-1",
                    source_url="https://boards.greenhouse.io/exampleco/jobs/1",
                    title="Backend Engineer",
                    company_name="Exampleco",
                    location_text="Austin, TX",
                    workplace_type="hybrid",
                    description_snippet="Python platform role",
                    raw_payload={"id": "job-1"},
                ),
                RawJobPosting(
                    source="greenhouse",
                    source_job_id="job-2",
                    source_url="https://boards.greenhouse.io/exampleco/jobs/2",
                    title="Platform Engineer",
                    company_name="Exampleco",
                    location_text="Remote",
                    workplace_type="remote",
                    description_snippet="Distributed systems role",
                    raw_payload={"id": "job-2"},
                ),
            ]
        )
    )

    summary = RunCoordinator(registry=registry).run(
        app_config,
        sqlite_database_url,
        run_started_at=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
    )

    assert len(summary.company_rollups) == 1
    rollup = summary.company_rollups[0]
    assert rollup["display_name"] == "Exampleco"
    assert rollup["active_relevant_job_count"] == 2
    assert rollup["recent_relevant_job_count"] == 2
    assert rollup["last_relevant_opening_seen_at"] == datetime(2026, 4, 19, 10, 0)
