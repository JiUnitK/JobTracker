"""Compatibility shim for tracked-job query planning.

New code should import from :mod:`jobtracker.job_tracking.sources.planner`.
"""

from jobtracker.job_tracking.sources.planner import build_search_queries

__all__ = ["build_search_queries"]
