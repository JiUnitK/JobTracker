from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jobtracker.config.loader import load_app_config
from jobtracker.config.models import InstantSearchSourceDefinition
from jobtracker.job_search.base import InstantJobSearchAdapter
from jobtracker.job_search.models import InstantJobSearchQuery, RawInstantSearchResult
from jobtracker.job_search.planner import JobSearchOverrides
from jobtracker.job_search.registry import InstantJobSearchRegistry
from jobtracker.job_search.reporting import format_instant_job_search_summary
from jobtracker.job_search.runner import InstantJobSearchRunner


class FixtureAdapter(InstantJobSearchAdapter):
    source_name = "brave_search"

    def search(
        self,
        source: InstantSearchSourceDefinition,
        query: InstantJobSearchQuery,
    ) -> list[RawInstantSearchResult]:
        return [
            RawInstantSearchResult(
                source_id="fresh",
                title="Backend Engineer - Example Health",
                url="https://boards.greenhouse.io/examplehealth/jobs/123",
                snippet="Remote Python role posted 2 days ago",
                age_text="2 days ago",
            ),
            RawInstantSearchResult(
                source_id="old",
                title="Backend Engineer - Old Co",
                url="https://boards.greenhouse.io/oldco/jobs/123",
                snippet="Remote Python role posted 4 weeks ago",
                age_text="4 weeks ago",
            ),
            RawInstantSearchResult(
                source_id="excluded",
                title="Backend Engineer Internship",
                url="https://boards.greenhouse.io/examplehealth/jobs/456",
                snippet="Remote Python internship posted 1 day ago",
                age_text="1 day ago",
            ),
        ]


class UnknownAgeAdapter(InstantJobSearchAdapter):
    source_name = "brave_search"

    def search(
        self,
        source: InstantSearchSourceDefinition,
        query: InstantJobSearchQuery,
    ) -> list[RawInstantSearchResult]:
        return [
            RawInstantSearchResult(
                source_id="unknown-age",
                title="Backend Engineer - Mystery Co",
                url="https://boards.greenhouse.io/mysteryco/jobs/123",
                snippet="Remote Python role",
            )
        ]


class LowScoreAdapter(InstantJobSearchAdapter):
    source_name = "brave_search"

    def search(
        self,
        source: InstantSearchSourceDefinition,
        query: InstantJobSearchQuery,
    ) -> list[RawInstantSearchResult]:
        return [
            RawInstantSearchResult(
                source_id="low-score",
                title="Community Events Coordinator - Example Health",
                url="https://boards.greenhouse.io/examplehealth/jobs/789",
                snippet="Community programming role.",
            )
        ]


def test_runner_returns_ranked_structured_results_without_database_writes() -> None:
    app_config = load_app_config(Path("config"))
    registry = InstantJobSearchRegistry()
    registry.register(FixtureAdapter())

    summary = InstantJobSearchRunner(registry).run(
        app_config,
        JobSearchOverrides(query="backend engineer", location="Remote", max_age_days=7, limit=3),
        now=datetime(2026, 4, 20, tzinfo=timezone.utc),
    )

    assert summary.total_raw_results >= 3
    assert summary.skipped_for_age >= 1
    assert summary.skipped_for_relevance >= 1
    assert len(summary.results) == 1
    assert summary.results[0].title == "Backend Engineer"
    assert summary.results[0].company == "Example Health"
    assert summary.results[0].score > 0


def test_runner_excludes_unknown_age_by_default() -> None:
    app_config = load_app_config(Path("config"))
    registry = InstantJobSearchRegistry()
    registry.register(UnknownAgeAdapter())

    summary = InstantJobSearchRunner(registry).run(
        app_config,
        JobSearchOverrides(query="backend engineer", location="Remote", max_age_days=7),
        now=datetime(2026, 4, 20, tzinfo=timezone.utc),
    )

    assert summary.total_raw_results >= 1
    assert summary.skipped_for_age >= 1
    assert summary.results == []


def test_runner_includes_unknown_age_when_requested() -> None:
    app_config = load_app_config(Path("config"))
    registry = InstantJobSearchRegistry()
    registry.register(UnknownAgeAdapter())

    summary = InstantJobSearchRunner(registry).run(
        app_config,
        JobSearchOverrides(
            query="backend engineer",
            location="Remote",
            max_age_days=7,
            include_unknown_age=True,
        ),
        now=datetime(2026, 4, 20, tzinfo=timezone.utc),
    )

    assert summary.skipped_for_age == 0
    assert len(summary.results) == 1
    assert summary.results[0].age_confidence == "unknown"


def test_runner_excludes_low_score_results_by_default() -> None:
    app_config = load_app_config(Path("config"))
    registry = InstantJobSearchRegistry()
    registry.register(LowScoreAdapter())

    summary = InstantJobSearchRunner(registry).run(
        app_config,
        JobSearchOverrides(
            query="backend engineer",
            location="Remote",
            max_age_days=7,
            include_unknown_age=True,
        ),
        now=datetime(2026, 4, 20, tzinfo=timezone.utc),
    )

    assert summary.skipped_for_relevance >= 1
    assert summary.results == []


def test_runner_always_excludes_low_score_results() -> None:
    app_config = load_app_config(Path("config"))
    registry = InstantJobSearchRegistry()
    registry.register(LowScoreAdapter())

    summary = InstantJobSearchRunner(registry).run(
        app_config,
        JobSearchOverrides(
            query="backend engineer",
            location="Remote",
            max_age_days=7,
            include_unknown_age=True,
            use_profile_matching=True,
        ),
        now=datetime(2026, 4, 20, tzinfo=timezone.utc),
    )

    assert summary.use_profile_matching is True
    assert summary.skipped_for_relevance >= 1
    assert summary.results == []


def test_human_summary_includes_freshness_and_reasons() -> None:
    app_config = load_app_config(Path("config"))
    registry = InstantJobSearchRegistry()
    registry.register(FixtureAdapter())
    summary = InstantJobSearchRunner(registry).run(
        app_config,
        JobSearchOverrides(query="backend engineer", location="Remote", max_age_days=7, limit=1),
    )

    output = format_instant_job_search_summary(summary)

    assert "Instant Job Search" in output
    assert "Max age: 7 days" in output
    assert "Backend Engineer" in output
    assert "Why:" in output


def test_human_summary_is_transparent_about_unknown_age() -> None:
    app_config = load_app_config(Path("config"))
    registry = InstantJobSearchRegistry()
    registry.register(UnknownAgeAdapter())
    summary = InstantJobSearchRunner(registry).run(
        app_config,
        JobSearchOverrides(
            query="backend engineer",
            location="Remote",
            max_age_days=7,
            include_unknown_age=True,
        ),
    )

    output = format_instant_job_search_summary(summary)

    assert "age unknown" in output
