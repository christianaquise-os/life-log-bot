import sqlite3

from src.db import get_conn
from src import db_backup


def test_backup_copies_all_rows(tmp_db):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO sessions
               (chat_id, pillar, activity_name, raw_text, source_intent, start_ts, status)
               VALUES (1, 'uncategorized', 'laundry', 'test', 'start_stop', '2026-01-01T00:00:00.000000Z', 'open')"""
        )

    backup_path = db_backup.backup()
    assert backup_path.exists()

    conn = sqlite3.connect(backup_path)
    row = conn.execute("SELECT activity_name FROM sessions WHERE chat_id = 1").fetchone()
    conn.close()
    assert row[0] == "laundry"


def test_prune_keeps_only_last_n(tmp_db):
    backup_dir = db_backup._backup_dir()
    for i in range(20):
        (backup_dir / f"activity-2026010{i:02d}T000000Z.db").touch()

    deleted = db_backup.prune(keep_last_n=14)

    remaining = sorted(backup_dir.glob("activity-*.db"))
    assert deleted == 6
    assert len(remaining) == 14
