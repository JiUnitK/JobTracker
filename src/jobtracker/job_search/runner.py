from __future__ import annotations

from datetime import datetime, timezone

from jobtracker.config.models import AppConfig
from jobtracker.job_search.models import InstantJobSearchRunSummary
from jobtracker.job_search.normalize import canonical_result_key, normalize_instant_search_result
from jobtracker.job_search.planner import JobSearchOverrides, build_instant_job_search_request
from jobtracker.job_search.registry import (
    InstantJobSearchRegistry,
    build_default_instant_job_search_registry,
)
from jobtracker.job_search.scoring import score_instant_job_result


class InstantJobSearchRunner:
    def __init__(self, registry: InstantJobSearchRegistry | None = None) -> None:
        self.registry = registry or build_default_instant_job_search_registry()

    def run(
        self,
        app_config: AppConfig,
        overrides: JobSearchOverrides | None = None,
        *,
        now: datetime | None = None,
    ) -> InstantJobSearchRunSummary:
        request = build_instant_job_search_request(app_config, overrides)
        now = now or datetime.now(timezone.utc)
        summary = InstantJobSearchRunSummary(
            requested_queries=request.queries,
            max_age_days=request.max_age_days,
            include_unknown_age=request.include_unknown_age,
            include_low_fit=request.include_low_fit,
        )
        results_by_key = {}

        for source in app_config.job_search.enabled_sources():
            adapter = self.registry.get(source.name)
            if adapter is None:
                continue
            for query in request.queries:
                raw_results = adapter.search(source, query)
                summary.total_raw_results += len(raw_results)
                for raw in raw_results:
                    normalized = normalize_instant_search_result(raw, now=now)
                    if _should_skip_for_age(normalized, request.max_age_days, request.include_unknown_age):
                        summary.skipped_for_age += 1
                        continue
                    scored = score_instant_job_result(normalized, request, app_config)
                    if not scored.relevant and not request.include_low_fit:
                        summary.skipped_for_relevance += 1
                        continue
                    key = canonical_result_key(scored.result)
                    existing = results_by_key.get(key)
                    if existing is None or scored.result.score > existing.score:
                        results_by_key[key] = scored.result

        summary.results = sorted(
            results_by_key.values(),
            key=lambda item: (item.score, _freshness_sort_value(item.age_days)),
            reverse=True,
        )[: request.limit]
        return summary


def _should_skip_for_age(
    result,
    max_age_days: int,
    include_unknown_age: bool,
) -> bool:
    if result.age_days is None:
        return not include_unknown_age
    return result.age_days > max_age_days


def _freshness_sort_value(age_days: int | None) -> int:
    if age_days is None:
        return -10_000
    return -age_days
