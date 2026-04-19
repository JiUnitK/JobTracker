from __future__ import annotations

import re
from datetime import datetime

from jobtracker.models import CompanyRecord, NormalizedJobPosting, RawJobPosting


COMPANY_SUFFIX_PATTERN = re.compile(
    r"\b(incorporated|inc|llc|l\.l\.c|ltd|limited|corp|corporation|co|company)\b",
    re.IGNORECASE,
)
TITLE_REPLACEMENTS = {
    "sr": "senior",
    "sr.": "senior",
    "jr": "junior",
    "jr.": "junior",
    "swe": "software engineer",
    "sde": "software engineer",
}


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", lowered)
    return normalized.strip("-") or "unknown"


def normalize_company_name(name: str) -> str:
    normalized = COMPANY_SUFFIX_PATTERN.sub("", name)
    normalized = re.sub(r"[,&./]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return slugify(normalized)


def normalize_job_title(title: str) -> str:
    tokens = re.split(r"\s+", title.strip().lower())
    expanded = [TITLE_REPLACEMENTS.get(token, token) for token in tokens if token]
    normalized = " ".join(expanded)
    normalized = re.sub(r"[^a-z0-9\s]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or "unknown"


def normalize_workplace_type(
    workplace_type: str | None,
    location_text: str | None = None,
) -> str:
    normalized = (workplace_type or "").strip().lower()
    if normalized in {"remote", "hybrid", "onsite", "on-site"}:
        return "onsite" if normalized == "on-site" else normalized

    location = (location_text or "").lower()
    if "remote" in location:
        return "remote"
    if "hybrid" in location:
        return "hybrid"
    if location.strip():
        return "onsite"
    return "unknown"


def normalize_location_text(location_text: str | None, workplace_type: str | None = None) -> str | None:
    if not location_text:
        return "Remote" if normalize_workplace_type(workplace_type) == "remote" else None
    normalized = re.sub(r"\s+", " ", location_text).strip()
    if "remote" in normalized.lower():
        return "Remote"
    return normalized


def normalize_datetime(value: datetime | None) -> datetime | None:
    return value


def normalize_salary(
    salary_min: int | None,
    salary_max: int | None,
    salary_currency: str | None,
) -> tuple[int | None, int | None, str | None]:
    min_value = int(salary_min) if salary_min is not None else None
    max_value = int(salary_max) if salary_max is not None else None
    if min_value is not None and max_value is not None and min_value > max_value:
        min_value, max_value = max_value, min_value
    currency = salary_currency.upper() if salary_currency else None
    return min_value, max_value, currency


def build_canonical_key(raw_job: RawJobPosting) -> str:
    location_part = normalize_location_text(raw_job.location_text, raw_job.workplace_type)
    return ":".join(
        [
            normalize_company_name(raw_job.company_name),
            slugify(normalize_job_title(raw_job.title)),
            slugify(location_part or normalize_workplace_type(raw_job.workplace_type)),
        ]
    )


def normalize_raw_job(raw_job: RawJobPosting) -> NormalizedJobPosting:
    workplace_type = normalize_workplace_type(raw_job.workplace_type, raw_job.location_text)
    location_text = normalize_location_text(raw_job.location_text, workplace_type)
    salary_min, salary_max, salary_currency = normalize_salary(
        raw_job.salary_min,
        raw_job.salary_max,
        raw_job.salary_currency,
    )
    company = CompanyRecord(
        normalized_name=normalize_company_name(raw_job.company_name),
        display_name=re.sub(r"\s+", " ", raw_job.company_name).strip(),
    )
    return NormalizedJobPosting(
        source=raw_job.source,
        source_job_id=raw_job.source_job_id,
        source_url=raw_job.source_url,
        canonical_key=build_canonical_key(raw_job),
        title=re.sub(r"\s+", " ", raw_job.title).strip(),
        company=company,
        location_text=location_text,
        workplace_type=workplace_type,
        posted_at=normalize_datetime(raw_job.posted_at),
        description_snippet=raw_job.description_snippet,
        employment_type=raw_job.employment_type,
        seniority=raw_job.seniority,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
        raw_tags=raw_job.raw_tags,
        status="active",
    )
