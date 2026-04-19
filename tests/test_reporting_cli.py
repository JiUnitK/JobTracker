from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session
from typer.testing import CliRunner

from jobtracker.cli.app import app
from jobtracker.models import CompanyRecord, NormalizedJobPosting
from jobtracker.storage import JobRepository, SearchRunRepository, create_db_engine, get_database_settings
from jobtracker.storage.migrations import upgrade_database


runner = CliRunner()


def _seed_report_data(sqlite_database_url: str) -> None:
    upgrade_database(sqlite_database_url)
    engine = create_db_engine(get_database_settings(sqlite_database_url))
    with Session(engine) as session:
        search_run = SearchRunRepository(session).start(
            started_at=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc)
        )
        job_repo = JobRepository(session)

        remote_job = job_repo.upsert(
            NormalizedJobPosting(
                source="greenhouse",
                source_job_id="job-1",
                source_url="https://boards.greenhouse.io/example/jobs/1",
                canonical_key="example:backend-engineer:remote",
                title="Backend Engineer",
                company=CompanyRecord(normalized_name="example", display_name="Example"),
                location_text="Remote",
                workplace_type="remote",
                status="active",
            ),
            seen_at=search_run.started_at,
            source="greenhouse",
            source_job_id="job-1",
        )
        remote_job.fit_score = 82
        remote_job.hiring_score = 76
        remote_job.priority_score = 80
        remote_job.score_payload = {"fit_score": 82, "hiring_score": 76, "priority_score": 80}

        austin_job = job_repo.upsert(
            NormalizedJobPosting(
                source="lever",
                source_job_id="job-2",
                source_url="https://jobs.lever.co/example/jobs/2",
                canonical_key="example:platform-engineer:austin-tx",
                title="Platform Engineer",
                company=CompanyRecord(normalized_name="example", display_name="Example"),
                location_text="Austin, TX",
                workplace_type="hybrid",
                status="active",
            ),
            seen_at=search_run.started_at,
            source="lever",
            source_job_id="job-2",
        )
        austin_job.fit_score = 74
        austin_job.hiring_score = 88
        austin_job.priority_score = 79
        austin_job.score_payload = {"fit_score": 74, "hiring_score": 88, "priority_score": 79}

        stale_job = job_repo.upsert(
            NormalizedJobPosting(
                source="ashby",
                source_job_id="job-3",
                source_url="https://jobs.ashbyhq.com/example/jobs/3",
                canonical_key="example:backend-engineer:onsite",
                title="Backend Engineer II",
                company=CompanyRecord(normalized_name="example", display_name="Example"),
                location_text="Austin, TX",
                workplace_type="onsite",
                status="stale",
            ),
            seen_at=datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc),
            source="ashby",
            source_job_id="job-3",
        )
        stale_job.current_status = "stale"
        stale_job.fit_score = 65
        stale_job.hiring_score = 40
        stale_job.priority_score = 56
        stale_job.score_payload = {"fit_score": 65, "hiring_score": 40, "priority_score": 56}

        session.commit()


def test_jobs_list_and_top_commands_apply_filters(sqlite_database_url: str) -> None:
    _seed_report_data(sqlite_database_url)

    list_result = runner.invoke(
        app,
        ["jobs", "list", "--database-url", sqlite_database_url, "--remote-only"],
    )
    top_result = runner.invoke(
        app,
        ["jobs", "top", "--database-url", sqlite_database_url, "--limit", "1"],
    )

    assert list_result.exit_code == 0
    assert "Backend Engineer" in list_result.stdout
    assert "Platform Engineer" not in list_result.stdout
    assert top_result.exit_code == 0
    assert "1. Example | Backend Engineer | Remote | priority=80" in top_result.stdout


def test_jobs_commands_support_status_and_sort_filters(sqlite_database_url: str) -> None:
    _seed_report_data(sqlite_database_url)

    stale_result = runner.invoke(
        app,
        ["jobs", "list", "--database-url", sqlite_database_url, "--status", "stale"],
    )
    fit_sorted_result = runner.invoke(
        app,
        ["jobs", "top", "--database-url", sqlite_database_url, "--sort-by", "fit", "--limit", "1"],
    )

    assert stale_result.exit_code == 0
    assert "Backend Engineer II" in stale_result.stdout
    assert "Backend Engineer | Remote" not in stale_result.stdout
    assert fit_sorted_result.exit_code == 0
    assert "1. Example | Backend Engineer | Remote | priority=80" in fit_sorted_result.stdout


def test_jobs_commands_support_company_drilldown(sqlite_database_url: str) -> None:
    _seed_report_data(sqlite_database_url)

    list_result = runner.invoke(
        app,
        ["jobs", "list", "--database-url", sqlite_database_url, "--company", "Example"],
    )
    top_result = runner.invoke(
        app,
        ["jobs", "top", "--database-url", sqlite_database_url, "--company", "Example", "--limit", "2"],
    )

    assert list_result.exit_code == 0
    assert "Backend Engineer" in list_result.stdout
    assert "Platform Engineer" in list_result.stdout
    assert top_result.exit_code == 0
    assert "1. Example | Backend Engineer | Remote | priority=80" in top_result.stdout


def test_companies_list_shows_rollup_summary(sqlite_database_url: str) -> None:
    _seed_report_data(sqlite_database_url)

    result = runner.invoke(
        app,
        ["companies", "list", "--database-url", sqlite_database_url],
    )

    assert result.exit_code == 0
    assert "Example | active=2 | recent=3" in result.stdout


def test_export_commands_write_csv_and_markdown(
    sqlite_database_url: str,
    scratch_dir: Path,
) -> None:
    _seed_report_data(sqlite_database_url)
    csv_output = scratch_dir / "jobs.csv"
    markdown_output = scratch_dir / "jobs.md"

    csv_result = runner.invoke(
        app,
        [
            "export",
            "csv",
            "--database-url",
            sqlite_database_url,
            "--output",
            str(csv_output),
            "--remote-only",
        ],
    )
    markdown_result = runner.invoke(
        app,
        [
            "export",
            "markdown",
            "--database-url",
            sqlite_database_url,
            "--output",
            str(markdown_output),
            "--limit",
            "1",
        ],
    )

    assert csv_result.exit_code == 0
    assert markdown_result.exit_code == 0
    csv_text = csv_output.read_text(encoding="utf-8")
    markdown_text = markdown_output.read_text(encoding="utf-8")
    assert "Backend Engineer" in csv_text
    assert "Platform Engineer" not in csv_text
    assert "# JobTracker Report" in markdown_text
    assert "| Example | Backend Engineer | Remote | active | 80 |" in markdown_text
