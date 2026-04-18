from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from jobtracker.config.models import (
    AppConfig,
    ProfileConfig,
    ScoringConfig,
    SearchTermsConfig,
    SourcesConfig,
)


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Load a YAML file into a dictionary."""
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}")

    return data


def load_app_config(config_dir: Path) -> AppConfig:
    """Load and validate all config files from a directory."""
    search_terms = SearchTermsConfig.model_validate(
        load_yaml_file(config_dir / "search_terms.yaml")
    )
    sources = SourcesConfig.model_validate(load_yaml_file(config_dir / "sources.yaml"))
    scoring = ScoringConfig.model_validate(load_yaml_file(config_dir / "scoring.yaml"))
    profile = ProfileConfig.model_validate(load_yaml_file(config_dir / "profile.yaml"))
    return AppConfig(
        search_terms=search_terms,
        sources=sources,
        scoring=scoring,
        profile=profile,
    )
