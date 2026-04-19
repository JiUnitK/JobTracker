from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from jobtracker.company_discovery.normalize import infer_resolution_candidate, normalize_company_discovery
from jobtracker.company_discovery.planner import build_company_discovery_queries
from jobtracker.company_discovery.registry import (
    CompanyDiscoveryRegistry,
    build_default_company_discovery_registry,
)
from jobtracker.company_discovery.scoring import CompanyDiscoveryScoringService
from jobtracker.config.models import AppConfig
from jobtracker.storage import (
    CompanyDiscoveryObservationRepository,
    CompanyDiscoveryRepository,
    CompanyResolutionRepository,
    SearchRunRepository,
    create_session_factory,
    get_database_settings,
)
from jobtracker.storage.migrations import upgrade_database


@dataclass(slots=True)
class CompanyDiscoveryRunSummary:
    status: str
    search_run_id: int
    total_raw_discoveries: int = 0
    total_persisted_discoveries: int = 0
    total_observations: int = 0
    total_resolutions: int = 0
    errors: list[str] = field(default_factory=list)


class CompanyDiscoveryRunner:
    def __init__(self, registry: CompanyDiscoveryRegistry | None = None) -> None:
        self.registry = registry or build_default_company_discovery_registry()

    def run(
        self,
        app_config: AppConfig,
        database_url: str | None = None,
        *,
        trigger_type: str = "company_discovery",
        started_at: datetime | None = None,
    ) -> CompanyDiscoveryRunSummary:
        settings = get_database_settings(database_url)
        upgrade_database(settings.url)
        session_factory = create_session_factory(settings)
        summary = CompanyDiscoveryRunSummary(status="success", search_run_id=0)
        queries = build_company_discovery_queries(app_config.company_discovery)

        with session_factory() as session:
            run_repo = SearchRunRepository(session)
            discovery_repo = CompanyDiscoveryRepository(session)
            observation_repo = CompanyDiscoveryObservationRepository(session)
            resolution_repo = CompanyResolutionRepository(session)
            search_run = run_repo.start(trigger_type=trigger_type, started_at=started_at)
            summary.search_run_id = search_run.id

            for source in app_config.company_discovery.enabled_sources():
                adapter = self.registry.get(source.name)
                if adapter is None:
                    summary.errors.append(f"no discovery adapter registered for '{source.name}'")
                    continue

                for query in queries:
                    if query.source_names and source.name not in query.source_names:
                        continue

                    try:
                        raw_discoveries = adapter.discover(source, query)
                    except Exception as exc:
                        summary.errors.append(f"{source.name}: {exc}")
                        continue

                    summary.total_raw_discoveries += len(raw_discoveries)
                    for raw_discovery in raw_discoveries:
                        normalized = normalize_company_discovery(raw_discovery)
                        persisted = discovery_repo.upsert(normalized, discovered_at=started_at)
                        observation_repo.create(
                            company_discovery_id=persisted.id,
                            search_run_id=search_run.id,
                            raw_discovery=raw_discovery,
                            observed_at=started_at,
                        )
                        summary.total_persisted_discoveries += 1
                        summary.total_observations += 1

                        resolution_candidate = infer_resolution_candidate(normalized)
                        if resolution_candidate is not None:
                            resolution_repo.upsert_candidate(
                                company_discovery_id=persisted.id,
                                resolution_type=str(resolution_candidate["resolution_type"]),
                                platform=str(resolution_candidate["platform"]),
                                identifier=str(resolution_candidate["identifier"]),
                                url=str(resolution_candidate["url"]),
                                confidence=float(resolution_candidate["confidence"]),
                                observed_at=started_at,
                            )
                            summary.total_resolutions += 1

            CompanyDiscoveryScoringService(session, app_config).score_all_discoveries(
                now=started_at or datetime.now()
            )

            if summary.errors:
                summary.status = "partial_success" if summary.total_persisted_discoveries else "failed"

            run_repo.complete(
                search_run,
                status=summary.status,
                summary={
                    "workflow": "company_discovery",
                    "raw_discoveries": summary.total_raw_discoveries,
                    "persisted_discoveries": summary.total_persisted_discoveries,
                    "observations": summary.total_observations,
                    "resolutions": summary.total_resolutions,
                    "errors": summary.errors,
                },
                completed_at=started_at,
            )
            session.commit()

        return summary
