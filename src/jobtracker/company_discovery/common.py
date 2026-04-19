from __future__ import annotations

from typing import Any


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
