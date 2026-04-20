from __future__ import annotations

from typer.testing import CliRunner

from jobtracker.cli import job_search as cli_job_search
from jobtracker.cli.app import app
from jobtracker.job_search.models import (
    InstantJobSearchQuery,
    InstantJobSearchResult,
    InstantJobSearchRunSummary,
)


runner = CliRunner()


class FakeRunner:
    def run(self, app_config, overrides):
        return InstantJobSearchRunSummary(
            requested_queries=[InstantJobSearchQuery(query="customer success", location="Remote")],
            max_age_days=overrides.max_age_days or 7,
            include_unknown_age=bool(overrides.include_unknown_age),
            results=[
                InstantJobSearchResult(
                    title="Customer Success Specialist",
                    company="Example Health",
                    location="Remote",
                    url="https://example.com/jobs/1",
                    age_days=2,
                    age_text="2 days old",
                    score=86,
                    reasons=["title match", "remote"],
                )
            ],
            total_raw_results=1,
        )


def test_search_jobs_command_outputs_human_shortlist(monkeypatch) -> None:
    monkeypatch.setattr(cli_job_search, "InstantJobSearchRunner", lambda: FakeRunner())

    result = runner.invoke(
        app,
        ["search", "jobs", "--query", "customer success", "--location", "Remote", "--days", "7"],
    )

    assert result.exit_code == 0
    assert "Instant Job Search" in result.stdout
    assert "Customer Success Specialist" in result.stdout
    assert "Why: title match, remote" in result.stdout


def test_search_jobs_command_outputs_json(monkeypatch) -> None:
    monkeypatch.setattr(cli_job_search, "InstantJobSearchRunner", lambda: FakeRunner())

    result = runner.invoke(app, ["search", "jobs", "--json"])

    assert result.exit_code == 0
    assert '"results"' in result.stdout
    assert '"Customer Success Specialist"' in result.stdout


def test_search_jobs_command_reports_adapter_errors(monkeypatch) -> None:
    class ErrorRunner:
        def run(self, app_config, overrides):
            raise ValueError("BRAVE_SEARCH_API_KEY is required for brave_search")

    monkeypatch.setattr(cli_job_search, "InstantJobSearchRunner", lambda: ErrorRunner())

    result = runner.invoke(app, ["search", "jobs"])

    assert result.exit_code != 0
    assert "BRAVE_SEARCH_API_KEY is required for brave_search" in (
        result.stdout + result.stderr
    )
