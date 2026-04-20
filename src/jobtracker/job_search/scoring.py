from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from jobtracker.config.models import AppConfig
from jobtracker.job_search.models import InstantJobSearchRequest, InstantJobSearchResult


MIN_RELEVANCE_SCORE = 45


@dataclass(frozen=True, slots=True)
class ScoredInstantResult:
    result: InstantJobSearchResult
    relevant: bool


def score_instant_job_result(
    result: InstantJobSearchResult,
    request: InstantJobSearchRequest,
    app_config: AppConfig,
) -> ScoredInstantResult:
    searchable = " ".join(
        filter(None, [result.title, result.company, result.location, result.snippet])
    ).lower()
    excluded = [
        keyword
        for keyword in app_config.search_terms.exclude + app_config.profile.excluded_keywords
        if keyword.lower() in searchable
    ]
    if excluded:
        result.score = 0
        result.reasons = [f"excluded keyword: {excluded[0]}"]
        return ScoredInstantResult(result=result, relevant=False)

    score = 10
    reasons: list[str] = []

    title_score = _title_match_score(result.title, request)
    if title_score >= 0.75:
        score += 30
        reasons.append("strong title match")
    elif title_score > 0:
        score += 18
        reasons.append("partial title match")

    keyword_hits = _matched_terms(searchable, app_config.search_terms.include)
    if keyword_hits:
        score += min(12, 4 * len(keyword_hits))
        reasons.append(f"matched keywords: {', '.join(keyword_hits[:3])}")

    preferred_skills = [skill.lower() for skill in app_config.profile.preferred_skills]
    matched_skills = [skill for skill in preferred_skills if skill in searchable]
    if matched_skills:
        score += min(18, 6 * len(matched_skills))
        reasons.append(f"matched skills: {', '.join(matched_skills[:3])}")

    location_score, location_reason = _location_score(result, searchable, app_config)
    score += location_score
    if location_reason:
        reasons.append(location_reason)

    seniority_hits = _matched_terms(searchable, app_config.search_terms.seniority)
    if seniority_hits:
        score += 6
        reasons.append(f"seniority match: {seniority_hits[0]}")

    freshness_score, freshness_reason = _freshness_score(result, request)
    score += freshness_score
    if freshness_reason:
        reasons.append(freshness_reason)

    source_score, source_reason = _source_score(str(result.url))
    score += source_score
    if source_reason:
        reasons.append(source_reason)

    if _looks_like_job_posting(str(result.url), searchable):
        score += 6
        reasons.append("job posting page")

    result.score = score
    result.reasons = _dedupe_reasons(reasons)
    return ScoredInstantResult(result=result, relevant=result.score >= MIN_RELEVANCE_SCORE)


def _title_match_score(title: str, request: InstantJobSearchRequest) -> float:
    title_tokens = {token for token in _tokens(title.lower()) if len(token) > 2}
    if not title_tokens:
        return 0.0
    best = 0.0
    for query in request.queries:
        query_tokens = {
            token
            for token in _tokens(query.query.lower().replace('"', ""))
            if len(token) > 2 and token not in _QUERY_STOPWORDS
        }
        if not query_tokens:
            continue
        best = max(best, len(title_tokens & query_tokens) / len(query_tokens))
    return min(best, 1.0)


def _matched_terms(searchable: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term.strip() and term.lower() in searchable]


def _location_score(
    result: InstantJobSearchResult,
    searchable: str,
    app_config: AppConfig,
) -> tuple[int, str | None]:
    preferred_workplaces = set(
        app_config.search_terms.workplace_types or app_config.profile.target_workplace_types
    )
    preferred_locations = app_config.search_terms.locations + app_config.profile.preferred_locations
    if result.workplace_type in preferred_workplaces and result.workplace_type != "unknown":
        return 14, f"{result.workplace_type} workplace"
    if result.workplace_type in {"remote", "hybrid"}:
        return 10, f"{result.workplace_type} workplace"
    if _matches_location(searchable, preferred_locations):
        return 10, "location match"
    return 0, None


def _freshness_score(
    result: InstantJobSearchResult,
    request: InstantJobSearchRequest,
) -> tuple[int, str | None]:
    if result.age_days is None:
        return 0, "age unknown" if result.age_confidence == "unknown" else None
    confidence_bonus = {"high": 4, "medium": 3, "low": 1, "unknown": 0}[result.age_confidence]
    if result.age_days <= request.max_age_days:
        return 18 + confidence_bonus, "recent posting"
    if result.age_days <= request.max_age_days * 2:
        return 6 + confidence_bonus, "possibly recent"
    return 0, None


def _source_score(url: str) -> tuple[int, str | None]:
    lowered = url.lower()
    if any(host in lowered for host in ["greenhouse.io", "lever.co", "ashbyhq.com"]):
        return 10, "ATS source"
    if "workdayjobs.com" in lowered or "myworkdayjobs.com" in lowered:
        return 8, "ATS source"
    if any(host in lowered for host in ["linkedin.com/jobs", "indeed.com", "ziprecruiter.com"]):
        return 4, "job board source"
    return 0, None


def _looks_like_job_posting(url: str, searchable: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if any(piece in path for piece in ["/job", "/jobs", "/careers", "/positions", "/posting"]):
        return True
    return any(
        term in searchable
        for term in ["apply now", "job description", "responsibilities", "qualifications"]
    )


def _matches_location(searchable: str, locations: list[str]) -> bool:
    return any(location.lower() in searchable for location in locations if location.strip())


def _tokens(text: str) -> list[str]:
    return [token.strip(".,:;()[]{}") for token in text.split()]


def _dedupe_reasons(reasons: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        cleaned = reason.strip()
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        deduped.append(cleaned)
    return deduped


_QUERY_STOPWORDS = {
    "job",
    "apply",
    "posted",
    "careers",
    "career",
    "recently",
    "site",
    "remote",
    "hybrid",
    "on-site",
    "onsite",
    "united",
    "states",
}
