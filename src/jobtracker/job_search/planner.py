from __future__ import annotations

from dataclasses import dataclass

from jobtracker.config.models import AppConfig
from jobtracker.job_search.models import InstantJobSearchQuery, InstantJobSearchRequest, SourceMode
from jobtracker.models import WorkplaceType


DEFAULT_QUERY_TEMPLATES = [
    '"{query}" "{location}" {workplace_terms} {job_intent}',
    '"{query}" "{location}" careers recently posted {workplace_terms}',
    'site:greenhouse.io "{query}" "{location}" {workplace_terms}',
    'site:jobs.lever.co "{query}" "{location}" {workplace_terms}',
    'site:jobs.ashbyhq.com "{query}" "{location}" {workplace_terms}',
]
JOB_INTENT_TERMS = ["job", "apply", "careers", "posted"]
JOB_INTENT_TEXT = " ".join(JOB_INTENT_TERMS)


@dataclass(frozen=True, slots=True)
class JobSearchOverrides:
    query: str | None = None
    location: str | None = None
    max_age_days: int | None = None
    include_unknown_age: bool | None = None
    use_profile_matching: bool | None = None
    source_mode: SourceMode | None = None
    limit: int | None = None


def build_instant_job_search_request(
    app_config: AppConfig,
    overrides: JobSearchOverrides | None = None,
) -> InstantJobSearchRequest:
    overrides = overrides or JobSearchOverrides()
    use_profile_matching = bool(overrides.use_profile_matching)
    base_queries = _query_terms(app_config, overrides.query, use_profile_matching)
    locations = _locations(app_config, overrides.location, use_profile_matching)
    workplace_types = _workplace_types(app_config, use_profile_matching)
    templates = app_config.job_search.settings.query_templates or DEFAULT_QUERY_TEMPLATES

    queries: list[InstantJobSearchQuery] = []
    seen: set[tuple[str, str | None, tuple[WorkplaceType, ...]]] = set()
    for query_text in base_queries:
        for location in locations:
            for planned in _expand_templates(
                templates,
                query=query_text,
                location=location,
                workplace_types=workplace_types,
            ):
                key = (planned.query.lower(), planned.location, tuple(planned.workplace_types))
                if key in seen:
                    continue
                seen.add(key)
                queries.append(planned)

    return InstantJobSearchRequest(
        queries=queries,
        max_age_days=overrides.max_age_days or app_config.job_search.settings.max_age_days,
        include_unknown_age=(
            app_config.job_search.settings.include_unknown_age
            if overrides.include_unknown_age is None
            else overrides.include_unknown_age
        ),
        use_profile_matching=use_profile_matching,
        source_mode=overrides.source_mode or "strict",
        limit=overrides.limit or 25,
    )


def _query_terms(
    app_config: AppConfig,
    override_query: str | None,
    use_profile_matching: bool,
) -> list[str]:
    if override_query and override_query.strip():
        return [override_query.strip()]
    values = app_config.job_search.settings.queries or app_config.search_terms.include
    if not values and use_profile_matching:
        values = app_config.profile.target_titles
    cleaned = [value.strip() for value in values if value.strip()]
    if not cleaned:
        raise ValueError("At least one instant-search query or include term is required")
    return cleaned


def _locations(
    app_config: AppConfig,
    override_location: str | None,
    use_profile_matching: bool,
) -> list[str]:
    if override_location and override_location.strip():
        return [override_location.strip()]
    values = app_config.search_terms.locations
    if not values and use_profile_matching:
        values = app_config.profile.preferred_locations
    cleaned = [value.strip() for value in values if value.strip()]
    return cleaned or [""]


def _workplace_types(app_config: AppConfig, use_profile_matching: bool) -> list[WorkplaceType]:
    values = app_config.search_terms.workplace_types
    if not values and use_profile_matching:
        values = app_config.profile.target_workplace_types
    return [value for value in values if value != "unknown"]


def _expand_templates(
    templates: list[str],
    *,
    query: str,
    location: str,
    workplace_types: list[WorkplaceType],
) -> list[InstantJobSearchQuery]:
    planned: list[InstantJobSearchQuery] = []
    workplace_terms = _workplace_terms(workplace_types)
    for template in templates:
        rendered = template.format(
            query=query,
            location=location,
            workplace_type=workplace_terms,
            workplace_terms=workplace_terms,
            job_intent=JOB_INTENT_TEXT,
        )
        rendered = _ensure_job_intent(" ".join(rendered.split()))
        if not rendered:
            continue
        planned.append(
            InstantJobSearchQuery(
                query=rendered,
                location=location or None,
                workplace_types=workplace_types,
            )
        )
    return planned


def _workplace_terms(workplace_types: list[WorkplaceType]) -> str:
    terms = [item for item in workplace_types if item in {"remote", "hybrid", "onsite"}]
    if not terms:
        return ""
    expanded = ["on-site" if item == "onsite" else item for item in terms]
    return " ".join(expanded)


def _ensure_job_intent(query: str) -> str:
    lowered = query.lower()
    if any(term in lowered for term in JOB_INTENT_TERMS):
        return query
    return f"{query} {JOB_INTENT_TEXT}".strip()
