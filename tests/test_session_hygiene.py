from datetime import datetime, timedelta, timezone

from src.db import get_conn
from src.session_hygiene import close_stale_open_sessions

FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _insert_open_session(chat_id, activity_name, hours_ago):
    start_ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime(FMT)
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO sessions
               (chat_id, pillar, activity_name, raw_text, source_intent, start_ts, status)
               VALUES (?, 'uncategorized', ?, 'test', 'start_stop', ?, 'open')""",
            (chat_id, activity_name, start_ts),
        )


def test_closes_only_sessions_past_threshold(tmp_db):
    chat_id = 30
    _insert_open_session(chat_id, "stale", hours_ago=13)
    _insert_open_session(chat_id, "fresh", hours_ago=2)

    closed = close_stale_open_sessions(threshold_hours=12)
    assert closed == 1

    with get_conn() as conn:
        stale = conn.execute(
            "SELECT status, notes FROM sessions WHERE chat_id = ? AND activity_name = 'stale'", (chat_id,)
        ).fetchone()
        fresh = conn.execute(
            "SELECT status FROM sessions WHERE chat_id = ? AND activity_name = 'fresh'", (chat_id,)
        ).fetchone()

    assert stale["status"] == "closed"
    assert "auto-closed" in stale["notes"]
    assert fresh["status"] == "open"
