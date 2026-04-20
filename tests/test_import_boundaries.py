from __future__ import annotations

from jobtracker import normalize, scoring, sources
from jobtracker.job_tracking import normalize as job_tracking_normalize
from jobtracker.job_tracking import scoring as job_tracking_scoring
from jobtracker.job_tracking import sources as job_tracking_sources


def test_top_level_sources_package_is_compatibility_shim() -> None:
    assert sources.AshbyAdapter is job_tracking_sources.AshbyAdapter
    assert sources.GreenhouseAdapter is job_tracking_sources.GreenhouseAdapter
    assert sources.LeverAdapter is job_tracking_sources.LeverAdapter
    assert sources.RunCoordinator is job_tracking_sources.RunCoordinator
    assert sources.SourceRegistry is job_tracking_sources.SourceRegistry


def test_top_level_normalize_package_is_compatibility_shim() -> None:
    assert normalize.normalize_raw_job is job_tracking_normalize.normalize_raw_job
    assert normalize.normalize_job_title is job_tracking_normalize.normalize_job_title
    assert normalize.normalize_company_name is job_tracking_normalize.normalize_company_name


def test_top_level_scoring_package_is_compatibility_shim() -> None:
    assert scoring.ScoringService is job_tracking_scoring.ScoringService
    assert scoring.JobScoreResult is job_tracking_scoring.JobScoreResult
