"""Compatibility shim for tracked-job source adapter interfaces.

New code should import from :mod:`jobtracker.job_tracking.sources.base`.
"""

from jobtracker.job_tracking.sources.base import SourceAdapter, SourceRunResult

__all__ = ["SourceAdapter", "SourceRunResult"]
