from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from jobtracker.job_search import (
    InstantJobSearchQuery,
    InstantJobSearchRequest,
    InstantJobSearchResult,
    InstantJobSearchRunSummary,
    RawInstantSearchResult,
)


def test_instant_job_search_request_requires_queries() -> None:
    with pytest.raises(ValidationError, match="At least one"):
        InstantJobSearchRequest(queries=[])


def test_instant_job_search_request_cleans_query_and_location() -> None:
    request = InstantJobSearchRequest(
        queries=[
            InstantJobSearchQuery(
                query=" customer success ",
                location=" Remote ",
                workplace_types=["remote"],
            )
        ],
        max_age_days=14,
        include_unknown_age=True,
        use_profile_matching=True,
        source_mode="broad",
        limit=10,
    )

    assert request.queries[0].query == "customer success"
    assert request.queries[0].location == "Remote"
    assert request.max_age_days == 14
    assert request.include_unknown_age is True
    assert request.use_profile_matching is True
    assert request.source_mode == "broad"
    assert request.limit == 10


def test_raw_instant_search_result_holds_provider_payload() -> None:
    result = RawInstantSearchResult(
        source_id="brave-1",
        title="Customer Success Specialist",
        url="https://example.com/jobs/1",
        snippet="Posted 2 days ago",
        age_text="2 days ago",
        raw_payload={"extra": "value"},
    )

    assert result.provider == "brave_search"
    assert str(result.url) == "https://example.com/jobs/1"
    assert result.raw_payload == {"extra": "value"}


def test_instant_job_search_result_is_structured_for_cli_and_gui_output() -> None:
    result = InstantJobSearchResult(
        title="Customer Success Specialist",
        company="Example Health",
        location="Remote",
        workplace_type="remote",
        url="https://example.com/jobs/1",
        posted_at=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        age_days=1,
        age_text="1 day old",
        age_confidence="high",
        score=86,
        reasons=[" title match ", "", "remote"],
        source_id="brave-1",
    )

    assert result.title == "Customer Success Specialist"
    assert result.company == "Example Health"
    assert result.location == "Remote"
    assert result.age_days == 1
    assert result.age_confidence == "high"
    assert result.score == 86
    assert result.reasons == ["title match", "remote"]


def test_instant_job_search_result_clamps_score() -> None:
    low = InstantJobSearchResult(
        title="Role",
        url="https://example.com/low",
        score=-10,
    )
    high = InstantJobSearchResult(
        title="Role",
        url="https://example.com/high",
        score=125,
    )

    assert low.score == 0
    assert high.score == 100


def test_instant_job_search_result_rejects_negative_age() -> None:
    with pytest.raises(ValidationError, match="age_days"):
        InstantJobSearchResult(
            title="Role",
            url="https://example.com/role",
            age_days=-1,
        )


def test_instant_job_search_run_summary_is_json_ready() -> None:
    query = InstantJobSearchQuery(query="customer success", location="Remote")
    result = InstantJobSearchResult(
        title="Customer Success Specialist",
        company="Example Health",
        location="Remote",
        url="https://example.com/jobs/1",
        score=86,
        reasons=["title match"],
    )
    summary = InstantJobSearchRunSummary(
        requested_queries=[query],
        results=[result],
        total_raw_results=3,
        skipped_for_age=1,
        skipped_for_relevance=1,
        use_profile_matching=True,
        source_mode="broad",
    )

    dumped = summary.model_dump(mode="json")

    assert dumped["requested_queries"][0]["query"] == "customer success"
    assert dumped["results"][0]["title"] == "Customer Success Specialist"
    assert dumped["total_raw_results"] == 3
    assert dumped["use_profile_matching"] is True
    assert dumped["source_mode"] == "broad"
