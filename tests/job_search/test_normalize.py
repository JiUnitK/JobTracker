from __future__ import annotations

from datetime import datetime, timezone

from jobtracker.job_search.models import RawInstantSearchResult
from jobtracker.job_search.normalize import classify_age, normalize_instant_search_result


NOW = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)


def test_classify_age_uses_published_at_as_high_confidence() -> None:
    age_days, age_text, confidence = classify_age(
        "",
        datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        now=NOW,
    )

    assert age_days == 1
    assert age_text == "1 day old"
    assert confidence == "high"


def test_classify_age_parses_relative_hours_and_days() -> None:
    assert classify_age("Posted 12 hours ago", None, now=NOW) == (
        0,
        "12 hours ago",
        "medium",
    )
    assert classify_age("Posted 3 days ago", None, now=NOW) == (
        3,
        "3 days ago",
        "medium",
    )


def test_classify_age_marks_plus_relative_age_low_confidence() -> None:
    assert classify_age("Posted 30+ days ago", None, now=NOW) == (
        30,
        "30+ days ago",
        "low",
    )


def test_classify_age_parses_explicit_dates_from_text() -> None:
    assert classify_age("Posted Apr 18, 2026", None, now=NOW) == (
        2,
        "2026-04-18",
        "medium",
    )
    assert classify_age("Posted 04/17/2026", None, now=NOW) == (
        3,
        "2026-04-17",
        "medium",
    )
    assert classify_age("Posted 2026-04-16", None, now=NOW) == (
        4,
        "2026-04-16",
        "medium",
    )


def test_classify_age_parses_dates_from_url_when_text_is_silent() -> None:
    assert classify_age(
        "Customer Success Specialist",
        None,
        url="https://example.com/jobs/role?posted_at=2026-04-18",
        now=NOW,
    ) == (2, "2026-04-18", "low")
    assert classify_age(
        "Customer Success Specialist",
        None,
        url="https://example.com/jobs/2026/04/18/role",
        now=NOW,
    ) == (2, "2026-04-18", "low")


def test_classify_age_returns_unknown_when_no_signal_exists() -> None:
    assert classify_age("Customer Success Specialist", None, now=NOW) == (
        None,
        None,
        "unknown",
    )


def test_normalize_instant_search_result_uses_url_age_signal() -> None:
    result = normalize_instant_search_result(
        RawInstantSearchResult(
            source_id="url-date",
            title="Customer Success Specialist - Example Health",
            url="https://example.com/jobs/role?posted=20260418",
            snippet="Remote role",
        ),
        now=NOW,
    )

    assert result.age_days == 2
    assert result.age_text == "2026-04-18"
    assert result.age_confidence == "low"
