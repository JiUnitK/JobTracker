from __future__ import annotations

import re

from jobtracker.models import CompanyRecord, NormalizedJobPosting, RawJobPosting


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", lowered)
    return normalized.strip("-") or "unknown"


def normalize_company_name(name: str) -> str:
    return slugify(name)


def build_canonical_key(raw_job: RawJobPosting) -> str:
    location_part = raw_job.location_text or raw_job.workplace_type
    return ":".join(
        [
            normalize_company_name(raw_job.company_name),
            slugify(raw_job.title),
            slugify(location_part),
        ]
    )


def normalize_raw_job(raw_job: RawJobPosting) -> NormalizedJobPosting:
    company = CompanyRecord(
        normalized_name=normalize_company_name(raw_job.company_name),
        display_name=raw_job.company_name,
    )
    return NormalizedJobPosting(
        source=raw_job.source,
        source_job_id=raw_job.source_job_id,
        source_url=raw_job.source_url,
        canonical_key=build_canonical_key(raw_job),
        title=raw_job.title,
        company=company,
        location_text=raw_job.location_text,
        workplace_type=raw_job.workplace_type,
        posted_at=raw_job.posted_at,
        description_snippet=raw_job.description_snippet,
        employment_type=raw_job.employment_type,
        seniority=raw_job.seniority,
        salary_min=raw_job.salary_min,
        salary_max=raw_job.salary_max,
        salary_currency=raw_job.salary_currency,
        raw_tags=raw_job.raw_tags,
        status="active",
    )
