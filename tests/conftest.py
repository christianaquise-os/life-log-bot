import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Points src.db at an isolated SQLite file and applies all migrations.

    Must patch src.db.DB_PATH (the name as bound inside src/db.py's own
    module namespace via `from src.config import DB_PATH`), not
    src.config.DB_PATH -- patching the original has no effect on the
    already-imported binding inside src.db.
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("src.db.DB_PATH", db_path)
    from src.db import apply_migrations

    apply_migrations()
    return db_path
