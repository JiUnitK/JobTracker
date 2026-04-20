from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlparse

from jobtracker.job_search.models import (
    AgeConfidence,
    InstantJobSearchResult,
    RawInstantSearchResult,
)
from jobtracker.models import WorkplaceType


RELATIVE_AGE_RE = re.compile(
    r"\b(\d+\+?)\s+(hour|hours|day|days|week|weeks|month|months)\s+ago\b",
    re.IGNORECASE,
)
ISO_DATE_RE = re.compile(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b")
US_DATE_RE = re.compile(r"\b(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])/(20\d{2})\b")
MONTH_DATE_RE = re.compile(
    r"\b("
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|sept|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    r")\.?\s+([0-3]?\d)(?:,)?\s+(20\d{2})\b",
    re.IGNORECASE,
)
URL_DATE_KEYS = ["posted", "posted_at", "date", "created", "created_at", "published", "published_at"]
MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def normalize_instant_search_result(
    raw: RawInstantSearchResult,
    *,
    now: datetime | None = None,
) -> InstantJobSearchResult:
    now = _aware_utc(now or datetime.now(timezone.utc))
    searchable = " ".join([raw.title, raw.snippet or "", raw.age_text or "", str(raw.url)])
    age_days, age_text, confidence = classify_age(
        searchable,
        raw.published_at,
        url=str(raw.url),
        now=now,
    )
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
    url: str | None = None,
    now: datetime,
) -> tuple[int | None, str | None, AgeConfidence]:
    if published_at is not None:
        age_days = max((_aware_utc(now) - _aware_utc(published_at)).days, 0)
        return age_days, _age_days_text(age_days), "high"

    match = RELATIVE_AGE_RE.search(text)
    if match:
        amount_text = match.group(1)
        amount = int(amount_text.rstrip("+"))
        unit = match.group(2).lower()
        if unit.startswith("hour"):
            return 0, match.group(0), "medium"
        multiplier = 1 if unit.startswith("day") else 7 if unit.startswith("week") else 30
        age_days = amount * multiplier
        confidence: AgeConfidence = "low" if amount_text.endswith("+") else "medium"
        return age_days, match.group(0), confidence

    lower_text = text.lower()
    if "today" in lower_text or "just posted" in lower_text or "new listing" in lower_text:
        return 0, "today", "low"
    if "yesterday" in lower_text:
        return 1, "yesterday", "low"

    explicit_date = _find_explicit_date(text)
    if explicit_date is not None:
        age_days = max((_aware_utc(now) - explicit_date).days, 0)
        return age_days, explicit_date.date().isoformat(), "medium"

    url_date = _find_url_date(url or text)
    if url_date is not None:
        age_days = max((_aware_utc(now) - url_date).days, 0)
        return age_days, url_date.date().isoformat(), "low"

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


def _find_explicit_date(text: str) -> datetime | None:
    for match in ISO_DATE_RE.finditer(text):
        parsed = _safe_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if parsed is not None:
            return parsed
    for match in US_DATE_RE.finditer(text):
        parsed = _safe_date(int(match.group(3)), int(match.group(1)), int(match.group(2)))
        if parsed is not None:
            return parsed
    for match in MONTH_DATE_RE.finditer(text):
        month_name = match.group(1).lower().rstrip(".")
        month = MONTHS.get(month_name)
        if month is None:
            continue
        parsed = _safe_date(int(match.group(3)), month, int(match.group(2)))
        if parsed is not None:
            return parsed
    return None


def _find_url_date(value: str) -> datetime | None:
    parsed_url = urlparse(value)
    query = parse_qs(parsed_url.query)
    for key in URL_DATE_KEYS:
        for item in query.get(key, []):
            parsed = _parse_date_fragment(item)
            if parsed is not None:
                return parsed

    decoded_path = unquote(parsed_url.path)
    path_date = _find_explicit_date(decoded_path)
    if path_date is not None:
        return path_date
    compact_match = re.search(r"\b(20\d{2})(0[1-9]|1[0-2])([0-3]\d)\b", decoded_path)
    if compact_match:
        return _safe_date(
            int(compact_match.group(1)),
            int(compact_match.group(2)),
            int(compact_match.group(3)),
        )
    return None


def _parse_date_fragment(value: str) -> datetime | None:
    decoded = unquote(value)
    parsed = _find_explicit_date(decoded)
    if parsed is not None:
        return parsed
    compact_match = re.search(r"\b(20\d{2})(0[1-9]|1[0-2])([0-3]\d)\b", decoded)
    if compact_match:
        return _safe_date(
            int(compact_match.group(1)),
            int(compact_match.group(2)),
            int(compact_match.group(3)),
        )
    return None


def _safe_date(year: int, month: int, day: int) -> datetime | None:
    try:
        return datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None


def _age_days_text(age_days: int) -> str:
    return "1 day old" if age_days == 1 else f"{age_days} days old"


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
