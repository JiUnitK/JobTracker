"""Compatibility shim for the tracked-job Ashby adapter.

New code should import from :mod:`jobtracker.job_tracking.sources.ashby`.
"""

from jobtracker.job_tracking.sources.ashby import AshbyAdapter

__all__ = ["AshbyAdapter"]
