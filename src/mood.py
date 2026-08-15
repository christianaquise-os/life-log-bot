from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.config import TIMEZONE
from src.db import get_conn

USAGE = "Usage: /mood <score 1-10> [note], or /mood <note> with no score."


def _local_date(event_ts: str) -> str:
    dt = datetime.strptime(event_ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")


def log_mood(chat_id: int, args_text: str, event_ts: str) -> str:
    args_text = (args_text or "").strip()
    if not args_text:
        return USAGE

    parts = args_text.split(maxsplit=1)
    score = None
    note = None

    if parts[0].isdigit():
        candidate = int(parts[0])
        if not (1 <= candidate <= 10):
            return "Mood score must be between 1 and 10."
        score = candidate
        note = parts[1].strip() if len(parts) > 1 else None
    else:
        note = args_text

    local_date = _local_date(event_ts)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO mood_entries (chat_id, mood_score, note, entry_ts, local_date) VALUES (?, ?, ?, ?, ?)",
            (chat_id, score, note, event_ts, local_date),
        )

    if score is not None and note:
        return f'Logged mood {score}/10 — "{note}"'
    if score is not None:
        return f"Logged mood {score}/10"
    return f'Logged: "{note}"'
