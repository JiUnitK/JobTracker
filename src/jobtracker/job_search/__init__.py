"""Instant open-web job search workflow package.

This package owns side-effect-light search request and result models for the
instant job-search workflow. Adapters, planning, scoring, and reporting should
build on these models without depending on tracked-job persistence.
"""

from jobtracker.job_search.models import (
    AgeConfidence,
    InstantJobSearchQuery,
    InstantJobSearchRequest,
    InstantJobSearchResult,
    InstantJobSearchRunSummary,
    RawInstantSearchResult,
    SearchProvider,
)

__all__ = [
    "AgeConfidence",
    "InstantJobSearchQuery",
    "InstantJobSearchRequest",
    "InstantJobSearchResult",
    "InstantJobSearchRunSummary",
    "RawInstantSearchResult",
    "SearchProvider",
]
