from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from jobtracker.config.models import AppConfig, SourceDefinition
from jobtracker.normalize import normalize_raw_job
from jobtracker.sources.planner import build_search_queries
from jobtracker.sources.registry import SourceRegistry, build_default_registry
from jobtracker.storage import (
    JobObservationRepository,
    JobRepository,
    SearchRunRepository,
    SourceRepository,
    create_session_factory,
    get_database_settings,
)
from jobtracker.storage.migrations import upgrade_database


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RunSummary:
    status: str
    search_run_id: int
    total_raw_jobs: int = 0
    total_persisted_jobs: int = 0
    total_observations: int = 0
    source_summaries: dict[str, dict[str, int | list[str]]] = field(default_factory=dict)


class RunCoordinator:
    def __init__(self, registry: SourceRegistry | None = None) -> None:
        self.registry = registry or build_default_registry()

    def run(self, config: AppConfig, database_url: str | None = None) -> RunSummary:
        settings = get_database_settings(database_url)
        upgrade_database(settings.url)
        session_factory = create_session_factory(settings)

        with session_factory() as session:
            return self._run_with_session(session, config)

    def _run_with_session(self, session: Session, config: AppConfig) -> RunSummary:
        queries = build_search_queries(config)
        search_run_repo = SearchRunRepository(session)
        source_repo = SourceRepository(session)
        job_repo = JobRepository(session)
        observation_repo = JobObservationRepository(session)

        for source_definition in config.sources.sources:
            source_repo.upsert(
                name=source_definition.name,
                reliability_tier=source_definition.reliability_tier,
                enabled=source_definition.enabled,
                base_url=str(source_definition.base_url) if source_definition.base_url else None,
            )

        search_run = search_run_repo.start(trigger_type="manual")
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
                job = job_repo.upsert(normalized_job, seen_at=raw_job.posted_at)
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
                    observed_at=raw_job.posted_at,
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
        )
        session.commit()
        return RunSummary(
            status=status,
            search_run_id=search_run.id,
            total_raw_jobs=total_raw_jobs,
            total_persisted_jobs=total_persisted_jobs,
            total_observations=total_observations,
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
