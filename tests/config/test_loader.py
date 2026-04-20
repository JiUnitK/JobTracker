from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from jobtracker.config.loader import load_app_config, load_yaml_file
from jobtracker.config.models import SearchTermsConfig


def test_load_app_config_reads_default_files() -> None:
    config = load_app_config(Path("config"))

    assert len(config.search_terms.include) >= 3
    assert any(source.name == "greenhouse" for source in config.sources.sources)
    assert any(
        source.name == "company_search" for source in config.company_discovery.sources
    )
    assert config.job_search.settings.max_age_days == 7
    assert config.job_search.settings.include_unknown_age is False
    assert config.job_search.settings.query_templates
    assert any(source.name == "brave_search" for source in config.job_search.sources)
    assert any(source.name == "brave_search" for source in config.job_search.enabled_sources())
    assert "backend engineer" in config.profile.target_titles
    assert "enabled instant search sources" in config.summary()


def test_load_yaml_file_rejects_non_mapping() -> None:
    scratch_dir = Path(".tmp") / "tests"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    config_path = scratch_dir / f"invalid-{uuid4().hex}.yaml"

    try:
        config_path.write_text("- not-a-mapping\n", encoding="utf-8")

        with pytest.raises(ValueError):
            load_yaml_file(config_path)
    finally:
        if config_path.exists():
            config_path.unlink()


def test_instant_job_search_config_rejects_non_positive_max_age() -> None:
    with pytest.raises(ValidationError, match="max_age_days"):
        SearchTermsConfig.model_validate(
            {
                "include": ["customer success"],
                "instant_job_search": {"max_age_days": 0},
            }
        )


def test_instant_job_search_config_cleans_blank_query_templates() -> None:
    config = SearchTermsConfig.model_validate(
        {
            "include": ["customer success"],
            "instant_job_search": {
                "max_age_days": 14,
                "include_unknown_age": True,
                "queries": [" customer success ", " ", ""],
                "query_templates": [" {query} job ", " ", ""],
            },
        }
    )

    assert config.instant_job_search.max_age_days == 14
    assert config.instant_job_search.include_unknown_age is True
    assert config.instant_job_search.queries == ["customer success"]
    assert config.instant_job_search.query_templates == ["{query} job"]
