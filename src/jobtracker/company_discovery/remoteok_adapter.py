from __future__ import annotations

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


_DEFAULT_FEED_URL = "https://remoteok.com/api"
_SNIPPET_LIMIT = 280

FetchJson = Callable[[str], Any]


class RemoteOKDiscoveryAdapter(CompanyDiscoveryAdapter):
    source_name = "remote_ok"

    def __init__(self, fetch_json: FetchJson | None = None) -> None:
        self.fetch_json = fetch_json or fetch_json_default

    def discover(
        self,
        source: CompanyDiscoverySourceDefinition,
        query: CompanyDiscoveryQuery,
    ) -> list[RawCompanyDiscovery]:
        feed_url = str(source.params.get("feed_url") or _DEFAULT_FEED_URL)
        raw_entries = self._load_feed(feed_url)

        discoveries: list[RawCompanyDiscovery] = []
        seen_companies: set[str] = set()

        for entry in raw_entries:
            company_name = str(entry.get("company") or "").strip()
            if not company_name:
                continue

            # One discovery per company per run; first matching job wins.
            company_key = company_name.lower()
            if company_key in seen_companies:
                continue

            job_title = str(entry.get("position") or "").strip() or None
            tags: list[str] = [str(t) for t in (entry.get("tags") or []) if t]
            description = str(entry.get("description") or "")
            snippet = _extract_snippet(description)

            searchable = " ".join(filter(None, [company_name, job_title, snippet, " ".join(tags)]))
            if not text_matches_query(searchable, query.keywords):
                continue

            # All RemoteOK jobs are remote; skip location filter and force workplace
            if not workplace_matches_query("remote", query.workplace_types):
                continue

            apply_url = str(entry.get("apply_url") or "").strip() or None
            company_url = str(entry.get("company_url") or "").strip() or None
            source_url = str(entry.get("url") or "").strip()
            if not source_url:
                continue

            seen_companies.add(company_key)
            discoveries.append(
                RawCompanyDiscovery(
                    source_name=source.name,
                    source_type=source.type,
                    source_url=source_url,
                    company_name=company_name,
                    company_url=company_url or None,
                    careers_url=apply_url or None,
                    job_url=source_url,
                    job_title=job_title,
                    location_text="Remote",
                    workplace_type="remote",
                    evidence_kind="job_listing",
                    raw_payload=entry,
                )
            )

        return discoveries

    def _load_feed(self, feed_url: str) -> list[dict[str, Any]]:
        payload = self.fetch_json(feed_url)
        if not isinstance(payload, list):
            raise ValueError(f"RemoteOK feed at {feed_url} must return a JSON array")
        # First element is a metadata/legal object, not a job
        entries: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            if "company" not in item:
                continue
            entries.append(item)
        return entries


def _extract_snippet(text: str) -> str:
    stripped = re.sub(r"<[^>]+>", " ", text)
    flattened = " ".join(stripped.split())
    return flattened[:_SNIPPET_LIMIT]


def fetch_json_default(url: str) -> Any:
    return fetch_json_url(url)
