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


def _profile_request() -> InstantJobSearchRequest:
    return InstantJobSearchRequest(
        queries=[InstantJobSearchQuery(query='"backend engineer" Remote job apply posted')],
        max_age_days=7,
        include_unknown_age=False,
        use_profile_matching=True,
        limit=10,
    )


def _broad_request() -> InstantJobSearchRequest:
    return InstantJobSearchRequest(
        queries=[InstantJobSearchQuery(query='"backend engineer" Remote job apply posted')],
        max_age_days=7,
        include_unknown_age=True,
        source_mode="broad",
        limit=10,
    )


def _broad_profile_request() -> InstantJobSearchRequest:
    return InstantJobSearchRequest(
        queries=[InstantJobSearchQuery(query='"backend engineer" Remote job apply posted')],
        max_age_days=7,
        include_unknown_age=True,
        use_profile_matching=True,
        source_mode="broad",
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
    assert "profile skills: python, distributed systems, apis" not in scored.result.reasons
    assert "remote workplace" in scored.result.reasons
    assert "recent posting" in scored.result.reasons
    assert "ATS source" in scored.result.reasons


def test_score_instant_job_result_uses_profile_matching_when_requested() -> None:
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

    scored = score_instant_job_result(result, _profile_request(), config)

    assert scored.relevant is True
    assert "profile skills: python, distributed systems, apis" in scored.result.reasons


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


def test_score_instant_job_result_ignores_profile_exclusions_by_default() -> None:
    config = load_app_config(Path("config"))
    result = InstantJobSearchResult(
        title="Sales Engineer",
        url="https://boards.greenhouse.io/example/jobs/1",
        snippet="Remote sales engineer role posted 1 day ago",
        age_days=1,
        workplace_type="remote",
    )
    request = InstantJobSearchRequest(
        queries=[InstantJobSearchQuery(query='"sales engineer" Remote job')],
        max_age_days=7,
    )

    scored = score_instant_job_result(result, request, config)

    assert scored.relevant is True
    assert not any("sales engineer" in reason for reason in scored.result.reasons)


def test_score_instant_job_result_uses_profile_exclusions_when_requested() -> None:
    config = load_app_config(Path("config"))
    result = InstantJobSearchResult(
        title="Sales Engineer",
        url="https://boards.greenhouse.io/example/jobs/1",
        snippet="Remote sales engineer role posted 1 day ago",
        age_days=1,
        workplace_type="remote",
    )
    request = InstantJobSearchRequest(
        queries=[InstantJobSearchQuery(query='"sales engineer" Remote job')],
        max_age_days=7,
        use_profile_matching=True,
    )

    scored = score_instant_job_result(result, request, config)

    assert scored.relevant is False
    assert scored.result.reasons == ["excluded keyword: sales engineer"]


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
        url="https://boards.greenhouse.io/example/jobs/123",
        snippet="Python role",
        age_confidence="unknown",
    )

    scored = score_instant_job_result(result, request, config)

    assert scored.relevant is True
    assert "age unknown" in scored.result.reasons


def test_score_instant_job_result_rejects_indeed_search_pages() -> None:
    config = load_app_config(Path("config"))
    result = InstantJobSearchResult(
        title=(
            "Flexible Remote Software Engineer Jobs - Apply Today to Work From Home "
            "in Austin, TX (February 23, 2026)"
        ),
        company="Indeed",
        location="Remote",
        workplace_type="remote",
        url="https://www.indeed.com/q-remote-software-engineer-l-austin-tx-jobs.html",
        age_days=0,
        age_text="today",
        age_confidence="low",
    )

    scored = score_instant_job_result(result, _request(), config)

    assert scored.relevant is False
    assert scored.result.score == 0
    assert scored.result.reasons == ["not a confirmed role posting"]


def test_score_instant_job_result_rejects_linkedin_collection_pages() -> None:
    config = load_app_config(Path("config"))
    result = InstantJobSearchResult(
        title="790 Remote Software jobs in Austin, Texas Metropolitan Area",
        company=None,
        location="Remote",
        workplace_type="remote",
        url="https://www.linkedin.com/jobs/remote-software-jobs-austin-texas-metropolitan-area",
        age_days=4,
        age_confidence="medium",
    )

    scored = score_instant_job_result(result, _request(), config)

    assert scored.relevant is False
    assert scored.result.reasons == ["not a confirmed role posting"]


def test_score_instant_job_result_allows_actual_linkedin_role_pages() -> None:
    config = load_app_config(Path("config"))
    result = InstantJobSearchResult(
        title="Backend Engineer",
        company="Example Health",
        location="Remote",
        workplace_type="remote",
        url="https://www.linkedin.com/jobs/view/1234567890",
        snippet="Python APIs role posted 1 day ago",
        age_days=1,
        age_confidence="medium",
    )

    scored = score_instant_job_result(result, _request(), config)

    assert scored.relevant is True
    assert "job board source" in scored.result.reasons


def test_score_instant_job_result_rejects_builtin_collection_pages() -> None:
    config = load_app_config(Path("config"))
    result = InstantJobSearchResult(
        title="Best Software Engineer Jobs in Austin, TX 2026",
        company="Built In Austin",
        location="hybrid",
        workplace_type="hybrid",
        url="https://www.builtinaustin.com/jobs/dev-engineering",
        age_confidence="unknown",
    )

    scored = score_instant_job_result(result, _request(), config)

    assert scored.relevant is False
    assert scored.result.reasons == ["not a confirmed role posting"]


def test_score_instant_job_result_rejects_dice_search_pages() -> None:
    config = load_app_config(Path("config"))
    result = InstantJobSearchResult(
        title="software engineer jobs in austin, tx",
        company="Dice.com",
        location="hybrid",
        workplace_type="hybrid",
        url="https://www.dice.com/jobs/q-software+engineer-l-austin-tx-jobs",
        age_confidence="unknown",
    )

    scored = score_instant_job_result(result, _request(), config)

    assert scored.relevant is False
    assert scored.result.reasons == ["not a confirmed role posting"]


def test_score_instant_job_result_rejects_dice_keyword_listing_pages() -> None:
    config = load_app_config(Path("config"))
    result = InstantJobSearchResult(
        title="embedded software engineer remote jobs",
        company="Dice.com",
        location="Remote",
        workplace_type="remote",
        url="https://www.dice.com/jobs/q-embedded+software+engineer-l-remote-jobs",
        age_days=5,
        age_confidence="high",
    )

    scored = score_instant_job_result(result, _request(), config)

    assert scored.relevant is False
    assert scored.result.reasons == ["not a confirmed role posting"]


def test_score_instant_job_result_rejects_ihire_listing_pages() -> None:
    config = load_app_config(Path("config"))
    result = InstantJobSearchResult(
        title="Remote & Hybrid Software Developer Jobs in Florida",
        company="iHire",
        location="Remote",
        workplace_type="remote",
        url="https://www.ihire.com/t-software-developer-s-florida-remote-jobs.html",
        age_days=3,
        age_confidence="medium",
    )

    scored = score_instant_job_result(result, _request(), config)

    assert scored.relevant is False
    assert scored.result.reasons == ["not a confirmed role posting"]


def test_score_instant_job_result_rejects_generic_company_career_pages_in_strict_mode() -> None:
    config = load_app_config(Path("config"))
    result = InstantJobSearchResult(
        title="Software Engineer",
        company="Example Health",
        location="Remote",
        workplace_type="remote",
        url="https://example.com/careers/software-engineer",
        age_days=1,
        age_confidence="medium",
    )

    scored = score_instant_job_result(result, _request(), config)

    assert scored.relevant is False
    assert scored.result.reasons == ["not a confirmed role posting"]


def test_score_instant_job_result_allows_collection_pages_in_broad_mode() -> None:
    config = load_app_config(Path("config"))
    result = InstantJobSearchResult(
        title="Best Software Engineer Jobs in Austin, TX 2026",
        company="Built In Austin",
        location="hybrid",
        workplace_type="hybrid",
        url="https://www.builtinaustin.com/jobs/dev-engineering",
        age_confidence="unknown",
    )

    scored = score_instant_job_result(result, _broad_profile_request(), config)

    assert scored.relevant is True
    assert scored.result.score > 0
    assert "partial title match" in scored.result.reasons


def test_score_instant_job_result_allows_actual_ashby_role_page_with_unknown_age() -> None:
    config = load_app_config(Path("config"))
    request = InstantJobSearchRequest(
        queries=[InstantJobSearchQuery(query='"senior software engineer" Austin job')],
        max_age_days=7,
        include_unknown_age=True,
    )
    result = InstantJobSearchResult(
        title="Senior Software Engineer",
        company="liblab",
        location=None,
        workplace_type="unknown",
        url="https://jobs.ashbyhq.com/liblab/fadf2a99-f060-47c0-bffc-123456789abc",
        snippet="Austin, TX role for a senior engineer.",
        age_confidence="unknown",
    )

    scored = score_instant_job_result(result, request, config)

    assert scored.relevant is True
    assert "ATS source" in scored.result.reasons
