import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from src import notion_sync
from src.claude_extract import extract_intent
from src.config import TIMEZONE
from src.db import get_conn


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def now_local_iso() -> str:
    return datetime.now(ZoneInfo(TIMEZONE)).isoformat()


def _parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def _get_open_sessions(conn, chat_id):
    return conn.execute(
        "SELECT * FROM sessions WHERE chat_id = ? AND status = 'open' ORDER BY start_ts",
        (chat_id,),
    ).fetchall()


def _get_pending_action(conn, chat_id):
    return conn.execute(
        "SELECT * FROM pending_actions WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
        (chat_id,),
    ).fetchone()


def _clear_pending_action(conn, pending_id) -> None:
    conn.execute("DELETE FROM pending_actions WHERE id = ?", (pending_id,))


def _create_pending_action(conn, chat_id, kind, payload) -> None:
    conn.execute(
        "INSERT INTO pending_actions (chat_id, kind, payload_json) VALUES (?, ?, ?)",
        (chat_id, kind, json.dumps(payload)),
    )


def _find_duplicate_reply(conn, chat_id, telegram_message_id) -> str | None:
    """Returns a reply to send if this telegram_message_id was already
    processed for this chat, else None. telegram_message_id=None (e.g. calls
    from scripts/ that don't come from a real Telegram update) always misses."""
    if telegram_message_id is None:
        return None
    row = conn.execute(
        "SELECT id FROM raw_messages WHERE chat_id = ? AND telegram_message_id = ? LIMIT 1",
        (chat_id, telegram_message_id),
    ).fetchone()
    if row is None:
        return None
    return "Already got that one — didn't log it twice."


def _insert_raw_message(conn, chat_id, telegram_message_id, raw_text, telegram_sent_at) -> int:
    cur = conn.execute(
        "INSERT INTO raw_messages (chat_id, telegram_message_id, raw_text, telegram_sent_at) VALUES (?, ?, ?, ?)",
        (chat_id, telegram_message_id, raw_text, telegram_sent_at),
    )
    return cur.lastrowid


def _update_raw_message(conn, raw_id, parsed_intent, resulting_action) -> None:
    conn.execute(
        "UPDATE raw_messages SET parsed_intent_json = ?, resulting_action = ? WHERE id = ?",
        (json.dumps(parsed_intent) if parsed_intent else None, resulting_action, raw_id),
    )


def _open_session(conn, chat_id, pillar, sub_track, activity_name, raw_text, event_ts: str) -> int:
    cur = conn.execute(
        """INSERT INTO sessions
           (chat_id, pillar, sub_track, activity_name, raw_text, source_intent, start_ts, status)
           VALUES (?, ?, ?, ?, ?, 'start_stop', ?, 'open')""",
        (chat_id, pillar, sub_track, activity_name, raw_text, event_ts),
    )
    return cur.lastrowid


def _close_session(conn, session_id, event_ts: str) -> int:
    row = conn.execute("SELECT start_ts FROM sessions WHERE id = ?", (session_id,)).fetchone()
    end_ts = event_ts
    duration = int((_parse_ts(end_ts) - _parse_ts(row["start_ts"])).total_seconds())
    conn.execute(
        "UPDATE sessions SET end_ts = ?, duration_seconds = ?, status = 'closed', updated_at = ? WHERE id = ?",
        (end_ts, duration, now_utc_iso(), session_id),
    )
    return duration


def _log_completed(conn, chat_id, pillar, sub_track, activity_name, raw_text, duration_minutes, event_ts: str) -> int:
    duration_seconds = int(duration_minutes * 60)
    end_ts = event_ts
    start_ts = (_parse_ts(end_ts) - timedelta(seconds=duration_seconds)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    cur = conn.execute(
        """INSERT INTO sessions
           (chat_id, pillar, sub_track, activity_name, raw_text, source_intent,
            start_ts, end_ts, duration_seconds, status)
           VALUES (?, ?, ?, ?, ?, 'log_duration', ?, ?, ?, 'closed')""",
        (chat_id, pillar, sub_track, activity_name, raw_text, start_ts, end_ts, duration_seconds),
    )
    return cur.lastrowid


def _format_duration(seconds: int) -> str:
    minutes = seconds // 60
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    return f"{minutes}m"


def _resolve_disambiguate_stop(conn, chat_id, pending, raw_text, event_ts: str):
    payload = json.loads(pending["payload_json"])
    candidates = payload["candidates"]  # [{id, activity_name}, ...]
    reply_norm = raw_text.strip().lower()

    match = None
    if reply_norm.isdigit():
        idx = int(reply_norm) - 1
        if 0 <= idx < len(candidates):
            match = candidates[idx]
    if match is None:
        for c in candidates:
            if c["activity_name"].lower() in reply_norm:
                match = c
                break

    if match is None:
        listing = "\n".join(f"{i+1}. {c['activity_name']}" for i, c in enumerate(candidates))
        return f"Still not sure which one. Reply with a number:\n{listing}"

    _clear_pending_action(conn, pending["id"])
    duration = _close_session(conn, match["id"], event_ts)
    notion_sync.enqueue(match["id"])
    return f"Closed {match['activity_name']} — {_format_duration(duration)} logged."


def route_message(
    chat_id: int,
    raw_text: str,
    telegram_message_id: int | None = None,
    message_sent_at: str | None = None,
) -> str:
    with get_conn() as conn:
        duplicate_reply = _find_duplicate_reply(conn, chat_id, telegram_message_id)
        if duplicate_reply is not None:
            return duplicate_reply

        event_ts = message_sent_at or now_utc_iso()
        raw_id = _insert_raw_message(conn, chat_id, telegram_message_id, raw_text, message_sent_at)

        pending = _get_pending_action(conn, chat_id)
        if pending is not None:
            if pending["kind"] == "disambiguate_stop":
                reply = _resolve_disambiguate_stop(conn, chat_id, pending, raw_text, event_ts)
                _update_raw_message(conn, raw_id, None, f"resolved:{pending['kind']}")
                return reply
            # Any other pending kind (e.g. confirm_intent) is a soft prompt —
            # clear it and let this message go through normal extraction.
            _clear_pending_action(conn, pending["id"])

        open_sessions = _get_open_sessions(conn, chat_id)
        open_names = [r["activity_name"] for r in open_sessions]
        event_local_iso = _parse_ts(event_ts).astimezone(ZoneInfo(TIMEZONE)).isoformat()
        extraction = extract_intent(raw_text, event_local_iso, open_names)
        reply = _handle_intent(conn, chat_id, raw_text, extraction, open_sessions, event_ts)
        _update_raw_message(conn, raw_id, extraction, reply)
        return reply


def _handle_intent(conn, chat_id, raw_text, extraction, open_sessions, event_ts: str) -> str:
    intent = extraction["intent"]
    activity_name = extraction["activity_name"]
    pillar = extraction["pillar_guess"]
    sub_track = extraction.get("sub_track_guess")

    if intent == "start":
        session_id = _open_session(conn, chat_id, pillar, sub_track, activity_name, raw_text, event_ts)
        return f"Started tracking {activity_name} ({pillar}) ⏳"

    if intent == "stop":
        target_hint = (extraction.get("target_hint") or "").lower()
        candidates = [dict(r) for r in open_sessions]

        if target_hint:
            candidates = [c for c in candidates if target_hint in c["activity_name"].lower()] or candidates

        if len(candidates) == 0:
            _create_pending_action(conn, chat_id, "confirm_intent", {"raw_text": raw_text})
            return "Nothing's running — what did you just finish? (tell me the activity and how long)"

        if len(candidates) == 1:
            session_id = candidates[0]["id"]
            duration = _close_session(conn, session_id, event_ts)
            notion_sync.enqueue(session_id)
            return f"Closed {candidates[0]['activity_name']} — {_format_duration(duration)} logged."

        _create_pending_action(
            conn, chat_id, "disambiguate_stop",
            {"candidates": [{"id": c["id"], "activity_name": c["activity_name"]} for c in candidates]},
        )
        listing = "\n".join(f"{i+1}. {c['activity_name']}" for i, c in enumerate(candidates))
        return f"Which one did you finish?\n{listing}"

    if intent == "log_duration":
        duration_minutes = extraction.get("duration_minutes") or 0
        session_id = _log_completed(
            conn, chat_id, pillar, sub_track, activity_name, raw_text, duration_minutes, event_ts
        )
        notion_sync.enqueue(session_id)
        return f"Logged {activity_name} — {_format_duration(int(duration_minutes * 60))} ({pillar})."

    if intent == "query":
        from src.digest import build_digest

        return build_digest(chat_id)

    _create_pending_action(conn, chat_id, "confirm_intent", {"raw_text": raw_text})
    return "Not sure what you mean — could you rephrase? (e.g. 'started X', 'done', 'did X for 30 min')"
