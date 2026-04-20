from __future__ import annotations

from pathlib import Path

from jobtracker.config.loader import load_app_config
from jobtracker.job_search.models import (
    InstantJobSearchQuery,
    InstantJobSearchRequest,
    InstantJobSearchResult,
)
from jobtracker.job_search.scoring import score_instant_job_result


def _request() -> InstantJobSearchRequest:
    return InstantJobSearchRequest(
        queries=[InstantJobSearchQuery(query='"backend engineer" Remote job apply posted')],
        max_age_days=7,
        include_unknown_age=False,
        limit=10,
    )


def test_score_instant_job_result_uses_explainable_relevance_signals() -> None:
    config = load_app_config(Path("config"))
    result = InstantJobSearchResult(
        title="Senior Backend Engineer",
        company="Example Health",
        location="Remote",
        workplace_type="remote",
        url="https://boards.greenhouse.io/example/jobs/123",
        snippet="Python APIs distributed systems role. Posted 2 days ago. Apply now.",
        age_days=2,
        age_confidence="medium",
    )

    scored = score_instant_job_result(result, _request(), config)

    assert scored.relevant is True
    assert scored.result.score >= 80
    assert "strong title match" in scored.result.reasons
    assert "matched skills: python, distributed systems, apis" in scored.result.reasons
    assert "remote workplace" in scored.result.reasons
    assert "recent posting" in scored.result.reasons
    assert "ATS source" in scored.result.reasons


def test_score_instant_job_result_rejects_excluded_keywords() -> None:
    config = load_app_config(Path("config"))
    result = InstantJobSearchResult(
        title="Backend Engineer Internship",
        url="https://example.com/jobs/1",
        snippet="Remote internship posted 1 day ago",
        age_days=1,
    )

    scored = score_instant_job_result(result, _request(), config)

    assert scored.relevant is False
    assert scored.result.score == 0
    assert scored.result.reasons == ["excluded keyword: internship"]


def test_score_instant_job_result_keeps_unknown_age_reason_when_included() -> None:
    config = load_app_config(Path("config"))
    request = InstantJobSearchRequest(
        queries=[InstantJobSearchQuery(query='"backend engineer" Remote job')],
        max_age_days=7,
        include_unknown_age=True,
    )
    result = InstantJobSearchResult(
        title="Backend Engineer",
        location="Remote",
        workplace_type="remote",
        url="https://example.com/jobs/backend-engineer",
        snippet="Python role",
        age_confidence="unknown",
    )

    scored = score_instant_job_result(result, request, config)

    assert scored.relevant is True
    assert "age unknown" in scored.result.reasons

