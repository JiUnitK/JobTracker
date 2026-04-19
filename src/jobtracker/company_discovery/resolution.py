from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse

from jobtracker.models import NormalizedCompanyDiscovery, RawCompanyDiscovery


ATS_PLATFORMS = {"greenhouse", "lever", "ashby"}
CAREERS_PATH_PATTERN = re.compile(r"(careers?|jobs?|openings?)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ResolutionCandidate:
    resolution_type: str
    platform: str
    identifier: str
    url: str
    confidence: float

    def as_dict(self) -> dict[str, object]:
        return {
            "resolution_type": self.resolution_type,
            "platform": self.platform,
            "identifier": self.identifier,
            "url": self.url,
            "confidence": self.confidence,
        }


def infer_resolution_candidate(discovery: NormalizedCompanyDiscovery) -> dict[str, object] | None:
    candidates = infer_resolution_candidates(
        raw_discovery=None,
        discovery=discovery,
    )
    return candidates[0].as_dict() if candidates else None


def infer_resolution_candidates(
    *,
    raw_discovery: RawCompanyDiscovery | None,
    discovery: NormalizedCompanyDiscovery,
) -> list[ResolutionCandidate]:
    candidates: dict[tuple[str, str], ResolutionCandidate] = {}
    ordered_urls = [
        ("careers_url", str(discovery.careers_url or "")),
        ("job_url", str(discovery.job_url or "")),
        ("company_url", str(discovery.company_url or "")),
        ("source_url", str(discovery.source_url or "")),
    ]
    if raw_discovery is not None:
        ordered_urls.extend(
            [
                ("careers_url", str(raw_discovery.careers_url or "")),
                ("job_url", str(raw_discovery.job_url or "")),
                ("company_url", str(raw_discovery.company_url or "")),
                ("source_url", str(raw_discovery.source_url or "")),
            ]
        )

    for url_source, url in ordered_urls:
        candidate = _candidate_from_url(url, url_source=url_source)
        if candidate is None:
            continue
        key = (candidate.resolution_type, candidate.url)
        existing = candidates.get(key)
        if existing is None or candidate.confidence > existing.confidence:
            candidates[key] = candidate

    ranked = sorted(
        candidates.values(),
        key=lambda item: (_platform_rank(item.platform), item.confidence, item.url),
        reverse=True,
    )
    return ranked


def _candidate_from_url(url: str, *, url_source: str) -> ResolutionCandidate | None:
    cleaned = url.strip()
    if not cleaned:
        return None

    parsed = urlparse(cleaned)
    hostname = (parsed.hostname or "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]
    resolution_type = "company_url"
    platform = "direct"
    identifier = _direct_identifier(hostname)
    confidence = _base_confidence(url_source=url_source, platform=platform, path=parsed.path)

    if "greenhouse" in hostname:
        platform = "greenhouse"
        resolution_type = "ats_board"
        identifier = _first_relevant_segment(path_parts, fallback=identifier)
        confidence = _base_confidence(url_source=url_source, platform=platform, path=parsed.path)
    elif "lever.co" in hostname:
        platform = "lever"
        resolution_type = "ats_board"
        identifier = _first_relevant_segment(path_parts, fallback=identifier)
        confidence = _base_confidence(url_source=url_source, platform=platform, path=parsed.path)
    elif "ashbyhq.com" in hostname:
        platform = "ashby"
        resolution_type = "ats_board"
        identifier = _first_relevant_segment(path_parts, fallback=identifier)
        confidence = _base_confidence(url_source=url_source, platform=platform, path=parsed.path)
    else:
        if _looks_like_careers_surface(hostname, parsed.path):
            resolution_type = "careers_page"
            confidence = _base_confidence(url_source=url_source, platform=platform, path=parsed.path)

    return ResolutionCandidate(
        resolution_type=resolution_type,
        platform=platform,
        identifier=identifier,
        url=cleaned,
        confidence=round(confidence, 2),
    )


def _base_confidence(*, url_source: str, platform: str, path: str) -> float:
    if platform in ATS_PLATFORMS:
        by_source = {
            "careers_url": 0.94,
            "job_url": 0.92,
            "source_url": 0.86,
            "company_url": 0.8,
        }
        confidence = by_source.get(url_source, 0.8)
        if "/jobs/" in path.lower():
            confidence += 0.02
        return min(confidence, 0.98)

    if _looks_like_careers_surface("", path):
        by_source = {
            "careers_url": 0.72,
            "job_url": 0.66,
            "source_url": 0.58,
            "company_url": 0.62,
        }
        return by_source.get(url_source, 0.6)

    by_source = {
        "company_url": 0.55,
        "source_url": 0.48,
        "careers_url": 0.62,
        "job_url": 0.52,
    }
    return by_source.get(url_source, 0.5)


def _looks_like_careers_surface(hostname: str, path: str) -> bool:
    lowered_host = hostname.lower()
    lowered_path = path.lower()
    return (
        lowered_host.startswith("jobs.")
        or lowered_host.startswith("careers.")
        or bool(CAREERS_PATH_PATTERN.search(lowered_path))
    )


def _first_relevant_segment(parts: list[str], *, fallback: str) -> str:
    ignored = {"jobs", "job", "boards", "board", "posting-api", "job-board"}
    for part in parts:
        cleaned = part.strip()
        if cleaned and cleaned.lower() not in ignored:
            return cleaned
    return fallback


def _direct_identifier(hostname: str) -> str:
    host = hostname.lower()
    for prefix in ("www.", "jobs.", "careers."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    root = host.split(".")[0] if host else "unknown"
    return root or "unknown"


def _platform_rank(platform: str) -> tuple[int, int]:
    if platform in ATS_PLATFORMS:
        return (2, 0)
    if platform == "direct":
        return (1, 0)
    return (0, 0)
