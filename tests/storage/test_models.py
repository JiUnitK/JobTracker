from __future__ import annotations

from datetime import datetime, timezone

import pytest

from jobtracker.models import CompanyRecord, NormalizedJobPosting, RawJobPosting, SearchQuery


def test_search_query_requires_keywords() -> None:
    with pytest.raises(ValueError):
        SearchQuery(keywords=["   "], locations=["Austin, TX"])


def test_raw_job_posting_rejects_invalid_salary_range() -> None:
    with pytest.raises(ValueError):
        RawJobPosting(
            source="greenhouse",
            source_job_id="123",
            source_url="https://boards.greenhouse.io/example/jobs/123",
            title="Backend Engineer",
            company_name="Example",
            salary_min=200000,
            salary_max=100000,
        )


def test_normalized_job_posting_validates_nested_company() -> None:
    job = NormalizedJobPosting(
        source="lever",
        source_job_id="abc-123",
        source_url="https://jobs.lever.co/example/abc-123",
        canonical_key="example:backend-engineer:austin",
        title="Backend Engineer",
        company=CompanyRecord(
            normalized_name="example",
            display_name="Example",
            careers_url="https://example.com/careers",
        ),
        location_text="Austin, TX",
        workplace_type="hybrid",
        posted_at=datetime.now(timezone.utc),
        status="active",
    )

    assert job.company.normalized_name == "example"
    assert job.status == "active"
