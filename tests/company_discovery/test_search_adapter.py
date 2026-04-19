from __future__ import annotations

import json
from pathlib import Path

from jobtracker.config.models import CompanyDiscoverySourceDefinition
from jobtracker.company_discovery.search_adapter import CompanySearchDiscoveryAdapter
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
