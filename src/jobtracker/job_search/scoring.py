from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from jobtracker.config.models import AppConfig
from jobtracker.job_search.models import InstantJobSearchRequest, InstantJobSearchResult


MIN_RELEVANCE_SCORE = 45
_AGGREGATOR_COMPANIES = {
    "indeed",
    "linkedin",
    "ziprecruiter",
    "glassdoor",
    "dice.com",
    "dice",
    "built in",
    "built in austin",
    "wellfound",
    "monster",
}
_AGGREGATOR_HOST_HINTS = {
    "indeed.com",
    "linkedin.com",
    "ziprecruiter.com",
    "glassdoor.com",
    "dice.com",
    "builtin",
    "wellfound.com",
    "monster.com",
}


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
    profile = app_config.profile if request.use_profile_matching else None
    excluded = [
        keyword
        for keyword in app_config.search_terms.exclude + (profile.excluded_keywords if profile else [])
        if keyword.lower() in searchable
    ]
    if excluded:
        result.score = 0
        result.reasons = [f"excluded keyword: {excluded[0]}"]
        return ScoredInstantResult(result=result, relevant=False)
    if request.source_mode == "strict" and not _is_strict_role_posting_url(str(result.url)):
        result.score = 0
        result.reasons = ["not a confirmed role posting"]
        return ScoredInstantResult(result=result, relevant=False)
    if request.source_mode == "strict" and _is_aggregator_collection_result(result, searchable):
        result.score = 0
        result.reasons = ["job-board search result, not a role posting"]
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

    keyword_hits = _matched_terms(searchable, _scoring_keywords(request, app_config))
    if keyword_hits:
        score += min(12, 4 * len(keyword_hits))
        reasons.append(f"matched keywords: {', '.join(keyword_hits[:3])}")

    if profile:
        preferred_skills = [skill.lower() for skill in profile.preferred_skills]
        matched_skills = [skill for skill in preferred_skills if skill in searchable]
        if matched_skills:
            score += min(18, 6 * len(matched_skills))
            reasons.append(f"profile skills: {', '.join(matched_skills[:3])}")

    location_score, location_reason = _location_score(result, searchable, request, app_config)
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


def _scoring_keywords(request: InstantJobSearchRequest, app_config: AppConfig) -> list[str]:
    if request.use_profile_matching:
        return app_config.search_terms.include
    seen: set[str] = set()
    terms: list[str] = []
    for query in request.queries:
        for token in _tokens(query.query.lower().replace('"', "")):
            if len(token) <= 2 or token in _QUERY_STOPWORDS or token in seen:
                continue
            seen.add(token)
            terms.append(token)
    return terms


def _location_score(
    result: InstantJobSearchResult,
    searchable: str,
    request: InstantJobSearchRequest,
    app_config: AppConfig,
) -> tuple[int, str | None]:
    if request.use_profile_matching:
        preferred_workplaces = set(app_config.search_terms.workplace_types)
        preferred_locations = list(app_config.search_terms.locations)
        preferred_workplaces.update(app_config.profile.target_workplace_types)
        preferred_locations.extend(app_config.profile.preferred_locations)
    else:
        preferred_workplaces = {
            workplace
            for query in request.queries
            for workplace in query.workplace_types
            if workplace != "unknown"
        }
        preferred_locations = [
            query.location for query in request.queries if query.location
        ]
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
    if _is_actual_job_board_posting(url):
        return 4, "job board source"
    return 0, None


def _looks_like_job_posting(url: str, searchable: str) -> bool:
    if _is_aggregator_collection_url(url):
        return False
    parsed = urlparse(url)
    path = parsed.path.lower()
    if _is_actual_job_board_posting(url):
        return True
    if any(piece in path for piece in ["/job", "/jobs", "/careers", "/positions", "/posting"]):
        return True
    return any(
        term in searchable
        for term in ["apply now", "job description", "responsibilities", "qualifications"]
    )


def _matches_location(searchable: str, locations: list[str]) -> bool:
    return any(location.lower() in searchable for location in locations if location.strip())


def _is_aggregator_collection_result(
    result: InstantJobSearchResult,
    searchable: str,
) -> bool:
    if _is_aggregator_collection_url(str(result.url)):
        return True
    title = result.title.lower()
    company = (result.company or "").lower()
    if company in _AGGREGATOR_COMPANIES and _looks_like_collection_title(title):
        return True
    if _looks_like_collection_title(title) and not _is_known_structured_job_url(str(result.url)):
        return True
    return _looks_like_collection_title(title) and any(
        host in str(result.url).lower()
        for host in _AGGREGATOR_HOST_HINTS
    )


def _is_aggregator_collection_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower().rstrip("/")
    query = parse_qs(parsed.query)
    if "indeed.com" in host:
        if path in {"", "/", "/jobs"}:
            return True
        if path.startswith("/q-") or path.startswith("/m/jobs"):
            return True
        return any(key in query for key in ["q", "l"])
    if "linkedin.com" in host:
        if path == "/jobs" or path.startswith("/jobs/search"):
            return True
        if path.startswith("/jobs/") and not path.startswith("/jobs/view/"):
            return True
    if "ziprecruiter.com" in host:
        return path.startswith("/jobs-search") or path.startswith("/jobs")
    if "glassdoor.com" in host:
        return "/job-listing" not in path and ("jobs" in path or "job-search" in path)
    if "dice.com" in host:
        return path.startswith("/jobs") and not path.startswith("/job-detail/")
    if "builtin" in host:
        return path.startswith("/jobs") or "/jobs/" in path
    if "wellfound.com" in host:
        return path.startswith("/jobs")
    if "monster.com" in host:
        return path.startswith("/jobs")
    return False


def _is_actual_job_board_posting(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower().rstrip("/")
    segments = [segment for segment in path.split("/") if segment]
    query = parse_qs(parsed.query)
    if "linkedin.com" in host:
        return _segment_after(segments, "view") is not None and segments[:2] == ["jobs", "view"]
    if "indeed.com" in host:
        return path == "/viewjob" or path == "/rc/clk" or bool(query.get("jk"))
    if "ziprecruiter.com" in host:
        return len(segments) >= 2 and segments[0] == "jobs" and _looks_like_posting_slug(segments[1])
    if "glassdoor.com" in host:
        return "job-listing" in segments and _segment_after(segments, "job-listing") is not None
    return False


def _looks_like_collection_title(title: str) -> bool:
    collection_phrases = [
        "best ",
        "best remote",
        "best hybrid",
        "jobs in",
        "job in",
        "remote jobs",
        "hybrid jobs",
        "software engineer jobs",
        "engineering jobs",
        "apply today",
        "work from home",
        "hiring now",
        "job search",
        "available jobs",
    ]
    if any(phrase in title for phrase in collection_phrases):
        return True
    return title.endswith(" jobs") or " jobs - " in title


def _is_known_structured_job_url(url: str) -> bool:
    lowered = url.lower()
    return any(
        host in lowered
        for host in [
            "greenhouse.io",
            "lever.co",
            "ashbyhq.com",
            "workdayjobs.com",
            "myworkdayjobs.com",
        ]
    ) or _is_actual_job_board_posting(url)


def _is_strict_role_posting_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower().rstrip("/")
    segments = [segment for segment in path.split("/") if segment]
    if _is_actual_job_board_posting(url):
        return True
    if "greenhouse.io" in host:
        return _segment_after(segments, "jobs") is not None or bool(parse_qs(parsed.query).get("gh_jid"))
    if "lever.co" in host:
        return host == "jobs.lever.co" and len(segments) >= 2 and _looks_like_posting_slug(segments[-1])
    if "ashbyhq.com" in host:
        return host == "jobs.ashbyhq.com" and len(segments) >= 2 and _looks_like_posting_slug(segments[-1])
    if "workdayjobs.com" in host or "myworkdayjobs.com" in host:
        return _segment_after(segments, "job") is not None
    return False


def _segment_after(segments: list[str], marker: str) -> str | None:
    try:
        index = segments.index(marker)
    except ValueError:
        return None
    if index + 1 >= len(segments):
        return None
    return segments[index + 1]


def _looks_like_posting_slug(value: str) -> bool:
    return any(character.isdigit() for character in value) or len(value) >= 20


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
