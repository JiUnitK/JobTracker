from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from jobtracker.config.models import (
    AppConfig,
    CompanyDiscoveryConfig,
    ProfileConfig,
    ScoringConfig,
    SearchTermsConfig,
    SourcesConfig,
)


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Load a YAML file into a dictionary."""
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}")

    return data


def load_optional_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return load_yaml_file(path)


def load_app_config(config_dir: Path) -> AppConfig:
    """Load and validate all config files from a directory."""
    _load_dotenv(config_dir.parent / ".env")
    search_terms = SearchTermsConfig.model_validate(
        load_yaml_file(config_dir / "search_terms.yaml")
    )
    sources = SourcesConfig.model_validate(load_yaml_file(config_dir / "sources.yaml"))
    company_discovery = CompanyDiscoveryConfig.model_validate(
        load_optional_yaml_file(config_dir / "company_discovery.yaml")
    )
    scoring = ScoringConfig.model_validate(load_yaml_file(config_dir / "scoring.yaml"))
    profile = ProfileConfig.model_validate(load_yaml_file(config_dir / "profile.yaml"))
    return AppConfig(
        search_terms=search_terms,
        sources=sources,
        company_discovery=company_discovery,
        scoring=scoring,
        profile=profile,
    )
