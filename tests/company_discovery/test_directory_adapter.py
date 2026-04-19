from __future__ import annotations

import json
from pathlib import Path

from jobtracker.config.models import CompanyDiscoverySourceDefinition
from jobtracker.company_discovery.directory_adapter import CompanyDirectoryDiscoveryAdapter
from jobtracker.models import CompanyDiscoveryQuery


def test_company_directory_adapter_filters_entries_from_fixture() -> None:
    payload = json.loads(
        (Path("tests/fixtures/company_directory_entries.json")).read_text(encoding="utf-8")
    )
    adapter = CompanyDirectoryDiscoveryAdapter()
    source = CompanyDiscoverySourceDefinition(
        name="company_directory",
        type="ecosystem",
        enabled=True,
        params={"entries": payload},
    )
    query = CompanyDiscoveryQuery(
        keywords=["software engineer", "backend engineer"],
        locations=["Austin, TX", "Remote"],
        workplace_types=["hybrid", "remote"],
    )

    discoveries = adapter.discover(source, query)

    assert len(discoveries) == 2
    assert {item.company_name for item in discoveries} == {"Pulse Labs", "Northwind Systems"}


def test_company_directory_adapter_fetches_query_driven_entries() -> None:
    payload = {
        "entries": json.loads(
            (Path("tests/fixtures/company_directory_entries.json")).read_text(encoding="utf-8")
        )
    }
    seen_urls: list[str] = []

    def fetch_json(url: str):
        seen_urls.append(url)
        return payload

    adapter = CompanyDirectoryDiscoveryAdapter(fetch_json=fetch_json)
    source = CompanyDiscoverySourceDefinition(
        name="company_directory",
        type="ecosystem",
        enabled=True,
        params={
            "query_url_template": (
                "https://directory.example.test/search?q={query}&keyword={keyword}&location={location}&workplace={workplace_type}"
            ),
            "entries_payload_key": "entries",
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
        "https://directory.example.test/search?q=backend+engineer+Austin%2C+TX+hybrid&keyword=backend+engineer&location=Austin%2C+TX&workplace=hybrid"
    ]
