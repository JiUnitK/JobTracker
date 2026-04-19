"""Source adapters for the job-tracking workflow."""

from jobtracker.job_tracking.sources.ashby import AshbyAdapter
from jobtracker.job_tracking.sources.base import SourceAdapter, SourceRunResult
from jobtracker.job_tracking.sources.greenhouse import GreenhouseAdapter
from jobtracker.job_tracking.sources.lever import LeverAdapter
from jobtracker.job_tracking.sources.planner import build_search_queries
from jobtracker.job_tracking.sources.registry import SourceRegistry, build_default_registry
from jobtracker.job_tracking.sources.runner import RunCoordinator, RunSummary

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
