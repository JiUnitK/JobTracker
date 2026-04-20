from __future__ import annotations

from pathlib import Path

from jobtracker.config.loader import load_app_config
from jobtracker.job_search.planner import JobSearchOverrides, build_instant_job_search_request


def test_build_instant_job_search_request_uses_config_defaults() -> None:
    app_config = load_app_config(Path("config"))

    request = build_instant_job_search_request(app_config)

    assert request.max_age_days == 7
    assert request.include_unknown_age is False
    assert request.limit == 25
    assert request.queries
    assert any("backend engineer" in query.query for query in request.queries)


def test_build_instant_job_search_request_applies_cli_overrides() -> None:
    app_config = load_app_config(Path("config"))

    request = build_instant_job_search_request(
        app_config,
        JobSearchOverrides(
            query="customer success",
            location="Remote",
            max_age_days=3,
            include_unknown_age=True,
            limit=5,
        ),
    )

    assert request.max_age_days == 3
    assert request.include_unknown_age is True
    assert request.limit == 5
    assert all("customer success" in query.query for query in request.queries)
    assert all(query.location == "Remote" for query in request.queries)

