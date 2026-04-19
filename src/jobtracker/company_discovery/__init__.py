"""Company discovery workflow package."""

from jobtracker.company_discovery.common import (
    ensure_list_param,
    location_matches_query,
    text_matches_query,
    workplace_matches_query,
)
from jobtracker.company_discovery.ecosystem_adapter import AustinEcosystemDiscoveryAdapter
from jobtracker.company_discovery.base import CompanyDiscoveryAdapter
from jobtracker.company_discovery.normalize import (
    infer_resolution_candidate,
    normalize_company_discovery,
    normalize_company_name,
)
from jobtracker.company_discovery.planner import build_company_discovery_queries
from jobtracker.company_discovery.registry import (
    CompanyDiscoveryRegistry,
    build_default_company_discovery_registry,
)
from jobtracker.company_discovery.runner import CompanyDiscoveryRunSummary, CompanyDiscoveryRunner
from jobtracker.company_discovery.search_adapter import CompanySearchDiscoveryAdapter
from jobtracker.company_discovery.scoring import (
    CompanyDiscoveryScoreResult,
    CompanyDiscoveryScoringService,
)

__all__ = [
    "AustinEcosystemDiscoveryAdapter",
    "CompanyDiscoveryAdapter",
    "CompanyDiscoveryRegistry",
    "CompanyDiscoveryScoreResult",
    "CompanyDiscoveryScoringService",
    "CompanyDiscoveryRunSummary",
    "CompanyDiscoveryRunner",
    "CompanySearchDiscoveryAdapter",
    "build_company_discovery_queries",
    "build_default_company_discovery_registry",
    "ensure_list_param",
    "infer_resolution_candidate",
    "location_matches_query",
    "normalize_company_discovery",
    "normalize_company_name",
    "text_matches_query",
    "workplace_matches_query",
]
