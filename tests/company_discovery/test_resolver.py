from __future__ import annotations

from jobtracker.company_discovery.normalize import normalize_company_discovery
from jobtracker.company_discovery.resolution import infer_resolution_candidates
from jobtracker.models import RawCompanyDiscovery


def test_resolver_extracts_ranked_candidates_from_discovery_evidence() -> None:
    raw = RawCompanyDiscovery(
        source_name="company_search",
        source_type="search",
        source_url="https://example-search.com/results/pulse-labs",
        company_name="Pulse Labs",
        company_url="https://pulselabs.dev",
        careers_url="https://boards.greenhouse.io/pulselabs",
        job_url="https://boards.greenhouse.io/pulselabs/jobs/101",
        job_title="Backend Engineer",
        location_text="Austin, TX",
        workplace_type="hybrid",
        raw_payload={"snippet": "Backend role"},
    )

    candidates = infer_resolution_candidates(
        raw_discovery=raw,
        discovery=normalize_company_discovery(raw),
    )

    assert len(candidates) >= 3
    assert candidates[0].platform == "greenhouse"
    assert candidates[0].identifier == "pulselabs"
    assert any(candidate.platform == "direct" and candidate.identifier == "pulselabs" for candidate in candidates)


def test_resolver_infers_ats_from_source_url_pattern_without_careers_url() -> None:
    raw = RawCompanyDiscovery(
        source_name="company_search",
        source_type="ats_pattern",
        source_url="https://jobs.lever.co/orbitworks/7f2aa11d",
        company_name="OrbitWorks",
        job_title="Platform Engineer",
        location_text="Remote",
        workplace_type="remote",
        raw_payload={"snippet": "Infra role"},
    )

    candidates = infer_resolution_candidates(
        raw_discovery=raw,
        discovery=normalize_company_discovery(raw),
    )

    assert candidates
    assert candidates[0].platform == "lever"
    assert candidates[0].identifier == "orbitworks"
    assert candidates[0].resolution_type == "ats_board"
