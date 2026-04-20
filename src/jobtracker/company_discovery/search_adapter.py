from __future__ import annotations

import os
from typing import Any, Callable
from urllib.request import Request, urlopen

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
        self._uses_injected_fetch = fetch_json is not None

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

        template = os.path.expandvars(template)

        payload_key = source.params.get("results_payload_key", "results")
        if not isinstance(payload_key, str) or not payload_key.strip():
            raise ValueError("company discovery source params.results_payload_key must be a non-empty string")

        field_map: dict[str, str] = source.params.get("field_map", {})

        urls = build_query_urls(
            template,
            keywords=query.keywords,
            locations=query.locations,
            workplace_types=query.workplace_types,
        )
        loaded: list[dict[str, Any]] = []
        for url in urls:
            payload = self._fetch_payload(source, url)
            items: Any = _payload_items(payload, payload_key)
            if not isinstance(items, list):
                raise ValueError(
                    f"company discovery payload from {url} must be a list or mapping with '{payload_key}'"
                )
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError(
                        f"company discovery payload items from {url} must be mappings"
                    )
                merged = {field_map.get(k, k): v for k, v in item.items()} if field_map else dict(item)
                merged.setdefault("source_url", url)
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

    def _fetch_payload(
        self,
        source: CompanyDiscoverySourceDefinition,
        url: str,
    ) -> Any:
        if self._uses_injected_fetch:
            return self.fetch_json(url)
        return fetch_json_for_source(url, source)


def _payload_items(payload: Any, payload_key: str) -> Any:
    if not isinstance(payload, dict):
        return payload
    items = payload.get(payload_key)
    if payload_key == "web.results" and items is None:
        web = payload.get("web")
        if isinstance(web, dict):
            return _normalize_brave_web_results(web.get("results", []))
    return items


def _normalize_brave_web_results(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "") or "").strip()
        url = str(item.get("url", "") or "").strip()
        if not title or not url:
            continue
        profile = item.get("profile", {})
        profile_name = profile.get("long_name", "") if isinstance(profile, dict) else ""
        snippet = str(item.get("description", "") or "")
        searchable_text = " ".join([title, snippet, url])
        normalized.append(
            {
                "company_name": _infer_company_name(title, profile_name, url),
                "job_title": title,
                "location_text": searchable_text,
                "workplace_type": _infer_workplace_type(searchable_text),
                "source_url": url,
                "job_url": url,
                "snippet": snippet,
                "evidence_kind": "brave_web_result",
                "raw_payload": item,
            }
        )
    return normalized


def _infer_company_name(title: str, profile_name: str, url: str) -> str:
    for separator in [" - ", " | ", " at "]:
        if separator in title:
            parts = [part.strip() for part in title.split(separator) if part.strip()]
            if len(parts) >= 2:
                return parts[-1]
    if profile_name.strip():
        return profile_name.strip()
    host = url.split("//", 1)[-1].split("/", 1)[0]
    return host.removeprefix("www.") or "Unknown Company"


def _infer_workplace_type(text: str) -> str:
    lowered = text.lower()
    if "remote" in lowered:
        return "remote"
    if "hybrid" in lowered:
        return "hybrid"
    if "onsite" in lowered or "on-site" in lowered:
        return "onsite"
    return "unknown"

def fetch_json_default(url: str) -> Any:
    return fetch_json_url(url)


def fetch_json_for_source(url: str, source: CompanyDiscoverySourceDefinition) -> Any:
    api_key_env = source.params.get("api_key_env")
    if not api_key_env:
        return fetch_json_url(url)
    if not isinstance(api_key_env, str) or not api_key_env.strip():
        raise ValueError("company discovery source params.api_key_env must be a non-empty string")
    api_key = os.environ.get(api_key_env, "").strip()
    if not api_key:
        raise ValueError(f"{api_key_env} is required for {source.name}")
    request = Request(
        url,
        headers={
            "User-Agent": "JobTracker/0.1.0 (+https://local.jobtracker)",
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
        },
    )
    import json

    with urlopen(request, timeout=15.0) as response:
        return json.loads(response.read().decode("utf-8"))
