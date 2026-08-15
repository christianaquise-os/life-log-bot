from datetime import datetime, timedelta, timezone

from src.db import get_conn
from src.flows import route_message

FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def fake_extract_intent(raw_text, now_local_iso, open_activity_names):
    text = raw_text.strip().lower()
    if text.startswith("started "):
        activity = text[len("started "):].strip()
        return {"intent": "start", "activity_name": activity, "pillar_guess": "uncategorized", "confidence": "high"}
    if text in ("done", "finished", "stop"):
        return {
            "intent": "stop",
            "activity_name": "<UNKNOWN>",
            "pillar_guess": "uncategorized",
            "confidence": "medium",
            "target_hint": None,
        }
    if text.startswith("done with "):
        hint = text[len("done with "):].strip()
        return {
            "intent": "stop",
            "activity_name": hint,
            "pillar_guess": "uncategorized",
            "confidence": "high",
            "target_hint": hint,
        }
    return {"intent": "unclear", "activity_name": "<UNKNOWN>", "pillar_guess": "uncategorized", "confidence": "low"}


def test_open_close_duration_math(tmp_db, monkeypatch):
    monkeypatch.setattr("src.flows.extract_intent", fake_extract_intent)
    chat_id = 1
    t0 = datetime.now(timezone.utc)
    t1 = t0 + timedelta(minutes=10)

    route_message(chat_id, "started laundry", 1, t0.strftime(FMT))
    reply = route_message(chat_id, "done", 2, t1.strftime(FMT))

    assert "10m" in reply
    with get_conn() as conn:
        row = conn.execute("SELECT duration_seconds FROM sessions WHERE chat_id = ?", (chat_id,)).fetchone()
    assert row["duration_seconds"] == 600


def test_dedup(tmp_db, monkeypatch):
    monkeypatch.setattr("src.flows.extract_intent", fake_extract_intent)
    chat_id = 2

    r1 = route_message(chat_id, "started laundry", 100)
    r2 = route_message(chat_id, "started laundry", 100)

    assert r1 != r2
    assert "didn't log it twice" in r2
    with get_conn() as conn:
        raw_count = conn.execute(
            "SELECT COUNT(*) AS c FROM raw_messages WHERE chat_id = ? AND telegram_message_id = 100", (chat_id,)
        ).fetchone()["c"]
        session_count = conn.execute("SELECT COUNT(*) AS c FROM sessions WHERE chat_id = ?", (chat_id,)).fetchone()[
            "c"
        ]
    assert raw_count == 1
    assert session_count == 1


def test_disambiguation_flow(tmp_db, monkeypatch):
    monkeypatch.setattr("src.flows.extract_intent", fake_extract_intent)
    chat_id = 3

    route_message(chat_id, "started laundry", 1)
    route_message(chat_id, "started cooking", 2)
    ambiguous_reply = route_message(chat_id, "done", 3)
    assert "Which one" in ambiguous_reply

    resolve_reply = route_message(chat_id, "1", 4)
    assert "Closed laundry" in resolve_reply

    with get_conn() as conn:
        laundry = conn.execute(
            "SELECT status FROM sessions WHERE chat_id = ? AND activity_name = 'laundry'", (chat_id,)
        ).fetchone()
        cooking = conn.execute(
            "SELECT status FROM sessions WHERE chat_id = ? AND activity_name = 'cooking'", (chat_id,)
        ).fetchone()
    assert laundry["status"] == "closed"
    assert cooking["status"] == "open"


def test_send_time_threading(tmp_db, monkeypatch):
    """The exact backlog-drain scenario: two route_message() calls happen
    back-to-back in wall-clock time, but their message_sent_at values are
    5 minutes apart -- duration must reflect the simulated send-time gap,
    not the near-zero real elapsed time between the two calls."""
    monkeypatch.setattr("src.flows.extract_intent", fake_extract_intent)
    chat_id = 4
    t0 = datetime.now(timezone.utc) - timedelta(hours=1)
    t1 = t0 + timedelta(minutes=5)

    route_message(chat_id, "started laundry", 1, t0.strftime(FMT))
    route_message(chat_id, "done", 2, t1.strftime(FMT))

    with get_conn() as conn:
        row = conn.execute("SELECT duration_seconds FROM sessions WHERE chat_id = ?", (chat_id,)).fetchone()
    assert row["duration_seconds"] == 300


def test_no_timestamp_arg_falls_back_to_now(tmp_db, monkeypatch):
    monkeypatch.setattr("src.flows.extract_intent", fake_extract_intent)
    chat_id = 5

    route_message(chat_id, "started cooking")

    with get_conn() as conn:
        row = conn.execute("SELECT start_ts FROM sessions WHERE chat_id = ?", (chat_id,)).fetchone()
    start_ts = datetime.strptime(row["start_ts"], FMT).replace(tzinfo=timezone.utc)
    assert (datetime.now(timezone.utc) - start_ts).total_seconds() < 5
