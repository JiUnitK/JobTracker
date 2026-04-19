from __future__ import annotations

from typing import Any, Callable

from jobtracker.config.models import SourceDefinition
from jobtracker.models import RawJobPosting, SearchQuery
from jobtracker.sources.base import SourceAdapter
from jobtracker.sources.common import (
    display_name_from_token,
    extract_snippet,
    fetch_json,
    infer_workplace_type,
    matches_query,
    parse_datetime,
)


FetchJson = Callable[[str], dict[str, Any]]


class GreenhouseAdapter(SourceAdapter):
    source_name = "greenhouse"

    def __init__(self, fetch_json: FetchJson | None = None) -> None:
        self.fetch_json = fetch_json or fetch_json_default

    def collect(self, source: SourceDefinition, query: SearchQuery) -> list[RawJobPosting]:
        board_tokens = source.params.get("board_tokens", [])
        if not isinstance(board_tokens, list):
            raise ValueError("greenhouse source params.board_tokens must be a list")

        collected: list[RawJobPosting] = []
        for board_token in board_tokens:
            payload = self.fetch_json(self.build_board_url(board_token))
            collected.extend(self.parse_jobs(payload, board_token, query))
        return collected

    def build_board_url(self, board_token: str) -> str:
        return f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"

    def parse_jobs(
        self,
        payload: dict[str, Any],
        board_token: str,
        query: SearchQuery,
    ) -> list[RawJobPosting]:
        jobs: list[RawJobPosting] = []
        company_name = display_name_from_token(board_token)
        for job_payload in payload.get("jobs", []):
            raw_job = RawJobPosting(
                source=self.source_name,
                source_job_id=str(job_payload["id"]),
                source_url=job_payload["absolute_url"],
                title=job_payload["title"],
                company_name=company_name,
                location_text=(job_payload.get("location") or {}).get("name"),
                workplace_type=infer_workplace_type(
                    " ".join(str(item.get("value", "")) for item in job_payload.get("metadata", [])),
                    (job_payload.get("location") or {}).get("name"),
                ),
                posted_at=parse_datetime(job_payload.get("updated_at")),
                description_snippet=extract_snippet(job_payload.get("content")),
                employment_type=self._extract_metadata_value(job_payload, "Employment Type"),
                seniority=self._extract_metadata_value(job_payload, "Experience Level"),
                raw_payload=job_payload,
                raw_tags=self._extract_tags(job_payload),
            )
            if matches_query(raw_job, query):
                jobs.append(raw_job)
        return jobs

    def _extract_metadata_value(self, payload: dict[str, Any], name: str) -> str | None:
        for item in payload.get("metadata", []):
            if item.get("name") == name and item.get("value"):
                return str(item["value"])
        return None

    def _extract_tags(self, payload: dict[str, Any]) -> list[str]:
        tags: list[str] = []
        for key in ("departments", "offices"):
            for item in payload.get(key, []):
                name = item.get("name")
                if name:
                    tags.append(str(name))
        return tags


def fetch_json_default(url: str) -> dict[str, Any]:
    return fetch_json(url)
