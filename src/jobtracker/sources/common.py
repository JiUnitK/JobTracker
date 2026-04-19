"""Compatibility shim for job source helpers."""

from jobtracker.job_tracking.sources.common import (
    display_name_from_token,
    extract_snippet,
    fetch_json,
    infer_workplace_type,
    matches_query,
    parse_datetime,
)

__all__ = [
    "display_name_from_token",
    "extract_snippet",
    "fetch_json",
    "infer_workplace_type",
    "matches_query",
    "parse_datetime",
]
