from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from jobtracker.config.models import AppConfig, SourceDefinition
from jobtracker.normalize import normalize_raw_job
from jobtracker.scoring import ScoringService
from jobtracker.sources.planner import build_search_queries
from jobtracker.sources.registry import SourceRegistry, build_default_registry
from jobtracker.storage import (
    CompanyActivityRepository,
    JobObservationRepository,
    JobRepository,
    SearchRunRepository,
    SourceRepository,
    create_session_factory,
    get_database_settings,
)
from jobtracker.storage.migrations import upgrade_database


logger = logging.getLogger(__name__)


def serialize_company_rollups(company_rollups: list[dict[str, object]]) -> list[dict[str, object]]:
    serialized: list[dict[str, object]] = []
    for rollup in company_rollups:
        serialized.append(
            {
                **rollup,
                "last_relevant_opening_seen_at": (
                    rollup["last_relevant_opening_seen_at"].isoformat()
                    if rollup.get("last_relevant_opening_seen_at") is not None
                    else None
                ),
            }
        )
    return serialized


@dataclass(slots=True)
class RunSummary:
    status: str
    search_run_id: int
    total_raw_jobs: int = 0
    total_persisted_jobs: int = 0
    total_observations: int = 0
    status_counts: dict[str, int] = field(default_factory=dict)
    company_rollups: list[dict[str, object]] = field(default_factory=list)
    source_summaries: dict[str, dict[str, int | list[str]]] = field(default_factory=dict)


class RunCoordinator:
    def __init__(self, registry: SourceRegistry | None = None) -> None:
        self.registry = registry or build_default_registry()

    def run(
        self,
        config: AppConfig,
        database_url: str | None = None,
        *,
        run_started_at: datetime | None = None,
    ) -> RunSummary:
        settings = get_database_settings(database_url)
        upgrade_database(settings.url)
        session_factory = create_session_factory(settings)

        with session_factory() as session:
            return self._run_with_session(session, config, run_started_at=run_started_at)

    def _run_with_session(
        self,
        session: Session,
        config: AppConfig,
        *,
        run_started_at: datetime | None = None,
    ) -> RunSummary:
        queries = build_search_queries(config)
        search_run_repo = SearchRunRepository(session)
        source_repo = SourceRepository(session)
        job_repo = JobRepository(session)
        observation_repo = JobObservationRepository(session)
        company_activity_repo = CompanyActivityRepository(session)
        stale_after_runs = int(config.sources.defaults.get("stale_after_runs", 2))
        closed_after_runs = int(config.sources.defaults.get("closed_after_runs", 4))
        recent_days = int(config.sources.defaults.get("recent_activity_days", 14))

        for source_definition in config.sources.sources:
            source_repo.upsert(
                name=source_definition.name,
                reliability_tier=source_definition.reliability_tier,
                enabled=source_definition.enabled,
                base_url=str(source_definition.base_url) if source_definition.base_url else None,
            )

        search_run = search_run_repo.start(
            trigger_type="manual",
            started_at=run_started_at,
        )
        source_summaries: dict[str, dict[str, int | list[str]]] = {}
        total_raw_jobs = 0
        total_persisted_jobs = 0
        total_observations = 0
        seen_observations: set[tuple[int, int, str, str]] = set()

        for source_definition in config.sources.enabled_sources():
            summary = {"raw_jobs": 0, "persisted_jobs": 0, "observations": 0, "errors": []}
            source_summaries[source_definition.name] = summary
            adapter = self.registry.get(source_definition.name)
            if adapter is None:
                error = f"No adapter registered for source '{source_definition.name}'"
                summary["errors"].append(error)
                source_repo.mark_error(source_definition.name)
                logger.warning(error)
                continue

            try:
                collected = []
                for query in queries:
                    collected.extend(adapter.collect(source_definition, query))
                source_repo.mark_success(source_definition.name)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                summary["errors"].append(error)
                source_repo.mark_error(source_definition.name)
                logger.exception("Source collection failed for %s", source_definition.name)
                continue

            summary["raw_jobs"] = len(collected)
            total_raw_jobs += len(collected)

            for raw_job in collected:
                normalized_job = normalize_raw_job(raw_job)
                job = job_repo.upsert(
                    normalized_job,
                    seen_at=search_run.started_at,
                    source=raw_job.source,
                    source_job_id=raw_job.source_job_id,
                )
                summary["persisted_jobs"] += 1
                total_persisted_jobs += 1

                observation_key = (
                    job.id,
                    search_run.id,
                    raw_job.source,
                    raw_job.source_job_id,
                )
                if observation_key in seen_observations:
                    continue
                observation_repo.create(
                    job_id=job.id,
                    search_run_id=search_run.id,
                    raw_job=raw_job,
                    observed_at=search_run.started_at,
                )
                seen_observations.add(observation_key)
                summary["observations"] += 1
                total_observations += 1

        status = self._derive_status(source_summaries, config.sources.enabled_sources())
        search_run_repo.complete(
            search_run,
            status=status,
            summary={
                "total_raw_jobs": total_raw_jobs,
                "total_persisted_jobs": total_persisted_jobs,
                "total_observations": total_observations,
                "sources": source_summaries,
            },
            completed_at=search_run.started_at,
        )
        status_counts = job_repo.infer_statuses(
            current_run=search_run,
            stale_after_runs=stale_after_runs,
            closed_after_runs=closed_after_runs,
        )
        company_rollups = company_activity_repo.summarize(
            recent_since=search_run.started_at - timedelta(days=recent_days)
        )
        ScoringService(session, config).score_all_jobs(now=search_run.started_at)
        search_run.summary_json = {
            **search_run.summary_json,
            "status_counts": status_counts,
            "company_rollups": serialize_company_rollups(company_rollups),
        }
        session.commit()
        return RunSummary(
            status=status,
            search_run_id=search_run.id,
            total_raw_jobs=total_raw_jobs,
            total_persisted_jobs=total_persisted_jobs,
            total_observations=total_observations,
            status_counts=status_counts,
            company_rollups=company_rollups,
            source_summaries=source_summaries,
        )

    def _derive_status(
        self,
        source_summaries: dict[str, dict[str, int | list[str]]],
        enabled_sources: list[SourceDefinition],
    ) -> str:
        if not enabled_sources:
            return "success"
        success_count = sum(1 for summary in source_summaries.values() if not summary["errors"])
        if success_count == len(enabled_sources):
            return "success"
        if success_count == 0:
            return "failed"
        return "partial_success"
