"""Compatibility exports for tracked-job source adapters.

New code should import from :mod:`jobtracker.job_tracking.sources`. This package
exists to keep older imports working while the tracked-job workflow lives in its
explicit workflow namespace.
"""

from jobtracker.job_tracking.sources import (
    AshbyAdapter,
    GreenhouseAdapter,
    LeverAdapter,
    RunCoordinator,
    RunSummary,
    SourceAdapter,
    SourceRegistry,
    SourceRunResult,
    build_default_registry,
    build_search_queries,
)

__all__ = [
    "AshbyAdapter",
    "GreenhouseAdapter",
    "LeverAdapter",
    "RunCoordinator",
    "RunSummary",
    "SourceAdapter",
    "SourceRegistry",
    "SourceRunResult",
    "build_default_registry",
    "build_search_queries",
]
