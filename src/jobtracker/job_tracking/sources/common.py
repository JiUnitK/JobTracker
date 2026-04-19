from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.request import Request, urlopen

from jobtracker.models import RawJobPosting, SearchQuery


def fetch_json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "JobTracker/0.1",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def display_name_from_token(token: str) -> str:
    words = token.replace("-", " ").replace("_", " ").split()
    return " ".join(word.capitalize() for word in words) or token


def infer_workplace_type(*values: str | None) -> str:
    searchable = " ".join(value or "" for value in values).lower()
    if "remote" in searchable:
        return "remote"
    if "hybrid" in searchable:
        return "hybrid"
    if searchable.strip():
        return "onsite"
    return "unknown"


def extract_snippet(content: str | None, limit: int = 280) -> str | None:
    if not content:
        return None
    flattened = " ".join(content.replace("\r", " ").replace("\n", " ").split())
    return flattened[:limit] if flattened else None


def matches_query(raw_job: RawJobPosting, query: SearchQuery) -> bool:
    searchable = " ".join(
        filter(
            None,
            [
                raw_job.title.lower(),
                (raw_job.location_text or "").lower(),
                (raw_job.description_snippet or "").lower(),
                " ".join(tag.lower() for tag in raw_job.raw_tags),
            ],
        )
    )
    keyword_match = any(keyword.lower() in searchable for keyword in query.keywords)
    if not keyword_match:
        return False

    if query.locations:
        location_match = any(location.lower() in searchable for location in query.locations)
        if not location_match and raw_job.workplace_type != "remote":
            return False

    if query.workplace_types and raw_job.workplace_type not in query.workplace_types:
        return False

    return True
