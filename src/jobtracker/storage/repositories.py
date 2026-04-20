"""Compatibility exports for storage repositories.

New code should import repository implementations from their domain modules.
This module keeps older imports working while storage is split by domain.
"""

from jobtracker.storage.company_repository import CompanyActivityRepository, CompanyRepository
from jobtracker.storage.discovery_repository import (
    CompanyDiscoveryObservationRepository,
    CompanyDiscoveryRepository,
    CompanyResolutionRepository,
)
from jobtracker.storage.job_repository import JobObservationRepository, JobRepository
from jobtracker.storage.repository_utils import to_utc_naive, utc_now
from jobtracker.storage.run_repository import SearchRunRepository
from jobtracker.storage.source_repository import SourceRepository

__all__ = [
    "CompanyActivityRepository",
    "CompanyDiscoveryObservationRepository",
    "CompanyDiscoveryRepository",
    "CompanyRepository",
    "CompanyResolutionRepository",
    "JobObservationRepository",
    "JobRepository",
    "SearchRunRepository",
    "SourceRepository",
    "to_utc_naive",
    "utc_now",
]
