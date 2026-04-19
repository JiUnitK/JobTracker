from __future__ import annotations

from jobtracker.config.models import AppConfig
from jobtracker.models import SearchQuery


def build_search_queries(config: AppConfig) -> list[SearchQuery]:
    return [
        SearchQuery(
            keywords=config.search_terms.include,
            locations=config.search_terms.locations,
            workplace_types=config.search_terms.workplace_types,
            seniority=config.search_terms.seniority,
        )
    ]
