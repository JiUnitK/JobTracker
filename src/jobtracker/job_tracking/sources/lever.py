from __future__ import annotations

from typing import Any, Callable

from jobtracker.config.models import SourceDefinition
from jobtracker.models import RawJobPosting, SearchQuery
from jobtracker.job_tracking.sources.base import SourceAdapter
from jobtracker.job_tracking.sources.common import (
    display_name_from_token,
    extract_snippet,
    fetch_json,
    infer_workplace_type,
    matches_query,
)


FetchJson = Callable[[str], list[dict[str, Any]]]


class LeverAdapter(SourceAdapter):
    source_name = "lever"

    def __init__(self, fetch_json: FetchJson | None = None) -> None:
        self.fetch_json = fetch_json or fetch_json_default

    def collect(self, source: SourceDefinition, query: SearchQuery) -> list[RawJobPosting]:
        account_names = source.params.get("account_names", [])
        if not isinstance(account_names, list):
            raise ValueError("lever source params.account_names must be a list")

        collected: list[RawJobPosting] = []
        for account_name in account_names:
            payload = self.fetch_json(self.build_postings_url(account_name))
            collected.extend(self.parse_jobs(payload, account_name, query))
        return collected

    def build_postings_url(self, account_name: str) -> str:
        return f"https://api.lever.co/v0/postings/{account_name}?mode=json"

    def parse_jobs(
        self,
        payload: list[dict[str, Any]],
        account_name: str,
        query: SearchQuery,
    ) -> list[RawJobPosting]:
        jobs: list[RawJobPosting] = []
        company_name = display_name_from_token(account_name)
        for job_payload in payload:
            categories = job_payload.get("categories") or {}
            description = " ".join(
                filter(
                    None,
                    [
                        job_payload.get("descriptionPlain"),
                        job_payload.get("description"),
                        job_payload.get("listsPlain"),
                        job_payload.get("additionalPlain"),
                    ],
                )
            )
            raw_job = RawJobPosting(
                source=self.source_name,
                source_job_id=str(job_payload["id"]),
                source_url=job_payload["hostedUrl"],
                title=job_payload["text"],
                company_name=company_name,
                location_text=categories.get("location"),
                workplace_type=infer_workplace_type(
                    categories.get("commitment"),
                    categories.get("location"),
                    job_payload.get("workplaceType"),
                ),
                posted_at=None,
                description_snippet=extract_snippet(description),
                employment_type=categories.get("commitment"),
                seniority=categories.get("level"),
                raw_payload=job_payload,
                raw_tags=self._extract_tags(categories),
            )
            if matches_query(raw_job, query):
                jobs.append(raw_job)
        return jobs

    def _extract_tags(self, categories: dict[str, Any]) -> list[str]:
        tags: list[str] = []
        for key in ("team", "department", "location", "allLocations"):
            value = categories.get(key)
            if isinstance(value, list):
                tags.extend(str(item) for item in value if item)
            elif value:
                tags.append(str(value))
        return tags


def fetch_json_default(url: str) -> list[dict[str, Any]]:
    payload = fetch_json(url)
    if isinstance(payload, list):
        return payload
    raise ValueError("Lever postings response must be a list")
