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
                url="https://example.com/jobs/fresh",
                snippet="Remote Python role posted 2 days ago",
                age_text="2 days ago",
            ),
            RawInstantSearchResult(
                source_id="old",
                title="Backend Engineer - Old Co",
                url="https://example.com/jobs/old",
                snippet="Remote Python role posted 4 weeks ago",
                age_text="4 weeks ago",
            ),
            RawInstantSearchResult(
                source_id="excluded",
                title="Backend Engineer Internship",
                url="https://example.com/jobs/internship",
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
                url="https://example.com/jobs/mystery",
                snippet="Remote Python role",
            )
        ]


class LowFitAdapter(InstantJobSearchAdapter):
    source_name = "brave_search"

    def search(
        self,
        source: InstantSearchSourceDefinition,
        query: InstantJobSearchQuery,
    ) -> list[RawInstantSearchResult]:
        return [
            RawInstantSearchResult(
                source_id="low-fit",
                title="Community Events Coordinator - Example Health",
                url="https://example.com/events/community-coordinator",
                snippet="Austin, TX role posted 1 day ago",
                age_text="1 day ago",
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


def test_runner_excludes_low_fit_by_default() -> None:
    app_config = load_app_config(Path("config"))
    registry = InstantJobSearchRegistry()
    registry.register(LowFitAdapter())

    summary = InstantJobSearchRunner(registry).run(
        app_config,
        JobSearchOverrides(query="backend engineer", location="Remote", max_age_days=7),
        now=datetime(2026, 4, 20, tzinfo=timezone.utc),
    )

    assert summary.skipped_for_relevance >= 1
    assert summary.results == []


def test_runner_includes_low_fit_when_requested() -> None:
    app_config = load_app_config(Path("config"))
    registry = InstantJobSearchRegistry()
    registry.register(LowFitAdapter())

    summary = InstantJobSearchRunner(registry).run(
        app_config,
        JobSearchOverrides(
            query="backend engineer",
            location="Remote",
            max_age_days=7,
            include_low_fit=True,
        ),
        now=datetime(2026, 4, 20, tzinfo=timezone.utc),
    )

    assert summary.include_low_fit is True
    assert summary.skipped_for_relevance == 0
    assert len(summary.results) == 1
    assert summary.results[0].title == "Community Events Coordinator"


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
