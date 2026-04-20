"""Compatibility shim for the tracked-job Greenhouse adapter.

New code should import from :mod:`jobtracker.job_tracking.sources.greenhouse`.
"""

from jobtracker.job_tracking.sources.greenhouse import GreenhouseAdapter

__all__ = ["GreenhouseAdapter"]
