from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from jobtracker.config.models import InstantSearchSourceDefinition
from jobtracker.job_search import brave_adapter
from jobtracker.job_search.brave_adapter import (
    BraveSearchError,
    BraveSearchAdapter,
    build_brave_search_url,
    fetch_brave_json,
    parse_brave_results,
)
from jobtracker.job_search.models import InstantJobSearchQuery


FIXTURES_DIR = Path(__file__).parents[1] / "fixtures"


def _source() -> InstantSearchSourceDefinition:
    return InstantSearchSourceDefinition(
        name="brave_search",
        type="search",
        base_url="https://api.search.brave.com/res/v1/web/search",
        params={"count": 10, "country": "US", "search_lang": "en"},
    )


def _load_fixture(name: str):
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_build_brave_search_url_includes_configured_params() -> None:
    url = build_brave_search_url(_source(), '"customer success" Remote job')

    assert "q=%22customer+success%22+Remote+job" in url
    assert "count=10" in url
    assert "country=US" in url
    assert "search_lang=en" in url


def test_build_brave_search_url_uses_safe_defaults_and_clamps_count() -> None:
    source = InstantSearchSourceDefinition(
        name="brave_search",
        type="search",
        base_url="https://api.search.brave.com/res/v1/web/search",
        params={"count": 500},
    )

    url = build_brave_search_url(source, "backend engineer")

    assert "count=50" in url
    assert "country=US" in url
    assert "search_lang=en" in url
    assert "safesearch=moderate" in url


def test_parse_brave_results_converts_success_fixture() -> None:
    results = parse_brave_results(_load_fixture("brave_search_success.json"))

    assert len(results) == 2
    assert results[0].title == "Customer Success Specialist - Example Health"
    assert str(results[0].url) == "https://example.com/jobs/1"
    assert results[0].age_text == "2 days ago"
    assert results[0].source_id == "Example Health Careers"
    assert results[1].published_at is not None


def test_parse_brave_results_handles_empty_fixture() -> None:
    assert parse_brave_results(_load_fixture("brave_search_empty.json")) == []


def test_parse_brave_results_rejects_malformed_fixture() -> None:
    with pytest.raises(ValueError, match="web.results"):
        parse_brave_results(_load_fixture("brave_search_malformed.json"))


def test_parse_brave_results_rejects_non_object_web_payload() -> None:
    with pytest.raises(ValueError, match="web must be an object"):
        parse_brave_results({"web": []})


def test_brave_adapter_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    adapter = BraveSearchAdapter(fetch_json=lambda url, key, timeout: {})

    with pytest.raises(ValueError, match="BRAVE_SEARCH_API_KEY"):
        adapter.search(_source(), InstantJobSearchQuery(query="customer success"))


def test_brave_adapter_uses_injected_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")

    def fetch_json(url: str, key: str, timeout: float):
        assert key == "test-key"
        assert "customer+success" in url
        return {
            "web": {
                "results": [
                    {
                        "title": "Customer Success Specialist",
                        "url": "https://example.com/jobs/1",
                    }
                ]
            }
        }

    adapter = BraveSearchAdapter(fetch_json=fetch_json)

    results = adapter.search(_source(), InstantJobSearchQuery(query="customer success"))

    assert len(results) == 1


def test_fetch_brave_json_sends_subscription_token(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self) -> bytes:
            return b'{"web": {"results": []}}'

    def fake_urlopen(request, timeout: float):
        assert request.headers["X-subscription-token"] == "test-key"
        assert timeout == 3.5
        return Response()

    monkeypatch.setattr(brave_adapter, "urlopen", fake_urlopen)

    assert fetch_brave_json("https://example.com/search?q=test", "test-key", 3.5) == {
        "web": {"results": []}
    }


def test_fetch_brave_json_wraps_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout: float):
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {},
            BytesIO(b'{"message": "invalid api key"}'),
        )

    monkeypatch.setattr(brave_adapter, "urlopen", fake_urlopen)

    with pytest.raises(BraveSearchError, match="HTTP 401: invalid api key"):
        fetch_brave_json("https://example.com/search?q=test", "bad-key", 15)


def test_fetch_brave_json_wraps_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout: float):
        raise URLError("temporary failure")

    monkeypatch.setattr(brave_adapter, "urlopen", fake_urlopen)

    with pytest.raises(BraveSearchError, match="temporary failure"):
        fetch_brave_json("https://example.com/search?q=test", "test-key", 15)


def test_fetch_brave_json_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self) -> bytes:
            return b"not-json"

    monkeypatch.setattr(brave_adapter, "urlopen", lambda request, timeout: Response())

    with pytest.raises(BraveSearchError, match="not valid JSON"):
        fetch_brave_json("https://example.com/search?q=test", "test-key", 15)
