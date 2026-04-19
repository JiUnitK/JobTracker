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


class CompanyDirectoryDiscoveryAdapter(CompanyDiscoveryAdapter):
    source_name = "company_directory"

    def __init__(self, fetch_json: FetchJson | None = None) -> None:
        self.fetch_json = fetch_json or fetch_json_default

    def discover(
        self,
        source: CompanyDiscoverySourceDefinition,
        query: CompanyDiscoveryQuery,
    ) -> list[RawCompanyDiscovery]:
        entries = self._load_entries(source, query)
        discoveries: list[RawCompanyDiscovery] = []

        for entry in entries:
            company_name = str(entry["company_name"])
            location_text = str(entry.get("location_text", "") or "")
            workplace_type = str(entry.get("workplace_type", "unknown") or "unknown")
            searchable_text = " ".join(
                [
                    company_name,
                    str(entry.get("summary", "") or ""),
                    " ".join(str(item) for item in entry.get("tags", []) if item),
                    " ".join(str(item) for item in entry.get("role_focus", []) if item),
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
                    source_url=str(entry["source_url"]),
                    company_name=company_name,
                    company_url=entry.get("company_url"),
                    careers_url=entry.get("careers_url"),
                    job_title=entry.get("representative_role"),
                    location_text=location_text or None,
                    workplace_type=workplace_type,  # type: ignore[arg-type]
                    evidence_kind=str(entry.get("evidence_kind", "directory_entry")),
                    raw_payload=entry,
                )
            )
        return discoveries

    def _load_entries(
        self,
        source: CompanyDiscoverySourceDefinition,
        query: CompanyDiscoveryQuery,
    ) -> list[dict[str, Any]]:
        inline_entries = load_record_items(
            source.params,
            inline_key="entries",
            url_key="entries_urls",
            fetch_json=self.fetch_json,
        )
        if inline_entries:
            return inline_entries

        template = source.params.get("query_url_template")
        if not template:
            return []
        if not isinstance(template, str) or not template.strip():
            raise ValueError("company discovery source params.query_url_template must be a non-empty string")

        payload_key = source.params.get("entries_payload_key", "entries")
        if not isinstance(payload_key, str) or not payload_key.strip():
            raise ValueError("company discovery source params.entries_payload_key must be a non-empty string")

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
                loaded.append(dict(item))
        return loaded


def fetch_json_default(url: str) -> Any:
    return fetch_json_url(url)
