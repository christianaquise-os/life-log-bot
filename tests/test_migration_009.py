import shutil
import sqlite3
from pathlib import Path

import pytest

from src.db import apply_migrations

REAL_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def test_check_constraint_rebuild_preserves_data_and_widens_check(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("src.db.DB_PATH", db_path)

    # Apply only migrations before 009 first, so we can seed data under the
    # OLD (narrower) CHECK constraint.
    partial_dir = tmp_path / "migrations_partial"
    partial_dir.mkdir()
    for f in sorted(REAL_MIGRATIONS_DIR.glob("*.sql")):
        if f.name < "009":
            shutil.copy(f, partial_dir / f.name)
    monkeypatch.setattr("src.db.MIGRATIONS_DIR", partial_dir)
    apply_migrations()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO sessions
           (chat_id, pillar, activity_name, raw_text, source_intent, start_ts, status)
           VALUES (1, 'uncategorized', 'laundry', 'test', 'start_stop', '2026-01-01T00:00:00.000000Z', 'open')"""
    )
    conn.commit()
    conn.close()

    # Now apply the rest (migration 009, the rebuild) against the real dir.
    monkeypatch.setattr("src.db.MIGRATIONS_DIR", REAL_MIGRATIONS_DIR)
    apply_migrations()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Pre-existing row survived byte-for-byte.
    row = conn.execute("SELECT * FROM sessions WHERE chat_id = 1").fetchone()
    assert row["activity_name"] == "laundry"
    assert row["source_intent"] == "start_stop"
    assert row["status"] == "open"

    # No foreign-key violations introduced by the rebuild.
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

    # The new 'expense' value is now accepted.
    conn.execute(
        """INSERT INTO sessions
           (chat_id, pillar, activity_name, raw_text, source_intent, start_ts, status)
           VALUES (1, 'finance', 'coffee shop', 'test', 'expense', '2026-01-02T00:00:00.000000Z', 'closed')"""
    )
    conn.commit()

    # An invalid value is still rejected.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO sessions
               (chat_id, pillar, activity_name, raw_text, source_intent, start_ts, status)
               VALUES (1, 'finance', 'bad', 'test', 'not_a_real_intent', '2026-01-03T00:00:00.000000Z', 'closed')"""
        )
    conn.close()
