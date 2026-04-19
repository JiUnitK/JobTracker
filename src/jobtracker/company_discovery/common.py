from __future__ import annotations

import json
from typing import Any, Callable
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


def ensure_list_param(params: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = params.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"company discovery source params.{key} must be a list")
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"company discovery source params.{key} entries must be mappings")
        normalized.append(item)
    return normalized


def text_matches_query(value: str | None, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = (value or "").lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def location_matches_query(value: str | None, locations: list[str]) -> bool:
    if not locations:
        return True
    haystack = (value or "").lower()
    return any(location.lower() in haystack for location in locations)


def workplace_matches_query(value: str | None, workplace_types: list[str]) -> bool:
    if not workplace_types:
        return True
    return (value or "unknown").lower() in {item.lower() for item in workplace_types}


def fetch_json_url(url: str, *, timeout_seconds: float = 15.0) -> Any:
    request = Request(
        url,
        headers={
            "User-Agent": "JobTracker/0.1.0 (+https://local.jobtracker)",
            "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _coerce_url_list(params: dict[str, Any], key: str) -> list[str]:
    value = params.get(key, [])
    if not value:
        return []
    if not isinstance(value, list):
        raise ValueError(f"company discovery source params.{key} must be a list")
    urls: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"company discovery source params.{key} entries must be non-empty strings")
        urls.append(item.strip())
    return urls


def load_record_items(
    params: dict[str, Any],
    *,
    inline_key: str,
    url_key: str,
    fetch_json: Callable[[str], Any],
) -> list[dict[str, Any]]:
    inline_items = ensure_list_param(params, inline_key)
    if inline_items:
        return inline_items

    urls = _coerce_url_list(params, url_key)
    loaded: list[dict[str, Any]] = []
    for url in urls:
        payload = fetch_json(url)
        items: Any = payload
        if isinstance(payload, dict):
            items = payload.get(inline_key)
        if not isinstance(items, list):
            raise ValueError(
                f"company discovery payload from {url} must be a list or mapping with '{inline_key}'"
            )
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(
                    f"company discovery payload items from {url} must be mappings"
                )
            loaded.append(item)
    return loaded


def build_query_urls(
    template: str,
    *,
    keywords: list[str],
    locations: list[str],
    workplace_types: list[str],
) -> list[str]:
    keyword_values = keywords or [""]
    location_values = locations or [""]
    workplace_values = workplace_types or [""]
    urls: list[str] = []
    for keyword in keyword_values:
        for location in location_values:
            for workplace_type in workplace_values:
                combined = " ".join(
                    item for item in [keyword, location, workplace_type] if item
                ).strip()
                urls.append(
                    template.format(
                        query=quote_plus(combined),
                        keyword=quote_plus(keyword),
                        location=quote_plus(location),
                        workplace_type=quote_plus(workplace_type),
                    )
                )
    return urls
