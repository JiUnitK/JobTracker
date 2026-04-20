from __future__ import annotations

import pytest

from jobtracker.company_discovery.fingerprinting import (
    ATSFingerprintingService,
    _derive_slugs,
)
from jobtracker.storage.orm import CompanyDiscoveryORM


# --- _derive_slugs unit tests ---

def test_derive_slugs_from_hyphenated_normalized_name() -> None:
    slugs = _derive_slugs("cockroach-labs", "Cockroach Labs")
    assert "cockroachlabs" in slugs
    assert "cockroach-labs" in slugs


def test_derive_slugs_deduplicates() -> None:
    slugs = _derive_slugs("linear", "Linear")
    assert slugs.count("linear") == 1


def test_derive_slugs_handles_multi_word() -> None:
    slugs = _derive_slugs("wp-engine", "WP Engine")
    assert "wpengine" in slugs
    assert "wp-engine" in slugs


def test_derive_slugs_strips_special_chars() -> None:
    slugs = _derive_slugs("q2-holdings", "Q2 Holdings")
    assert all(slug.replace("-", "").isalnum() for slug in slugs)


# --- ATSFingerprintingService integration tests (mocked HTTP) ---

def _make_discovery(normalized_name: str, display_name: str) -> CompanyDiscoveryORM:
    d = CompanyDiscoveryORM()
    d.id = 1
    d.normalized_name = normalized_name
    d.display_name = display_name
    d.resolution_status = "unresolved"
    d.discovery_status = "candidate"
    return d


class _MockSession:
    """Minimal session stub for fingerprinting tests.

    Tracks added objects so that refresh_resolution_state can retrieve
    newly created CompanyResolutionORM rows via scalars().
    """

    def __init__(self, discoveries: list[CompanyDiscoveryORM]) -> None:
        self._discoveries = discoveries
        self._added: list[object] = []
        self.flushed: int = 0

    def scalars(self, stmt):
        from jobtracker.storage.orm import CompanyResolutionORM
        # Distinguish by what was added: if resolutions were added, return them;
        # otherwise return discoveries (for the initial unresolved query).
        added_resolutions = [o for o in self._added if isinstance(o, CompanyResolutionORM)]
        if added_resolutions:
            return iter(added_resolutions)
        return iter(self._discoveries)

    def get(self, model, pk):
        return next((d for d in self._discoveries if d.id == pk), None)

    def add(self, obj) -> None:
        self._added.append(obj)

    def flush(self) -> None:
        self.flushed += 1

    def scalar(self, _stmt):
        return None  # upsert_candidate always creates new


def test_fingerprint_finds_hit_and_upserts_candidate() -> None:
    discovery = _make_discovery("linear", "Linear")
    session = _MockSession([discovery])

    probed: list[str] = []

    def probe(url: str) -> bool:
        probed.append(url)
        # Simulate Ashby hit for "linear"
        return "ashby" in url and "linear" in url

    service = ATSFingerprintingService(session, probe_http=probe, inter_probe_delay=0)
    results = service.fingerprint_unresolved()

    assert "linear" in results
    hits = results["linear"]
    assert any(h.platform == "ashby" for h in hits)
    assert any("linear" in h.slug for h in hits)


def test_fingerprint_skips_no_hit() -> None:
    discovery = _make_discovery("unknownco", "UnknownCo")
    session = _MockSession([discovery])

    def probe(url: str) -> bool:
        return False

    service = ATSFingerprintingService(session, probe_http=probe, inter_probe_delay=0)
    results = service.fingerprint_unresolved()

    assert results == {}


def test_fingerprint_skips_ignored_companies() -> None:
    discovery = _make_discovery("ignoredco", "IgnoredCo")
    discovery.discovery_status = "ignored"
    # Session won't return it because the WHERE clause filters it
    # Simulate by returning empty list
    session = _MockSession([])

    probed: list[str] = []

    def probe(url: str) -> bool:
        probed.append(url)
        return True

    service = ATSFingerprintingService(session, probe_http=probe, inter_probe_delay=0)
    service.fingerprint_unresolved()

    assert probed == []


def test_fingerprint_tries_each_platform() -> None:
    discovery = _make_discovery("testco", "TestCo")
    session = _MockSession([discovery])

    probed_platforms: list[str] = []

    def probe(url: str) -> bool:
        if "greenhouse" in url:
            probed_platforms.append("greenhouse")
        elif "lever" in url:
            probed_platforms.append("lever")
        elif "ashby" in url:
            probed_platforms.append("ashby")
        return False

    service = ATSFingerprintingService(session, probe_http=probe, inter_probe_delay=0)
    service.fingerprint_unresolved()

    assert "greenhouse" in probed_platforms
    assert "lever" in probed_platforms
    assert "ashby" in probed_platforms


def test_fingerprint_stops_at_first_slug_hit_per_platform() -> None:
    discovery = _make_discovery("cockroach-labs", "Cockroach Labs")
    session = _MockSession([discovery])

    greenhouse_probes: list[str] = []

    def probe(url: str) -> bool:
        if "greenhouse" in url:
            greenhouse_probes.append(url)
            return True  # Hit on first slug
        return False

    service = ATSFingerprintingService(session, probe_http=probe, inter_probe_delay=0)
    service.fingerprint_unresolved()

    # Should stop after first Greenhouse hit, not try all slug variants
    assert len(greenhouse_probes) == 1
