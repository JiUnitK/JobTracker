"""Compatibility shim for the tracked-job Lever adapter.

New code should import from :mod:`jobtracker.job_tracking.sources.lever`.
"""

from jobtracker.job_tracking.sources.lever import LeverAdapter

__all__ = ["LeverAdapter"]
