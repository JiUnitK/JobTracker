from __future__ import annotations

import json
from pathlib import Path

from jobtracker.config.models import CompanyDiscoverySourceDefinition
from jobtracker.company_discovery.ecosystem_adapter import AustinEcosystemDiscoveryAdapter
from jobtracker.models import CompanyDiscoveryQuery


def test_austin_ecosystem_adapter_filters_entries_from_fixture() -> None:
    payload = json.loads(
        (Path("tests/fixtures/austin_ecosystem_entries.json")).read_text(encoding="utf-8")
    )
    adapter = AustinEcosystemDiscoveryAdapter()
    source = CompanyDiscoverySourceDefinition(
        name="austin_ecosystem",
        type="ecosystem",
        enabled=True,
        params={"entries": payload},
    )
    query = CompanyDiscoveryQuery(
        keywords=["software engineer", "backend engineer"],
        locations=["Austin, TX"],
        workplace_types=["hybrid", "remote"],
    )

    discoveries = adapter.discover(source, query)

    assert len(discoveries) == 2
    assert {item.company_name for item in discoveries} == {"Pulse Labs", "Lakeside Robotics"}
