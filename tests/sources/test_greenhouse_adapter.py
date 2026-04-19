from __future__ import annotations

import json
from pathlib import Path

from jobtracker.config.models import SourceDefinition
from jobtracker.models import SearchQuery
from jobtracker.job_tracking.sources.greenhouse import GreenhouseAdapter


def test_greenhouse_adapter_parses_and_filters_jobs() -> None:
    fixture_path = Path("tests/fixtures/greenhouse_board.json")
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    adapter = GreenhouseAdapter(fetch_json=lambda _: payload)
    source = SourceDefinition(
        name="greenhouse",
        type="ats",
        reliability_tier="tier1",
        params={"board_tokens": ["exampleco"]},
    )
    query = SearchQuery(
        keywords=["backend engineer", "python"],
        locations=["Austin, TX", "Remote"],
        workplace_types=["remote", "hybrid", "onsite"],
    )

    jobs = adapter.collect(source, query)

    assert len(jobs) == 1
    assert jobs[0].source_job_id == "101"
    assert jobs[0].company_name == "Exampleco"
    assert jobs[0].employment_type == "Full-time"
    assert jobs[0].seniority == "Senior"
    assert jobs[0].raw_tags == ["Engineering", "Austin"]
