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


class AshbyAdapter(SourceAdapter):
    source_name = "ashby"

    def __init__(self, fetch_json: FetchJson | None = None) -> None:
        self.fetch_json = fetch_json or fetch_json_default

    def collect(self, source: SourceDefinition, query: SearchQuery) -> list[RawJobPosting]:
        job_board_names = source.params.get("job_board_names", [])
        if not isinstance(job_board_names, list):
            raise ValueError("ashby source params.job_board_names must be a list")

        collected: list[RawJobPosting] = []
        for board_name in job_board_names:
            payload = self.fetch_json(self.build_postings_url(board_name))
            collected.extend(self.parse_jobs(payload, board_name, query))
        return collected

    def build_postings_url(self, board_name: str) -> str:
        return (
            "https://api.ashbyhq.com/posting-api/job-board/"
            f"{board_name}?includeCompensation=true"
        )

    def parse_jobs(
        self,
        payload: dict[str, Any],
        board_name: str,
        query: SearchQuery,
    ) -> list[RawJobPosting]:
        jobs: list[RawJobPosting] = []
        company_name = display_name_from_token(board_name)
        for job_payload in payload.get("jobs", []):
            if not job_payload.get("isListed", True):
                continue
            compensation = job_payload.get("compensation") or {}
            salary_min, salary_max, currency = self._extract_salary(compensation)
            raw_job = RawJobPosting(
                source=self.source_name,
                source_job_id=str(job_payload.get("id") or job_payload["jobUrl"]),
                source_url=job_payload["jobUrl"],
                title=job_payload["title"],
                company_name=company_name,
                location_text=job_payload.get("location"),
                workplace_type=infer_workplace_type(
                    job_payload.get("workplaceType"),
                    "remote" if job_payload.get("isRemote") else None,
                    job_payload.get("location"),
                ),
                posted_at=parse_datetime(job_payload.get("publishedAt")),
                description_snippet=extract_snippet(job_payload.get("descriptionPlain")),
                employment_type=job_payload.get("employmentType"),
                seniority=job_payload.get("team"),
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=currency,
                raw_payload=job_payload,
                raw_tags=self._extract_tags(job_payload),
            )
            if matches_query(raw_job, query):
                jobs.append(raw_job)
        return jobs

    def _extract_salary(self, compensation: dict[str, Any]) -> tuple[int | None, int | None, str | None]:
        for component in compensation.get("summaryComponents", []):
            if component.get("compensationType") != "Salary":
                continue
            min_value = component.get("minValue")
            max_value = component.get("maxValue")
            currency = component.get("currencyCode")
            return (
                int(min_value) if min_value is not None else None,
                int(max_value) if max_value is not None else None,
                str(currency) if currency else None,
            )
        return None, None, None

    def _extract_tags(self, payload: dict[str, Any]) -> list[str]:
        tags: list[str] = []
        for key in ("department", "team", "location", "workplaceType"):
            value = payload.get(key)
            if value:
                tags.append(str(value))
        return tags


def fetch_json_default(url: str) -> dict[str, Any]:
    return fetch_json(url)
