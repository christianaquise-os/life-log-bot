from datetime import datetime, timezone

from src.db import get_conn
from src.mood import log_mood, USAGE

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def test_score_and_note(tmp_db):
    reply = log_mood(1, "7 felt good after the gym", NOW)
    assert "7/10" in reply
    assert "felt good after the gym" in reply
    with get_conn() as conn:
        row = conn.execute("SELECT mood_score, note FROM mood_entries WHERE chat_id = 1").fetchone()
    assert row["mood_score"] == 7
    assert row["note"] == "felt good after the gym"


def test_score_only(tmp_db):
    reply = log_mood(2, "5", NOW)
    assert "5/10" in reply
    with get_conn() as conn:
        row = conn.execute("SELECT mood_score, note FROM mood_entries WHERE chat_id = 2").fetchone()
    assert row["mood_score"] == 5
    assert row["note"] is None


def test_note_only_no_score(tmp_db):
    reply = log_mood(3, "rough day, nothing went right", NOW)
    assert "rough day" in reply
    with get_conn() as conn:
        row = conn.execute("SELECT mood_score, note FROM mood_entries WHERE chat_id = 3").fetchone()
    assert row["mood_score"] is None
    assert row["note"] == "rough day, nothing went right"


def test_empty_args_returns_usage(tmp_db):
    assert log_mood(4, "", NOW) == USAGE
    assert log_mood(4, "   ", NOW) == USAGE


def test_out_of_range_score_rejected(tmp_db):
    reply = log_mood(5, "15 way too happy", NOW)
    assert "between 1 and 10" in reply
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM mood_entries WHERE chat_id = 5").fetchone()["c"]
    assert count == 0
