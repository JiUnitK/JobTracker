from __future__ import annotations

from typing import Any, Callable

from jobtracker.company_discovery.base import CompanyDiscoveryAdapter
from jobtracker.company_discovery.common import (
    build_query_urls,
    fetch_json_url,
    location_matches_query,
    load_record_items,
    text_matches_query,
    workplace_matches_query,
)
from jobtracker.config.models import CompanyDiscoverySourceDefinition
from jobtracker.models import CompanyDiscoveryQuery, RawCompanyDiscovery


FetchJson = Callable[[str], Any]


class CompanySearchDiscoveryAdapter(CompanyDiscoveryAdapter):
    source_name = "company_search"

    def __init__(self, fetch_json: FetchJson | None = None) -> None:
        self.fetch_json = fetch_json or fetch_json_default

    def discover(
        self,
        source: CompanyDiscoverySourceDefinition,
        query: CompanyDiscoveryQuery,
    ) -> list[RawCompanyDiscovery]:
        results = self._load_results(source, query)
        discoveries: list[RawCompanyDiscovery] = []

        for result in results:
            job_title = str(result.get("job_title", "") or "")
            location_text = str(result.get("location_text", "") or "")
            workplace_type = str(result.get("workplace_type", "unknown") or "unknown")
            searchable_text = " ".join(
                [
                    str(result.get("company_name", "") or ""),
                    job_title,
                    str(result.get("snippet", "") or ""),
                    " ".join(str(item) for item in result.get("tags", []) if item),
                ]
            )
            if not text_matches_query(searchable_text, query.keywords):
                continue
            if not location_matches_query(location_text, query.locations):
                continue
            if not workplace_matches_query(workplace_type, query.workplace_types):
                continue

            discoveries.append(
                RawCompanyDiscovery(
                    source_name=source.name,
                    source_type=source.type,
                    source_url=str(result["source_url"]),
                    company_name=str(result["company_name"]),
                    company_url=result.get("company_url"),
                    careers_url=result.get("careers_url"),
                    job_url=result.get("job_url"),
                    job_title=job_title or None,
                    location_text=location_text or None,
                    workplace_type=workplace_type,  # type: ignore[arg-type]
                    evidence_kind=str(result.get("evidence_kind", "job_result")),
                    raw_payload=result,
                )
            )
        return discoveries

    def _load_results(
        self,
        source: CompanyDiscoverySourceDefinition,
        query: CompanyDiscoveryQuery,
    ) -> list[dict[str, Any]]:
        inline_results = load_record_items(
            source.params,
            inline_key="results",
            url_key="results_urls",
            fetch_json=self.fetch_json,
        )
        if inline_results:
            return inline_results

        template = source.params.get("query_url_template")
        if not template:
            return []
        if not isinstance(template, str) or not template.strip():
            raise ValueError("company discovery source params.query_url_template must be a non-empty string")

        payload_key = source.params.get("results_payload_key", "results")
        if not isinstance(payload_key, str) or not payload_key.strip():
            raise ValueError("company discovery source params.results_payload_key must be a non-empty string")

        urls = build_query_urls(
            template,
            keywords=query.keywords,
            locations=query.locations,
            workplace_types=query.workplace_types,
        )
        loaded: list[dict[str, Any]] = []
        for url in urls:
            payload = self.fetch_json(url)
            items: Any = payload
            if isinstance(payload, dict):
                items = payload.get(payload_key)
            if not isinstance(items, list):
                raise ValueError(
                    f"company discovery payload from {url} must be a list or mapping with '{payload_key}'"
                )
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError(
                        f"company discovery payload items from {url} must be mappings"
                    )
                merged = dict(item)
                merged.setdefault(
                    "raw_payload",
                    {
                        "query_url": url,
                        "query_keywords": query.keywords,
                        "query_locations": query.locations,
                        "query_workplace_types": query.workplace_types,
                    },
                )
                loaded.append(merged)
        return loaded

def fetch_json_default(url: str) -> Any:
    return fetch_json_url(url)
