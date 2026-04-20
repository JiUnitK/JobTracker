"""Company-first discovery, resolution, and promotion workflow.

This package owns discovering companies, resolving their hiring surfaces, and
promoting selected companies into tracked monitoring. Persisted ATS job
collection belongs in ``jobtracker.job_tracking``; instant open-web job search
belongs in ``jobtracker.job_search``.
"""

from jobtracker.company_discovery.common import (
    build_query_urls,
    ensure_list_param,
    fetch_json_url,
    location_matches_query,
    load_record_items,
    text_matches_query,
    workplace_matches_query,
)
from jobtracker.company_discovery.base import CompanyDiscoveryAdapter
from jobtracker.company_discovery.normalize import (
    normalize_company_discovery,
    normalize_company_name,
)
from jobtracker.company_discovery.resolution import (
    ResolutionCandidate,
    infer_resolution_candidate,
    infer_resolution_candidates,
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
    "CompanyDiscoveryAdapter",
    "CompanyDiscoveryRegistry",
    "CompanyDiscoveryScoreResult",
    "CompanyDiscoveryScoringService",
    "CompanyDiscoveryRunSummary",
    "CompanyDiscoveryRunner",
    "CompanySearchDiscoveryAdapter",
    "ResolutionCandidate",
    "build_company_discovery_queries",
    "build_default_company_discovery_registry",
    "build_query_urls",
    "ensure_list_param",
    "fetch_json_url",
    "infer_resolution_candidate",
    "infer_resolution_candidates",
    "location_matches_query",
    "load_record_items",
    "normalize_company_discovery",
    "normalize_company_name",
    "text_matches_query",
    "workplace_matches_query",
]
