from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from jobtracker.job_search.models import (
    AgeConfidence,
    InstantJobSearchResult,
    RawInstantSearchResult,
)
from jobtracker.models import WorkplaceType


RELATIVE_AGE_RE = re.compile(r"\b(\d+)\s+(day|days|week|weeks|month|months)\s+ago\b", re.IGNORECASE)


def normalize_instant_search_result(
    raw: RawInstantSearchResult,
    *,
    now: datetime | None = None,
) -> InstantJobSearchResult:
    now = _aware_utc(now or datetime.now(timezone.utc))
    searchable = " ".join([raw.title, raw.snippet or "", raw.age_text or ""])
    age_days, age_text, confidence = classify_age(searchable, raw.published_at, now=now)
    title, company = split_title_company(raw.title)
    location = infer_location(searchable)
    workplace_type = infer_workplace_type(searchable)

    return InstantJobSearchResult(
        title=title,
        company=company,
        location=location,
        workplace_type=workplace_type,
        url=raw.url,
        snippet=raw.snippet,
        posted_at=raw.published_at,
        age_days=age_days,
        age_text=age_text or raw.age_text,
        age_confidence=confidence,
        source_provider=raw.provider,
        source_id=raw.source_id,
    )


def classify_age(
    text: str,
    published_at: datetime | None,
    *,
    now: datetime,
) -> tuple[int | None, str | None, AgeConfidence]:
    if published_at is not None:
        age_days = max((_aware_utc(now) - _aware_utc(published_at)).days, 0)
        return age_days, f"{age_days} days old", "high"

    match = RELATIVE_AGE_RE.search(text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()
        multiplier = 1 if unit.startswith("day") else 7 if unit.startswith("week") else 30
        age_days = amount * multiplier
        return age_days, match.group(0), "medium"

    lower_text = text.lower()
    if "today" in lower_text or "just posted" in lower_text or "new listing" in lower_text:
        return 0, "today", "low"
    if "yesterday" in lower_text:
        return 1, "yesterday", "low"
    return None, None, "unknown"


def split_title_company(title: str) -> tuple[str, str | None]:
    for separator in [" | ", " - ", " at "]:
        if separator in title:
            left, right = title.split(separator, 1)
            left = left.strip()
            right = right.strip()
            if left and right:
                if separator == " at ":
                    return left, right
                return left, right
    return title.strip(), None


def infer_workplace_type(text: str) -> WorkplaceType:
    lower_text = text.lower()
    if "remote" in lower_text:
        return "remote"
    if "hybrid" in lower_text:
        return "hybrid"
    if "on-site" in lower_text or "onsite" in lower_text:
        return "onsite"
    return "unknown"


def infer_location(text: str) -> str | None:
    if "remote" in text.lower():
        return "Remote"
    return None


def canonical_result_key(result: InstantJobSearchResult) -> str:
    parsed = urlparse(str(result.url))
    return f"{parsed.netloc.lower()}{parsed.path.rstrip('/').lower()}"


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

