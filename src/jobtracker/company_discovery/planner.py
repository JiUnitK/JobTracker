from __future__ import annotations

from jobtracker.config.models import CompanyDiscoveryConfig
from jobtracker.models import CompanyDiscoveryQuery


def build_company_discovery_queries(
    config: CompanyDiscoveryConfig,
) -> list[CompanyDiscoveryQuery]:
    return [
        CompanyDiscoveryQuery(
            keywords=query.keywords,
            locations=query.locations,
            workplace_types=query.workplace_types,
            source_names=query.source_names,
        )
        for query in config.queries
    ]
