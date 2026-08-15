from datetime import datetime, timedelta, timezone

from src.db import get_conn
from src.flows import route_message

FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def fake_extract_intent(raw_text, now_local_iso, open_activity_names):
    return {"intent": "unclear", "activity_name": "<UNKNOWN>", "pillar_guess": "uncategorized", "confidence": "low"}


def test_expired_pending_action_is_ignored(tmp_db, monkeypatch):
    monkeypatch.setattr("src.flows.extract_intent", fake_extract_intent)
    chat_id = 20

    with get_conn() as conn:
        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime(FMT)
        conn.execute(
            "INSERT INTO pending_actions (chat_id, kind, payload_json, expires_at) VALUES (?, 'confirm_intent', '{}', ?)",
            (chat_id, past),
        )

    # Should NOT be treated as a disambiguate_stop resolution -- the pending
    # row is expired, so this goes through fresh (unclear) extraction instead.
    reply = route_message(chat_id, "hello there", 1)
    assert "Not sure what you mean" in reply

    with get_conn() as conn:
        remaining = conn.execute("SELECT COUNT(*) AS c FROM pending_actions WHERE chat_id = ?", (chat_id,)).fetchone()[
            "c"
        ]
    # The expired row was cleared; a new pending_action may have been created
    # by the unclear-intent path, but never more than one live row.
    assert remaining <= 1


def test_unexpired_pending_action_still_resolves(tmp_db, monkeypatch):
    chat_id = 21

    def fake_start(raw_text, now_local_iso, open_activity_names):
        return {"intent": "start", "activity_name": "laundry", "pillar_guess": "uncategorized", "confidence": "high"}

    def fake_stop(raw_text, now_local_iso, open_activity_names):
        return {
            "intent": "stop",
            "activity_name": "<UNKNOWN>",
            "pillar_guess": "uncategorized",
            "confidence": "medium",
            "target_hint": None,
        }

    def fake_start2(raw_text, now_local_iso, open_activity_names):
        return {"intent": "start", "activity_name": "cooking", "pillar_guess": "uncategorized", "confidence": "high"}

    monkeypatch.setattr("src.flows.extract_intent", fake_start)
    route_message(chat_id, "started laundry", 1)
    monkeypatch.setattr("src.flows.extract_intent", fake_start2)
    route_message(chat_id, "started cooking", 2)
    monkeypatch.setattr("src.flows.extract_intent", fake_stop)
    ambiguous = route_message(chat_id, "done", 3)
    assert "Which one" in ambiguous

    resolve = route_message(chat_id, "laundry", 4)
    assert "Closed laundry" in resolve
