from __future__ import annotations

import re
import time
import urllib.error
from dataclasses import dataclass
from typing import Callable
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from jobtracker.storage.orm import CompanyDiscoveryORM
from jobtracker.storage.repositories import CompanyResolutionRepository


_PROBE_TIMEOUT = 8.0
_INTER_PROBE_DELAY = 0.3

_PLATFORMS: list[tuple[str, str, str]] = [
    (
        "greenhouse",
        "ats_board",
        "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    ),
    (
        "lever",
        "ats_board",
        "https://api.lever.co/v0/postings/{slug}",
    ),
    (
        "ashby",
        "ats_board",
        "https://api.ashbyhq.com/posting-api/job-board/{slug}",
    ),
]

_BOARD_URLS = {
    "greenhouse": "https://boards.greenhouse.io/{slug}",
    "lever": "https://jobs.lever.co/{slug}",
    "ashby": "https://jobs.ashbyhq.com/{slug}",
}

_CONFIDENCE = 0.78


@dataclass(slots=True)
class FingerprintHit:
    platform: str
    slug: str
    board_url: str
    probe_url: str


ProbeHttp = Callable[[str], bool]


class ATSFingerprintingService:
    def __init__(
        self,
        session: Session,
        probe_http: ProbeHttp | None = None,
        inter_probe_delay: float = _INTER_PROBE_DELAY,
    ) -> None:
        self.session = session
        self._probe_http = probe_http or _probe_url_live
        self._delay = inter_probe_delay

    def fingerprint_unresolved(
        self,
        *,
        observed_at=None,
    ) -> dict[str, list[FingerprintHit]]:
        """Probe ATS platforms for every unresolved candidate discovery.

        Returns a mapping of normalized_name -> list of hits found.
        """
        from sqlalchemy import select

        unresolved = list(
            self.session.scalars(
                select(CompanyDiscoveryORM).where(
                    CompanyDiscoveryORM.resolution_status == "unresolved",
                    CompanyDiscoveryORM.discovery_status.notin_(["ignored", "archived"]),
                )
            )
        )

        results: dict[str, list[FingerprintHit]] = {}
        resolution_repo = CompanyResolutionRepository(self.session)

        for discovery in unresolved:
            hits = self._probe_company(discovery)
            if hits:
                results[discovery.normalized_name] = hits
                for hit in hits:
                    resolution_repo.upsert_candidate(
                        company_discovery_id=discovery.id,
                        resolution_type=hit.platform and "ats_board" or "company_url",
                        platform=hit.platform,
                        identifier=hit.slug,
                        url=hit.board_url,
                        confidence=_CONFIDENCE,
                        observed_at=observed_at,
                    )

        return results

    def _probe_company(self, discovery: CompanyDiscoveryORM) -> list[FingerprintHit]:
        slugs = _derive_slugs(discovery.normalized_name, discovery.display_name)
        hits: list[FingerprintHit] = []
        seen_slugs: set[tuple[str, str]] = set()

        for platform, resolution_type, probe_template in _PLATFORMS:
            for slug in slugs:
                key = (platform, slug)
                if key in seen_slugs:
                    continue
                seen_slugs.add(key)

                probe_url = probe_template.format(slug=slug)
                if self._delay:
                    time.sleep(self._delay)

                if self._probe_http(probe_url):
                    board_url = _BOARD_URLS[platform].format(slug=slug)
                    hits.append(
                        FingerprintHit(
                            platform=platform,
                            slug=slug,
                            board_url=board_url,
                            probe_url=probe_url,
                        )
                    )
                    break  # First slug hit per platform is enough

        return hits


def _derive_slugs(normalized_name: str, display_name: str | None) -> list[str]:
    """Generate slug candidates from normalized and display name."""
    candidates: list[str] = []

    # normalized_name is already lowercase and hyphenated: "cockroach-labs"
    if normalized_name:
        candidates.append(normalized_name)
        candidates.append(normalized_name.replace("-", ""))  # "cockroachlabs"

    if display_name:
        lowered = display_name.lower()
        no_spaces = re.sub(r"[^a-z0-9]+", "", lowered)        # "cockroachlabs"
        hyphenated = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")  # "cockroach-labs"
        candidates.append(no_spaces)
        candidates.append(hyphenated)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for slug in candidates:
        if slug and slug not in seen:
            seen.add(slug)
            unique.append(slug)
    return unique


def _probe_url_live(url: str) -> bool:
    """Return True if the URL responds with HTTP 200."""
    try:
        request = Request(
            url,
            headers={
                "User-Agent": "JobTracker/0.1.0 (+https://local.jobtracker)",
                "Accept": "application/json",
            },
        )
        with urlopen(request, timeout=_PROBE_TIMEOUT) as response:
            return response.status == 200
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return False
