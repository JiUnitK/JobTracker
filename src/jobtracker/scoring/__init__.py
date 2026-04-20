"""Compatibility exports for tracked-job scoring.

New code should import from :mod:`jobtracker.job_tracking.scoring`.
"""

from jobtracker.job_tracking.scoring import JobScoreResult, ScoringService

__all__ = ["JobScoreResult", "ScoringService"]
