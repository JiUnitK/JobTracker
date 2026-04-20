from __future__ import annotations

from dataclasses import dataclass

from jobtracker.config.models import AppConfig
from jobtracker.job_search.models import InstantJobSearchRequest, InstantJobSearchResult


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

    score = 20
    reasons: list[str] = []

    query_terms = [query.query.lower().replace('"', "") for query in request.queries]
    if any(_has_title_overlap(result.title.lower(), query) for query in query_terms):
        score += 30
        reasons.append("title match")

    preferred_skills = [skill.lower() for skill in app_config.profile.preferred_skills]
    matched_skills = [skill for skill in preferred_skills if skill in searchable]
    if matched_skills:
        score += min(20, 5 * len(matched_skills))
        reasons.append(f"matched skills: {', '.join(matched_skills[:3])}")

    if result.workplace_type in {"remote", "hybrid"}:
        score += 15
        reasons.append(result.workplace_type)
    elif _matches_location(searchable, app_config.search_terms.locations + app_config.profile.preferred_locations):
        score += 10
        reasons.append("location match")

    if result.age_days is not None:
        if result.age_days <= request.max_age_days:
            score += 20
            reasons.append("recent posting")
        elif result.age_days <= request.max_age_days * 2:
            score += 5
            reasons.append("possibly recent")
    elif result.age_confidence == "unknown":
        reasons.append("age unknown")

    if _high_confidence_job_host(str(result.url)):
        score += 10
        reasons.append("job board source")

    result.score = score
    result.reasons = reasons
    return ScoredInstantResult(result=result, relevant=score >= 35)


def _has_title_overlap(title: str, query: str) -> bool:
    title_tokens = {token for token in _tokens(title) if len(token) > 2}
    query_tokens = {
        token
        for token in _tokens(query)
        if len(token) > 2
        and token not in {"job", "apply", "posted", "careers", "recently", "site"}
    }
    if not title_tokens or not query_tokens:
        return False
    return bool(title_tokens & query_tokens)


def _matches_location(searchable: str, locations: list[str]) -> bool:
    return any(location.lower() in searchable for location in locations if location.strip())


def _high_confidence_job_host(url: str) -> bool:
    lowered = url.lower()
    return any(host in lowered for host in ["greenhouse.io", "lever.co", "ashbyhq.com", "workdayjobs.com"])


def _tokens(text: str) -> list[str]:
    return [token.strip(".,:;()[]{}") for token in text.split()]

