from __future__ import annotations

import html
import re
from typing import Any, Callable

from jobtracker.company_discovery.base import CompanyDiscoveryAdapter
from jobtracker.company_discovery.common import (
    fetch_json_url,
    text_matches_query,
    workplace_matches_query,
)
from jobtracker.config.models import CompanyDiscoverySourceDefinition
from jobtracker.models import CompanyDiscoveryQuery, RawCompanyDiscovery


_ALGOLIA_SEARCH_URL = (
    "https://hn.algolia.com/api/v1/search"
    "?query=Ask+HN%3A+Who+is+hiring"
    "&tags=story,ask_hn"
    "&numericFilters=points%3E50"
    "&hitsPerPage=5"
)
_ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items/{story_id}"
_HN_COMMENT_URL = "https://news.ycombinator.com/item?id={comment_id}"

_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://[^\s\"<>]+", re.IGNORECASE)
_SNIPPET_LIMIT = 280

_ATS_HOSTS = {
    "boards.greenhouse.io": "greenhouse",
    "job-boards.greenhouse.io": "greenhouse",
    "jobs.lever.co": "lever",
    "jobs.ashbyhq.com": "ashby",
}

FetchJson = Callable[[str], Any]


class HNHiringDiscoveryAdapter(CompanyDiscoveryAdapter):
    source_name = "hn_whos_hiring"

    def __init__(self, fetch_json: FetchJson | None = None) -> None:
        self.fetch_json = fetch_json or fetch_json_default

    def discover(
        self,
        source: CompanyDiscoverySourceDefinition,
        query: CompanyDiscoveryQuery,
    ) -> list[RawCompanyDiscovery]:
        story_id = self._resolve_story_id(source)
        if story_id is None:
            return []

        story = self.fetch_json(_ALGOLIA_ITEM_URL.format(story_id=story_id))
        comments: list[dict[str, Any]] = story.get("children") or []

        discoveries: list[RawCompanyDiscovery] = []
        seen_companies: set[str] = set()

        for comment in comments:
            raw_text = comment.get("text") or ""
            if not raw_text:
                continue

            parsed = _parse_comment(raw_text)
            if not parsed:
                continue

            company_name = parsed["company_name"]
            if not company_name:
                continue

            company_key = company_name.lower()
            if company_key in seen_companies:
                continue

            workplace_type = parsed["workplace_type"]
            if not workplace_matches_query(workplace_type, query.workplace_types):
                continue

            searchable = " ".join(filter(None, [
                company_name,
                parsed.get("job_title"),
                parsed.get("snippet"),
            ]))
            if not text_matches_query(searchable, query.keywords):
                continue

            comment_id = str(comment.get("id") or story_id)
            source_url = _HN_COMMENT_URL.format(comment_id=comment_id)

            seen_companies.add(company_key)
            discoveries.append(
                RawCompanyDiscovery(
                    source_name=source.name,
                    source_type=source.type,
                    source_url=source_url,
                    company_name=company_name,
                    company_url=parsed.get("company_url") or None,
                    careers_url=parsed.get("ats_url") or None,
                    job_title=parsed.get("job_title") or None,
                    location_text=parsed.get("location_text") or None,
                    workplace_type=workplace_type,  # type: ignore[arg-type]
                    evidence_kind="job_posting",
                    raw_payload={
                        "comment_id": comment_id,
                        "story_id": story_id,
                        "raw_text": raw_text[:1000],
                    },
                )
            )

        return discoveries

    def _resolve_story_id(self, source: CompanyDiscoverySourceDefinition) -> str | None:
        story_id = source.params.get("story_id")
        if story_id:
            return str(story_id)

        result = self.fetch_json(_ALGOLIA_SEARCH_URL)
        hits = result.get("hits") or []
        if not hits:
            return None
        # Most recent story is first hit when sorted by relevance + recency
        return str(hits[0].get("objectID") or "")


def _strip_html(text: str) -> str:
    unescaped = html.unescape(text)
    return _TAG_RE.sub(" ", unescaped)


def _parse_comment(raw_html: str) -> dict[str, Any] | None:
    text = _strip_html(raw_html)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None

    first_line = lines[0]
    fields = [f.strip() for f in first_line.split("|")]

    company_name = fields[0].strip() if fields else ""
    if not company_name or len(company_name) > 120:
        return None

    job_title: str | None = None
    location_text: str | None = None
    workplace_type = "unknown"

    # Scan pipe fields for role, location, remote signal
    for field in fields[1:]:
        low = field.lower()
        if "remote" in low:
            workplace_type = "remote"
            if location_text is None:
                location_text = field.strip()
        elif "hybrid" in low:
            if workplace_type == "unknown":
                workplace_type = "hybrid"
            if location_text is None:
                location_text = field.strip()
        elif _looks_like_location(field) and location_text is None:
            location_text = field.strip()
        elif _looks_like_role(field) and job_title is None:
            job_title = field.strip()

    # Also scan full text for remote/hybrid signal
    full_text = " ".join(lines)
    if workplace_type == "unknown":
        low_full = full_text.lower()
        if "remote" in low_full:
            workplace_type = "remote"
        elif "hybrid" in low_full:
            workplace_type = "hybrid"

    # Extract ATS URLs and the first non-ATS URL as company_url
    all_urls = _URL_RE.findall(full_text)
    ats_url: str | None = None
    company_url: str | None = None
    for url in all_urls:
        matched_ats = _match_ats_host(url)
        if matched_ats and ats_url is None:
            ats_url = url
        elif company_url is None and not matched_ats:
            company_url = url

    snippet = " ".join(full_text.split())[:_SNIPPET_LIMIT] or None

    return {
        "company_name": company_name,
        "job_title": job_title,
        "location_text": location_text,
        "workplace_type": workplace_type,
        "ats_url": ats_url,
        "company_url": company_url,
        "snippet": snippet,
    }


def _match_ats_host(url: str) -> str | None:
    for host, platform in _ATS_HOSTS.items():
        if host in url.lower():
            return platform
    return None


_ROLE_KEYWORDS = frozenset([
    "engineer", "developer", "programmer", "architect", "sre", "devops",
    "backend", "frontend", "fullstack", "full-stack", "full stack",
    "data", "ml", "ai", "platform", "infrastructure", "software",
])

_LOCATION_MARKERS = frozenset(["tx", "ny", "ca", "usa", "us", "uk", "eu", "remote"])


def _looks_like_role(field: str) -> bool:
    low = field.lower()
    return any(kw in low for kw in _ROLE_KEYWORDS)


def _looks_like_location(field: str) -> bool:
    low = field.strip().lower()
    if any(m in low for m in _LOCATION_MARKERS):
        return True
    # City, State pattern
    if re.search(r"\b[A-Z][a-z]+,\s*[A-Z]{2}\b", field):
        return True
    return False


def fetch_json_default(url: str) -> Any:
    return fetch_json_url(url)
