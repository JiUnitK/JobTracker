"""Compatibility shim for job source adapter interfaces."""

from jobtracker.job_tracking.sources.base import SourceAdapter, SourceRunResult

__all__ = ["SourceAdapter", "SourceRunResult"]
