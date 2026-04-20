from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_launcher_wrapper_calls_powershell_script() -> None:
    text = (ROOT / "Start-JobTracker.bat").read_text(encoding="utf-8")

    assert "Start-JobTracker.ps1" in text
    assert "-ExecutionPolicy Bypass" in text
    assert "pause >nul" in text


def test_powershell_launcher_contains_first_run_flow() -> None:
    text = (ROOT / "Start-JobTracker.ps1").read_text(encoding="utf-8")

    assert "winget install --id Python.Python.3.12" in text
    assert "--accept-package-agreements" in text
    assert "python 3.12+" in text.lower()
    assert "pip install -e ." in text
    assert "BRAVE_SEARCH_API_KEY" in text
    assert "Start-Process $url" in text
    assert "Find-OpenPort" in text


def test_powershell_launcher_parses_when_powershell_is_available() -> None:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        return

    command = (
        "$errors = $null; $tokens = $null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        "'Start-JobTracker.ps1', [ref]$tokens, [ref]$errors) | Out-Null; "
        "if ($errors) { $errors | ForEach-Object { $_.Message }; exit 1 }"
    )
    result = subprocess.run(
        [powershell, "-NoProfile", "-Command", command],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
