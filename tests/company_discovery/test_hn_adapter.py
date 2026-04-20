from __future__ import annotations

import json
from pathlib import Path

import pytest

from jobtracker.config.models import CompanyDiscoverySourceDefinition
from jobtracker.company_discovery.hn_adapter import HNHiringDiscoveryAdapter, _parse_comment
from jobtracker.models import CompanyDiscoveryQuery


_STORY_ID = "43500001"

_ALGOLIA_SEARCH_RESPONSE = {
    "hits": [{"objectID": _STORY_ID, "title": "Ask HN: Who is hiring? (April 2026)", "points": 512}]
}


def _story_fixture() -> dict:
    return json.loads(
        (Path("tests/fixtures/hn_whos_hiring_story.json")).read_text(encoding="utf-8")
    )


def _fetch_json_factory(story: dict):
    """Returns a fetch_json stub that serves the story for item requests and search for search."""
    def fetch_json(url: str):
        if "items/" in url:
            return story
        return _ALGOLIA_SEARCH_RESPONSE
    return fetch_json


def _source(params: dict | None = None) -> CompanyDiscoverySourceDefinition:
    return CompanyDiscoverySourceDefinition(
        name="hn_whos_hiring",
        type="aggregator",
        enabled=True,
        params=params or {},
    )


def _query(**kwargs) -> CompanyDiscoveryQuery:
    defaults = dict(
        keywords=["software engineer", "backend engineer", "platform engineer", "machine learning engineer"],
        locations=["Remote", "Austin, TX"],
        workplace_types=["remote", "hybrid"],
    )
    return CompanyDiscoveryQuery(**(defaults | kwargs))


def test_discovers_matching_companies() -> None:
    story = _story_fixture()
    adapter = HNHiringDiscoveryAdapter(fetch_json=_fetch_json_factory(story))

    discoveries = adapter.discover(_source({"story_id": _STORY_ID}), _query())

    company_names = {d.company_name for d in discoveries}
    assert "Pulse Labs" in company_names
    assert "Northwind Systems" in company_names
    assert "Orbital AI" in company_names


def test_filters_non_engineering_roles() -> None:
    story = _story_fixture()
    adapter = HNHiringDiscoveryAdapter(fetch_json=_fetch_json_factory(story))

    discoveries = adapter.discover(_source({"story_id": _STORY_ID}), _query())

    assert "DesignCo" not in {d.company_name for d in discoveries}


def test_respects_workplace_type_filter() -> None:
    story = _story_fixture()
    adapter = HNHiringDiscoveryAdapter(fetch_json=_fetch_json_factory(story))

    # Remote + hybrid — FinEdge (onsite) should be excluded
    discoveries = adapter.discover(_source({"story_id": _STORY_ID}), _query())

    assert "FinEdge" not in {d.company_name for d in discoveries}


def test_extracts_ats_url_as_careers_url() -> None:
    story = _story_fixture()
    adapter = HNHiringDiscoveryAdapter(fetch_json=_fetch_json_factory(story))

    discoveries = adapter.discover(_source({"story_id": _STORY_ID}), _query())

    pulse = next(d for d in discoveries if d.company_name == "Pulse Labs")
    assert pulse.careers_url is not None
    assert "greenhouse.io" in str(pulse.careers_url)

    orbital = next(d for d in discoveries if d.company_name == "Orbital AI")
    assert orbital.careers_url is not None
    assert "ashbyhq.com" in str(orbital.careers_url)


def test_auto_detects_story_via_algolia() -> None:
    story = _story_fixture()
    seen_urls: list[str] = []

    def fetch_json(url: str):
        seen_urls.append(url)
        if "items/" in url:
            return story
        return _ALGOLIA_SEARCH_RESPONSE

    adapter = HNHiringDiscoveryAdapter(fetch_json=fetch_json)
    # No story_id in params — should auto-detect via Algolia
    adapter.discover(_source(), _query())

    assert any("hn.algolia.com" in u and "search" in u for u in seen_urls)
    assert any(f"items/{_STORY_ID}" in u for u in seen_urls)


def test_uses_story_id_from_params_directly() -> None:
    story = _story_fixture()
    seen_urls: list[str] = []

    def fetch_json(url: str):
        seen_urls.append(url)
        return story

    adapter = HNHiringDiscoveryAdapter(fetch_json=fetch_json)
    adapter.discover(_source({"story_id": _STORY_ID}), _query())

    # Should skip Algolia search and go straight to the item
    assert all("search" not in u for u in seen_urls)
    assert any(f"items/{_STORY_ID}" in u for u in seen_urls)


def test_returns_empty_on_no_algolia_hits() -> None:
    def fetch_json(url: str):
        return {"hits": []}

    adapter = HNHiringDiscoveryAdapter(fetch_json=fetch_json)
    result = adapter.discover(_source(), _query())
    assert result == []


# --- _parse_comment unit tests ---

def test_parse_comment_extracts_company_and_role() -> None:
    text = "Acme Corp | Backend Engineer | Remote | Full-time<p>We build cool stuff. https://jobs.lever.co/acme"
    result = _parse_comment(text)
    assert result is not None
    assert result["company_name"] == "Acme Corp"
    assert result["job_title"] == "Backend Engineer"
    assert result["workplace_type"] == "remote"
    assert result["ats_url"] is not None
    assert "lever.co" in result["ats_url"]


def test_parse_comment_detects_remote_in_body() -> None:
    text = "SomeCo | SWE<p>Fully remote position. Apply at https://boards.greenhouse.io/someco"
    result = _parse_comment(text)
    assert result is not None
    assert result["workplace_type"] == "remote"


def test_parse_comment_skips_empty_text() -> None:
    assert _parse_comment("") is None
    assert _parse_comment("   ") is None


def test_parse_comment_skips_implausibly_long_company_name() -> None:
    long_name = "A" * 121
    result = _parse_comment(f"{long_name} | Engineer | Remote")
    assert result is None
