from __future__ import annotations

import json
from pathlib import Path

from jobtracker.config.models import SourceDefinition
from jobtracker.models import SearchQuery
from jobtracker.job_tracking.sources.ashby import AshbyAdapter


def test_ashby_adapter_parses_and_filters_jobs() -> None:
    fixture_path = Path("tests/fixtures/ashby_jobs.json")
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    adapter = AshbyAdapter(fetch_json=lambda _: payload)
    source = SourceDefinition(
        name="ashby",
        type="ats",
        reliability_tier="tier1",
        params={"job_board_names": ["ExampleCo"]},
    )
    query = SearchQuery(
        keywords=["backend", "python"],
        locations=["Austin, TX", "Remote", "United States"],
        workplace_types=["remote", "hybrid", "onsite"],
    )

    jobs = adapter.collect(source, query)

    assert len(jobs) == 1
    assert jobs[0].source_job_id == "ash-001"
    assert jobs[0].company_name == "Exampleco"
    assert jobs[0].employment_type == "FullTime"
    assert jobs[0].salary_min == 160000
    assert jobs[0].salary_currency == "USD"
