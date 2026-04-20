from __future__ import annotations

from typer.testing import CliRunner

from jobtracker.cli.app import app


runner = CliRunner()


def test_cli_help_smoke() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Track job opportunities" in result.stdout


def test_web_command_help_smoke() -> None:
    result = runner.invoke(app, ["web", "--help"])

    assert result.exit_code == 0
    assert "Start the local browser UI" in result.stdout


def test_config_validate_command_uses_default_config() -> None:
    result = runner.invoke(app, ["config", "validate"])

    assert result.exit_code == 0
    assert "Configuration valid:" in result.stdout


def test_company_discovery_run_command_uses_default_config(sqlite_database_url: str) -> None:
    result = runner.invoke(
        app,
        ["discover", "companies", "run", "--database-url", sqlite_database_url],
    )

    assert result.exit_code == 0
    assert "Discovery run complete:" in result.stdout
