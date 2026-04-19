from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from jobtracker.cli.app import app


runner = CliRunner()


def _write_config(config_dir: Path, sources_content: str) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    for name in ("search_terms.yaml", "scoring.yaml", "profile.yaml"):
        (config_dir / name).write_text(
            Path("config", name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    (config_dir / "sources.yaml").write_text(sources_content, encoding="utf-8")
    return config_dir


def test_sources_list_shows_configured_sources_and_adapter_status(
    scratch_dir: Path,
    sqlite_database_url: str,
) -> None:
    config_dir = _write_config(
        scratch_dir / "config",
        """\
defaults:
  timeout_seconds: 20
  max_results_per_query: 100
sources:
  - name: greenhouse
    type: ats
    enabled: true
    reliability_tier: tier1
    base_url: https://boards.greenhouse.io/
    params:
      board_tokens: []
  - name: lever
    type: ats
    enabled: false
    reliability_tier: tier1
    base_url: https://jobs.lever.co/
""",
    )

    result = runner.invoke(
        app,
        [
            "sources",
            "list",
            "--config-dir",
            str(config_dir),
            "--database-url",
            sqlite_database_url,
        ],
    )

    assert result.exit_code == 0
    assert "greenhouse | type=ats | enabled=yes | tier=tier1 | adapter=yes" in result.stdout
    assert "lever | type=ats | enabled=no | tier=tier1 | adapter=yes" in result.stdout
    assert "last_success=-" in result.stdout
