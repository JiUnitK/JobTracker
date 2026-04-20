from __future__ import annotations

from jobtracker.job_search.models import (
    InstantJobSearchQuery,
    InstantJobSearchResult,
    InstantJobSearchRunSummary,
)
from jobtracker.job_search.reporting import format_instant_job_search_markdown


def test_format_instant_job_search_markdown_outputs_review_table() -> None:
    summary = InstantJobSearchRunSummary(
        requested_queries=[InstantJobSearchQuery(query="customer success", location="Remote")],
        max_age_days=7,
        skipped_for_age=1,
        skipped_for_relevance=2,
        results=[
            InstantJobSearchResult(
                title="Customer Success Specialist",
                company="Example Health",
                location="Remote",
                url="https://example.com/jobs/1",
                age_text="2 days ago",
                score=86,
                reasons=["strong title match", "recent posting"],
            )
        ],
    )

    output = format_instant_job_search_markdown(summary)

    assert "# Instant Job Search" in output
    assert "Skipped for age: 1" in output
    assert "| Rank | Title | Company | Location | Age | Score | Why | URL |" in output
    assert "Customer Success Specialist" in output
    assert "strong title match, recent posting" in output

