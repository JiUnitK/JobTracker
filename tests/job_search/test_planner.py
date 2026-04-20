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
    assert any("remote hybrid on-site" in query.query for query in request.queries)
    assert any("site:greenhouse.io" in query.query for query in request.queries)
    assert all(
        any(term in query.query.lower() for term in ["job", "apply", "careers", "posted"])
        for query in request.queries
    )


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


def test_build_instant_job_search_request_prefers_explicit_configured_queries() -> None:
    app_config = load_app_config(Path("config"))
    app_config.job_search.settings.queries = ["customer success", "medical billing"]
    app_config.search_terms.include = ["backend engineer"]

    request = build_instant_job_search_request(
        app_config,
        JobSearchOverrides(location="Remote", limit=20),
    )

    rendered = [query.query for query in request.queries]
    assert any("customer success" in query for query in rendered)
    assert any("medical billing" in query for query in rendered)
    assert not any("backend engineer" in query for query in rendered)


def test_build_instant_job_search_request_appends_job_intent_to_plain_templates() -> None:
    app_config = load_app_config(Path("config"))
    app_config.job_search.settings.query_templates = ['"{query}" "{location}"']

    request = build_instant_job_search_request(
        app_config,
        JobSearchOverrides(query="customer success", location="Remote", limit=5),
    )

    assert request.queries
    assert all("job apply careers posted" in query.query for query in request.queries)


def test_build_instant_job_search_request_supports_non_tech_searches() -> None:
    app_config = load_app_config(Path("config"))
    app_config.job_search.settings.queries = ["office manager"]
    app_config.search_terms.locations = ["Chicago, IL"]
    app_config.search_terms.workplace_types = ["onsite"]

    request = build_instant_job_search_request(app_config, JobSearchOverrides(limit=10))

    assert any("office manager" in query.query for query in request.queries)
    assert all(query.location == "Chicago, IL" for query in request.queries)
    assert all(query.workplace_types == ["onsite"] for query in request.queries)
    assert any("on-site" in query.query for query in request.queries)
