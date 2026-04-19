"""Compatibility exports for job normalization helpers."""

from jobtracker.job_tracking.normalize import (
    build_canonical_key,
    normalize_datetime,
    normalize_company_name,
    normalize_job_title,
    normalize_location_text,
    normalize_raw_job,
    normalize_salary,
    normalize_workplace_type,
    slugify,
)

__all__ = [
    "build_canonical_key",
    "normalize_datetime",
    "normalize_company_name",
    "normalize_job_title",
    "normalize_location_text",
    "normalize_raw_job",
    "normalize_salary",
    "normalize_workplace_type",
    "slugify",
]
