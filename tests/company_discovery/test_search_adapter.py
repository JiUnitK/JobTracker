from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request

import pytest

from jobtracker.company_discovery import search_adapter
from jobtracker.config.models import CompanyDiscoverySourceDefinition
from jobtracker.company_discovery.search_adapter import (
    CompanySearchDiscoveryAdapter,
    fetch_json_for_source,
)
from jobtracker.models import CompanyDiscoveryQuery


def test_company_search_adapter_filters_results_from_fixture() -> None:
    payload = json.loads((Path("tests/fixtures/company_search_results.json")).read_text(encoding="utf-8"))
    adapter = CompanySearchDiscoveryAdapter()
    source = CompanyDiscoverySourceDefinition(
        name="company_search",
        type="search",
        enabled=True,
        params={"results": payload},
    )
    query = CompanyDiscoveryQuery(
        keywords=["backend engineer", "software engineer"],
        locations=["Austin, TX", "Remote"],
        workplace_types=["hybrid", "remote"],
    )

    discoveries = adapter.discover(source, query)

    assert len(discoveries) == 1
    assert discoveries[0].company_name == "Pulse Labs"
    assert str(discoveries[0].careers_url) == "https://boards.greenhouse.io/pulselabs"


def test_company_search_adapter_fetches_results_from_url() -> None:
    payload = json.loads((Path("tests/fixtures/company_search_results.json")).read_text(encoding="utf-8"))
    adapter = CompanySearchDiscoveryAdapter(fetch_json=lambda url: payload)
    source = CompanyDiscoverySourceDefinition(
        name="company_search",
        type="search",
        enabled=True,
        params={"results_urls": ["https://example.com/company-search.json"]},
    )
    query = CompanyDiscoveryQuery(
        keywords=["backend engineer", "software engineer"],
        locations=["Austin, TX", "Remote"],
        workplace_types=["hybrid", "remote"],
    )

    discoveries = adapter.discover(source, query)

    assert len(discoveries) == 1
    assert discoveries[0].company_name == "Pulse Labs"


def test_company_search_adapter_rejects_invalid_fetched_payload() -> None:
    adapter = CompanySearchDiscoveryAdapter(fetch_json=lambda url: {"results": "not-a-list"})
    source = CompanyDiscoverySourceDefinition(
        name="company_search",
        type="search",
        enabled=True,
        params={"results_urls": ["https://example.com/company-search.json"]},
    )
    query = CompanyDiscoveryQuery(
        keywords=["backend engineer"],
        locations=["Austin, TX"],
        workplace_types=["hybrid"],
    )

    with pytest.raises(ValueError):
        adapter.discover(source, query)


def test_company_search_adapter_builds_query_urls_and_fetches_results() -> None:
    payload = json.loads((Path("tests/fixtures/company_search_results.json")).read_text(encoding="utf-8"))
    seen_urls: list[str] = []

    def fetch_json(url: str):
        seen_urls.append(url)
        return {"results": payload}

    adapter = CompanySearchDiscoveryAdapter(fetch_json=fetch_json)
    source = CompanyDiscoverySourceDefinition(
        name="company_search",
        type="search",
        enabled=True,
        params={
            "query_url_template": (
                "https://search.example.test?q={query}&keyword={keyword}&location={location}&workplace={workplace_type}"
            ),
            "results_payload_key": "results",
        },
    )
    query = CompanyDiscoveryQuery(
        keywords=["backend engineer"],
        locations=["Austin, TX"],
        workplace_types=["hybrid"],
    )

    discoveries = adapter.discover(source, query)

    assert len(discoveries) == 1
    assert discoveries[0].company_name == "Pulse Labs"
    assert seen_urls == [
        "https://search.example.test?q=backend+engineer+Austin%2C+TX+hybrid&keyword=backend+engineer&location=Austin%2C+TX&workplace=hybrid"
    ]


def test_company_search_adapter_normalizes_brave_web_results() -> None:
    adapter = CompanySearchDiscoveryAdapter(
        fetch_json=lambda url: {
            "web": {
                "results": [
                    {
                        "title": "Backend Engineer - Pulse Labs",
                        "url": "https://boards.greenhouse.io/pulselabs/jobs/1",
                        "description": "Remote Python role in Austin, TX",
                    }
                ]
            }
        }
    )
    source = CompanyDiscoverySourceDefinition(
        name="company_search",
        type="search",
        enabled=True,
        params={
            "query_url_template": "https://api.search.brave.com/res/v1/web/search?q={query}",
            "results_payload_key": "web.results",
            "api_key_env": "BRAVE_SEARCH_API_KEY",
        },
    )
    query = CompanyDiscoveryQuery(
        keywords=["backend engineer"],
        locations=["Austin, TX"],
        workplace_types=["remote"],
    )

    discoveries = adapter.discover(source, query)

    assert len(discoveries) == 1
    assert discoveries[0].company_name == "Pulse Labs"
    assert discoveries[0].workplace_type == "remote"
    assert discoveries[0].evidence_kind == "brave_web_result"


def test_company_search_source_requires_brave_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    source = CompanyDiscoverySourceDefinition(
        name="company_search",
        type="search",
        enabled=True,
        params={"api_key_env": "BRAVE_SEARCH_API_KEY"},
    )

    with pytest.raises(ValueError, match="BRAVE_SEARCH_API_KEY"):
        fetch_json_for_source("https://api.search.brave.com/res/v1/web/search?q=test", source)


def test_company_search_source_sends_brave_subscription_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self) -> bytes:
            return b'{"web": {"results": []}}'

    def fake_urlopen(request: Request, timeout: float):
        assert request.headers["X-subscription-token"] == "test-key"
        return Response()

    monkeypatch.setattr(search_adapter, "urlopen", fake_urlopen)
    source = CompanyDiscoverySourceDefinition(
        name="company_search",
        type="search",
        enabled=True,
        params={"api_key_env": "BRAVE_SEARCH_API_KEY"},
    )

    assert fetch_json_for_source(
        "https://api.search.brave.com/res/v1/web/search?q=test",
        source,
    ) == {"web": {"results": []}}
