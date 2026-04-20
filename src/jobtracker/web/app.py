from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from jobtracker.config.loader import load_app_config
from jobtracker.config.models import AppConfig
from jobtracker.job_search.brave_adapter import BraveSearchError
from jobtracker.job_search.planner import JobSearchOverrides
from jobtracker.job_search.runner import InstantJobSearchRunner
from jobtracker.web.schemas import InstantJobSearchApiRequest, WebConfigSummary


RunnerFactory = Callable[[], InstantJobSearchRunner]


def create_app(
    *,
    config_dir: Path | str = Path("config"),
    runner_factory: RunnerFactory | None = None,
) -> FastAPI:
    app = FastAPI(title="JobTracker", version="0.1.0")
    config_path = Path(config_dir)
    static_dir = Path(__file__).resolve().parent / "static"
    runner_factory = runner_factory or InstantJobSearchRunner

    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/api/config/summary", response_model=WebConfigSummary)
    def config_summary() -> WebConfigSummary:
        app_config = load_app_config(config_path)
        return build_web_config_summary(app_config)

    @app.post("/api/search/jobs")
    def search_jobs(payload: InstantJobSearchApiRequest) -> dict:
        app_config = load_app_config(config_path)
        try:
            summary = runner_factory().run(
                app_config,
                JobSearchOverrides(
                    query=payload.query,
                    location=payload.location,
                    max_age_days=payload.days,
                    include_unknown_age=payload.include_unknown_age,
                    include_low_fit=payload.include_low_fit,
                    limit=payload.limit,
                ),
            )
        except (BraveSearchError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return summary.model_dump(mode="json")

    return app


def build_web_config_summary(app_config: AppConfig) -> WebConfigSummary:
    search_settings = app_config.job_search.settings
    return WebConfigSummary(
        default_query=_first_value(
            search_settings.queries,
            app_config.search_terms.include,
            app_config.profile.target_titles,
        ),
        default_location=_first_value(
            app_config.search_terms.locations,
            app_config.profile.preferred_locations,
        ),
        max_age_days=search_settings.max_age_days,
        include_unknown_age=search_settings.include_unknown_age,
        include_low_fit=False,
        enabled_instant_search_sources=[
            source.name for source in app_config.job_search.enabled_sources()
        ],
    )


def _first_value(*groups: list[str]) -> str | None:
    for group in groups:
        for item in group:
            cleaned = item.strip()
            if cleaned:
                return cleaned
    return None
