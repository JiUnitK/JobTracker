from __future__ import annotations

import shutil
import sys
from pathlib import Path
from uuid import uuid4

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TMP = ROOT / ".tmp"

TMP.mkdir(exist_ok=True)

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture()
def scratch_dir() -> Path:
    path = TMP / "tests" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


@pytest.fixture()
def sqlite_database_url(scratch_dir: Path) -> str:
    return f"sqlite:///{(scratch_dir / 'jobtracker-test.db').as_posix()}"
