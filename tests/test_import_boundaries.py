from __future__ import annotations

from jobtracker import normalize, scoring, sources
from jobtracker import storage
from jobtracker.job_tracking import normalize as job_tracking_normalize
from jobtracker.job_tracking import scoring as job_tracking_scoring
from jobtracker.job_tracking import sources as job_tracking_sources
from jobtracker.storage import repositories
from jobtracker.storage.company_repository import CompanyActivityRepository, CompanyRepository
from jobtracker.storage.discovery_repository import (
    CompanyDiscoveryObservationRepository,
    CompanyDiscoveryRepository,
    CompanyResolutionRepository,
)
from jobtracker.storage.job_repository import JobObservationRepository, JobRepository
from jobtracker.storage.run_repository import SearchRunRepository
from jobtracker.storage.source_repository import SourceRepository


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


def test_storage_repositories_module_is_compatibility_shim() -> None:
    assert repositories.CompanyActivityRepository is CompanyActivityRepository
    assert repositories.CompanyRepository is CompanyRepository
    assert repositories.CompanyDiscoveryRepository is CompanyDiscoveryRepository
    assert repositories.CompanyDiscoveryObservationRepository is CompanyDiscoveryObservationRepository
    assert repositories.CompanyResolutionRepository is CompanyResolutionRepository
    assert repositories.JobRepository is JobRepository
    assert repositories.JobObservationRepository is JobObservationRepository
    assert repositories.SearchRunRepository is SearchRunRepository
    assert repositories.SourceRepository is SourceRepository


def test_storage_package_preserves_repository_exports() -> None:
    assert storage.CompanyActivityRepository is CompanyActivityRepository
    assert storage.CompanyRepository is CompanyRepository
    assert storage.CompanyDiscoveryRepository is CompanyDiscoveryRepository
    assert storage.CompanyDiscoveryObservationRepository is CompanyDiscoveryObservationRepository
    assert storage.CompanyResolutionRepository is CompanyResolutionRepository
    assert storage.JobRepository is JobRepository
    assert storage.JobObservationRepository is JobObservationRepository
    assert storage.SearchRunRepository is SearchRunRepository
    assert storage.SourceRepository is SourceRepository
