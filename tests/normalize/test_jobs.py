from __future__ import annotations

from jobtracker.models import RawJobPosting
from jobtracker.normalize import (
    build_canonical_key,
    normalize_company_name,
    normalize_job_title,
    normalize_location_text,
    normalize_raw_job,
    normalize_salary,
    normalize_workplace_type,
)


def test_normalize_company_name_removes_common_suffixes() -> None:
    assert normalize_company_name("Example, Inc.") == "example"
    assert normalize_company_name("Example Company LLC") == "example"


def test_normalize_job_title_expands_common_abbreviations() -> None:
    assert normalize_job_title("Sr. SWE") == "senior software engineer"


def test_normalize_workplace_and_location_text_handle_remote() -> None:
    assert normalize_workplace_type("unknown", "Remote - United States") == "remote"
    assert normalize_location_text("Remote - United States", "remote") == "Remote"


def test_normalize_salary_orders_values_and_normalizes_currency() -> None:
    assert normalize_salary(200000, 150000, "usd") == (150000, 200000, "USD")


def test_build_canonical_key_uses_normalized_fields() -> None:
    raw_job = RawJobPosting(
        source="greenhouse",
        source_job_id="123",
        source_url="https://boards.greenhouse.io/example/jobs/123",
        title="Sr. SWE",
        company_name="Example, Inc.",
        location_text="Remote - United States",
    )

    assert build_canonical_key(raw_job) == "example:senior-software-engineer:remote"


def test_normalize_raw_job_applies_normalized_fields() -> None:
    raw_job = RawJobPosting(
        source="ashby",
        source_job_id="abc",
        source_url="https://jobs.ashbyhq.com/Example/abc",
        title="Backend Engineer",
        company_name="Example Company LLC",
        location_text="Remote - United States",
        workplace_type="unknown",
        salary_min=150000,
        salary_max=175000,
        salary_currency="usd",
    )

    normalized = normalize_raw_job(raw_job)

    assert normalized.company.normalized_name == "example"
    assert normalized.location_text == "Remote"
    assert normalized.workplace_type == "remote"
    assert normalized.salary_min == 150000
    assert normalized.salary_currency == "USD"
