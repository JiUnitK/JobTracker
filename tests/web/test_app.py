from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from jobtracker.config.models import AppConfig
from jobtracker.job_search.models import (
    InstantJobSearchQuery,
    InstantJobSearchResult,
    InstantJobSearchRunSummary,
)
from jobtracker.job_search.planner import JobSearchOverrides
from jobtracker.web.app import build_web_config_summary, create_app


class FakeRunner:
    def run(self, app_config: AppConfig, overrides: JobSearchOverrides):
        return InstantJobSearchRunSummary(
            requested_queries=[InstantJobSearchQuery(query=overrides.query or "backend engineer")],
            max_age_days=overrides.max_age_days or 7,
            include_unknown_age=bool(overrides.include_unknown_age),
            include_low_fit=bool(overrides.include_low_fit),
            total_raw_results=1,
            results=[
                InstantJobSearchResult(
                    title="Backend Engineer",
                    company="Example Health",
                    location=overrides.location or "Remote",
                    workplace_type="remote",
                    url="https://example.com/jobs/1",
                    age_text="2 days ago",
                    age_days=2,
                    score=91,
                    reasons=["strong title match", "recent posting"],
                )
            ],
        )


class ErrorRunner:
    def run(self, app_config: AppConfig, overrides: JobSearchOverrides):
        raise ValueError("BRAVE_SEARCH_API_KEY is required for brave_search")


def test_config_summary_uses_default_config() -> None:
    client = TestClient(create_app(runner_factory=FakeRunner))

    response = client.get("/api/config/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["max_age_days"] == 7
    assert "brave_search" in payload["enabled_instant_search_sources"]
    assert payload["default_query"]


def test_search_jobs_api_returns_structured_summary() -> None:
    client = TestClient(create_app(runner_factory=FakeRunner))

    response = client.post(
        "/api/search/jobs",
        json={
            "query": "backend engineer",
            "location": "Remote",
            "days": 7,
            "limit": 5,
            "include_unknown_age": True,
            "include_low_fit": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["max_age_days"] == 7
    assert payload["include_unknown_age"] is True
    assert payload["include_low_fit"] is True
    assert payload["results"][0]["title"] == "Backend Engineer"
    assert payload["results"][0]["reasons"] == ["strong title match", "recent posting"]


def test_search_jobs_api_reports_runner_errors() -> None:
    client = TestClient(create_app(runner_factory=ErrorRunner))

    response = client.post("/api/search/jobs", json={"query": "backend engineer"})

    assert response.status_code == 400
    assert response.json()["detail"] == "BRAVE_SEARCH_API_KEY is required for brave_search"


def test_static_frontend_and_assets_are_served() -> None:
    client = TestClient(create_app(runner_factory=FakeRunner))

    index = client.get("/")
    script = client.get("/static/app.js")
    styles = client.get("/static/styles.css")

    assert index.status_code == 200
    assert "JobTracker" in index.text
    assert 'id="searchForm"' in index.text
    assert "Role Link" in index.text
    assert "Low fit" in index.text
    assert script.status_code == 200
    assert "runSearch" in script.text
    assert "Open role" in script.text
    assert "url-preview" in script.text
    assert "include_low_fit" in script.text
    assert styles.status_code == 200
    assert ".results-wrap" in styles.text
    assert ".url-preview" in styles.text


def test_build_web_config_summary_prefers_explicit_instant_query() -> None:
    from jobtracker.config.loader import load_app_config

    app_config = load_app_config(Path("config"))
    app_config.job_search.settings.queries = ["customer success"]

    summary = build_web_config_summary(app_config)

    assert summary.default_query == "customer success"
