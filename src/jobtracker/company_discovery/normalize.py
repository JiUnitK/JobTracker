from __future__ import annotations

import re
from urllib.parse import urlparse

from jobtracker.models import NormalizedCompanyDiscovery, RawCompanyDiscovery


COMPANY_SUFFIX_PATTERN = re.compile(
    r"\b(incorporated|inc|llc|l\.l\.c|ltd|limited|corp|corporation|co|company)\b",
    re.IGNORECASE,
)


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", lowered)
    return normalized.strip("-") or "unknown"


def normalize_company_name(name: str) -> str:
    normalized = COMPANY_SUFFIX_PATTERN.sub("", name)
    normalized = re.sub(r"[,&./]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return slugify(normalized)


def normalize_company_discovery(discovery: RawCompanyDiscovery) -> NormalizedCompanyDiscovery:
    return NormalizedCompanyDiscovery(
        source_name=discovery.source_name,
        normalized_name=normalize_company_name(discovery.company_name),
        display_name=discovery.company_name.strip(),
        source_url=discovery.source_url,
        company_url=discovery.company_url,
        careers_url=discovery.careers_url,
        job_url=discovery.job_url,
        job_title=discovery.job_title,
        location_text=discovery.location_text,
        workplace_type=discovery.workplace_type,
        evidence_kind=discovery.evidence_kind,
    )


def infer_resolution_candidate(discovery: NormalizedCompanyDiscovery) -> dict[str, object] | None:
    candidate_url = str(discovery.careers_url or discovery.company_url or "")
    if not candidate_url:
        return None

    parsed = urlparse(candidate_url)
    hostname = (parsed.hostname or "").lower()
    platform = "direct"
    resolution_type = "company_url"
    identifier = parsed.path.strip("/") or hostname

    if "greenhouse" in hostname:
        platform = "greenhouse"
        resolution_type = "ats_board"
        identifier = parsed.path.strip("/") or hostname
    elif "lever.co" in hostname:
        platform = "lever"
        resolution_type = "ats_board"
        identifier = parsed.path.strip("/") or hostname
    elif "ashbyhq.com" in hostname:
        platform = "ashby"
        resolution_type = "ats_board"
        identifier = parsed.path.strip("/") or hostname

    return {
        "resolution_type": resolution_type,
        "platform": platform,
        "identifier": identifier,
        "url": candidate_url,
        "confidence": 0.8 if platform != "direct" else 0.6,
    }
