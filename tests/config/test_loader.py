from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from jobtracker.config.loader import load_app_config, load_yaml_file


def test_load_app_config_reads_default_files() -> None:
    config = load_app_config(Path("config"))

    assert len(config.search_terms.include) >= 3
    assert any(source.name == "greenhouse" for source in config.sources.sources)
    assert any(
        source.name == "company_search" for source in config.company_discovery.sources
    )
    assert "backend engineer" in config.profile.target_titles


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
