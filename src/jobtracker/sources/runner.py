"""Compatibility shim for tracked-job run coordination.

New code should import from :mod:`jobtracker.job_tracking.sources.runner`.
"""

from jobtracker.job_tracking.sources.runner import RunCoordinator, RunSummary

__all__ = ["RunCoordinator", "RunSummary"]
