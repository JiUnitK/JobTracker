from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

LEGACY_IMPORT_PATTERNS = [
    "jobtracker." + name
    for name in ("sources", "normalize", "scoring")
] + [
    "storage." + "repositories",
    *["from jobtracker import " + name for name in ("sources", "normalize", "scoring")],
]

ALLOWED_FILES = {
    Path("tests/test_import_boundaries.py"),
    Path("tests/test_legacy_imports.py"),
}


def _candidate_files() -> list[Path]:
    roots = [REPO_ROOT / "src" / "jobtracker", REPO_ROOT / "tests"]
    files: list[Path] = []
    for root in roots:
        files.extend(root.rglob("*.py"))
    return sorted(files)


def test_first_party_code_does_not_use_legacy_import_paths() -> None:
    violations: list[str] = []
    for path in _candidate_files():
        relative_path = path.relative_to(REPO_ROOT)
        if relative_path in ALLOWED_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in LEGACY_IMPORT_PATTERNS:
            if pattern in text:
                violations.append(f"{relative_path}: {pattern}")

    assert violations == []
