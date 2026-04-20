from __future__ import annotations

import json
from pathlib import Path

import pytest

from jobtracker.config.models import CompanyDiscoverySourceDefinition
from jobtracker.company_discovery.remoteok_adapter import RemoteOKDiscoveryAdapter
from jobtracker.models import CompanyDiscoveryQuery


def _source(params: dict | None = None) -> CompanyDiscoverySourceDefinition:
    return CompanyDiscoverySourceDefinition(
        name="remote_ok",
        type="aggregator",
        enabled=True,
        params=params or {},
    )


def _query(**kwargs) -> CompanyDiscoveryQuery:
    defaults = dict(
        keywords=["software engineer", "backend engineer"],
        locations=["Remote"],
        workplace_types=["remote"],
    )
    return CompanyDiscoveryQuery(**(defaults | kwargs))


def _fixture_feed() -> list[dict]:
    return json.loads(
        (Path("tests/fixtures/remoteok_feed.json")).read_text(encoding="utf-8")
    )


def test_discovers_matching_companies_from_feed() -> None:
    feed = _fixture_feed()

    def fetch_json(url: str):
        return feed

    adapter = RemoteOKDiscoveryAdapter(fetch_json=fetch_json)
    discoveries = adapter.discover(_source(), _query())

    company_names = {d.company_name for d in discoveries}
    assert "Northwind Systems" in company_names
    assert "Pulse Labs" in company_names


def test_filters_out_non_engineering_roles() -> None:
    feed = _fixture_feed()

    def fetch_json(url: str):
        return feed

    adapter = RemoteOKDiscoveryAdapter(fetch_json=fetch_json)
    discoveries = adapter.discover(_source(), _query())

    assert "DesignCo" not in {d.company_name for d in discoveries}


def test_deduplicates_companies_within_feed() -> None:
    feed = _fixture_feed()

    def fetch_json(url: str):
        return feed

    adapter = RemoteOKDiscoveryAdapter(fetch_json=fetch_json)
    discoveries = adapter.discover(_source(), _query())

    names = [d.company_name for d in discoveries]
    assert names.count("Northwind Systems") == 1


def test_all_discoveries_are_remote() -> None:
    feed = _fixture_feed()

    def fetch_json(url: str):
        return feed

    adapter = RemoteOKDiscoveryAdapter(fetch_json=fetch_json)
    discoveries = adapter.discover(_source(), _query())

    assert all(d.workplace_type == "remote" for d in discoveries)
    assert all(d.location_text == "Remote" for d in discoveries)


def test_apply_url_mapped_to_careers_url() -> None:
    feed = _fixture_feed()

    def fetch_json(url: str):
        return feed

    adapter = RemoteOKDiscoveryAdapter(fetch_json=fetch_json)
    discoveries = adapter.discover(_source(), _query())

    northwind = next(d for d in discoveries if d.company_name == "Northwind Systems")
    assert northwind.careers_url is not None
    assert "lever.co" in str(northwind.careers_url)


def test_skips_workplace_type_mismatch() -> None:
    feed = _fixture_feed()

    def fetch_json(url: str):
        return feed

    adapter = RemoteOKDiscoveryAdapter(fetch_json=fetch_json)
    # Only onsite — should exclude all RemoteOK results
    discoveries = adapter.discover(_source(), _query(workplace_types=["onsite"]))

    assert discoveries == []


def test_uses_feed_url_from_params() -> None:
    seen_urls: list[str] = []

    def fetch_json(url: str):
        seen_urls.append(url)
        return [{"legal": "notice"}, {
            "id": "1",
            "company": "TestCo",
            "company_url": "https://testco.com",
            "url": "https://remoteok.com/remote-jobs/1",
            "position": "Backend Engineer",
            "tags": ["backend engineer"],
            "location": "Worldwide",
            "description": "Backend engineer role",
            "apply_url": "https://testco.com/jobs",
        }]

    adapter = RemoteOKDiscoveryAdapter(fetch_json=fetch_json)
    source = _source(params={"feed_url": "https://custom.example.com/api"})
    adapter.discover(source, _query())

    assert seen_urls == ["https://custom.example.com/api"]


def test_raises_on_non_list_response() -> None:
    def fetch_json(url: str):
        return {"error": "bad response"}

    adapter = RemoteOKDiscoveryAdapter(fetch_json=fetch_json)
    with pytest.raises(ValueError, match="must return a JSON array"):
        adapter.discover(_source(), _query())
