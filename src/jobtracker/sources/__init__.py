"""Source adapters package."""

from jobtracker.sources.ashby import AshbyAdapter
from jobtracker.sources.base import SourceAdapter, SourceRunResult
from jobtracker.sources.greenhouse import GreenhouseAdapter
from jobtracker.sources.lever import LeverAdapter
from jobtracker.sources.planner import build_search_queries
from jobtracker.sources.registry import SourceRegistry, build_default_registry
from jobtracker.sources.runner import RunCoordinator, RunSummary

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
