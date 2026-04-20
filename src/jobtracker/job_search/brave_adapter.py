from __future__ import annotations

import json
import os
from datetime import datetime
from json import JSONDecodeError
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from jobtracker.config.models import InstantSearchSourceDefinition
from jobtracker.job_search.base import InstantJobSearchAdapter
from jobtracker.job_search.models import InstantJobSearchQuery, RawInstantSearchResult


FetchBraveJson = Callable[[str, str, float], Any]


class BraveSearchError(RuntimeError):
    """Raised when Brave Search returns an unusable response."""


class BraveSearchAdapter(InstantJobSearchAdapter):
    source_name = "brave_search"

    def __init__(self, fetch_json: FetchBraveJson | None = None) -> None:
        self.fetch_json = fetch_json or fetch_brave_json

    def search(
        self,
        source: InstantSearchSourceDefinition,
        query: InstantJobSearchQuery,
    ) -> list[RawInstantSearchResult]:
        api_key = os.environ.get(source.api_key_env, "").strip()
        if not api_key:
            raise ValueError(f"{source.api_key_env} is required for {source.name}")

        url = build_brave_search_url(source, query.query)
        payload = self.fetch_json(url, api_key, _timeout_seconds(source))
        return parse_brave_results(payload)


def build_brave_search_url(source: InstantSearchSourceDefinition, query: str) -> str:
    if source.base_url is None:
        raise ValueError("brave_search source requires base_url")

    params = {
        "q": query,
        "count": _int_param(source, "count", 20),
        "country": _str_param(source, "country", "US"),
        "search_lang": _str_param(source, "search_lang", "en"),
        "safesearch": _str_param(source, "safesearch", "moderate"),
    }
    return f"{source.base_url}?{urlencode(params)}"


def parse_brave_results(payload: Any) -> list[RawInstantSearchResult]:
    if not isinstance(payload, dict):
        raise ValueError("Brave Search response must be a JSON object")
    web = payload.get("web", {})
    if web is None:
        return []
    if not isinstance(web, dict):
        raise ValueError("Brave Search response web must be an object")
    results = web.get("results", [])
    if not isinstance(results, list):
        raise ValueError("Brave Search response web.results must be a list")

    parsed: list[RawInstantSearchResult] = []
    for index, item in enumerate(results):
        if not isinstance(item, dict):
            raise ValueError("Brave Search result entries must be objects")
        title = str(item.get("title", "") or "").strip()
        url = str(item.get("url", "") or "").strip()
        if not title or not url:
            continue
        age_text = _first_text(item, ["age", "page_age", "date", "published"])
        published_at = _parse_datetime(_first_text(item, ["page_age", "published", "date"]))
        profile = item.get("profile", {})
        profile_name = profile.get("long_name", "") if isinstance(profile, dict) else ""
        parsed.append(
            RawInstantSearchResult(
                source_id=str(profile_name or item.get("url") or f"brave-{index}"),
                title=title,
                url=url,
                snippet=str(item.get("description", "") or "").strip() or None,
                published_at=published_at,
                age_text=age_text,
                raw_payload=item,
            )
        )
    return parsed


def fetch_brave_json(url: str, api_key: str, timeout_seconds: float) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "JobTracker/0.1.0 (+https://local.jobtracker)",
            "X-Subscription-Token": api_key,
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            if response.status >= 400:
                raise BraveSearchError(
                    f"Brave Search request failed with HTTP {response.status}"
                )
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = _http_error_detail(exc)
        message = f"Brave Search request failed with HTTP {exc.code}"
        if detail:
            message = f"{message}: {detail}"
        raise BraveSearchError(message) from exc
    except URLError as exc:
        raise BraveSearchError(f"Brave Search request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise BraveSearchError("Brave Search request timed out") from exc

    try:
        return json.loads(payload)
    except JSONDecodeError as exc:
        raise BraveSearchError("Brave Search response was not valid JSON") from exc


def _first_text(item: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized or "ago" in normalized.lower():
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _http_error_detail(exc: HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8", errors="replace")
    except Exception:
        return ""
    if not raw.strip():
        return ""
    try:
        payload = json.loads(raw)
    except JSONDecodeError:
        return raw.strip()[:200]
    if isinstance(payload, dict):
        for key in ["message", "error", "detail"]:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            return str(errors[0])[:200]
    return raw.strip()[:200]


def _int_param(source: InstantSearchSourceDefinition, key: str, default: int) -> int:
    value = source.params.get(key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"brave_search params.{key} must be an integer") from exc
    return max(1, min(parsed, 50))


def _str_param(source: InstantSearchSourceDefinition, key: str, default: str) -> str:
    value = source.params.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"brave_search params.{key} must be a non-empty string")
    return value.strip()


def _timeout_seconds(source: InstantSearchSourceDefinition) -> float:
    value = source.params.get("timeout_seconds", 15)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("brave_search params.timeout_seconds must be numeric") from exc
