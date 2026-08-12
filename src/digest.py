from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic

from src.config import ANTHROPIC_API_KEY, TIMEZONE
from src.db import get_conn

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

PILLAR_LABELS = {
    "nutrition_body": "Nutrition & Body",
    "finance": "Finance",
    "mind_wellbeing": "Mind & Well-being",
    "relationships": "Relationships",
    "career_learning": "Career & Learning",
    "leisure": "Leisure",
    "uncategorized": "Uncategorized",
}

PERSONALITY_SYSTEM_PROMPT = (
    "You are a personal life-tracking assistant. Your tone is friendly and "
    "motivating day to day, but direct and firm when the user needs a push. "
    "Given a tally of today's logged activities, write 2-4 sentences: what was "
    "logged, the total time per pillar (only pillars with time), and one line "
    "framing today's effort as a concrete accomplishment. No headers, no bullet "
    "lists, just short prose. Do not invent activities not in the tally."
)


def _today_local(date_local: str | None = None) -> str:
    if date_local:
        return date_local
    return datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")


def _tally(chat_id: int, date_local: str) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT pillar, activity_name, duration_seconds, start_ts FROM sessions "
            "WHERE chat_id = ? AND status = 'closed'",
            (chat_id,),
        ).fetchall()

    tz = ZoneInfo(TIMEZONE)
    by_pillar: dict[str, int] = {}
    activities: list[dict] = []
    for row in rows:
        start_local = (
            datetime.strptime(row["start_ts"], "%Y-%m-%dT%H:%M:%S.%fZ")
            .replace(tzinfo=ZoneInfo("UTC"))
            .astimezone(tz)
        )
        if start_local.strftime("%Y-%m-%d") != date_local:
            continue
        by_pillar[row["pillar"]] = by_pillar.get(row["pillar"], 0) + (row["duration_seconds"] or 0)
        activities.append(
            {"activity": row["activity_name"], "pillar": row["pillar"], "seconds": row["duration_seconds"]}
        )

    return {"by_pillar": by_pillar, "activities": activities}


def build_digest(chat_id: int, date_local: str | None = None) -> str:
    date_local = _today_local(date_local)
    tally = _tally(chat_id, date_local)

    if not tally["activities"]:
        return f"Nothing logged yet for {date_local}."

    lines = [f"Date: {date_local}"]
    for pillar, seconds in sorted(tally["by_pillar"].items(), key=lambda kv: -kv[1]):
        minutes = round(seconds / 60)
        lines.append(f"- {PILLAR_LABELS.get(pillar, pillar)}: {minutes} min")
    lines.append("Activities:")
    for a in tally["activities"]:
        minutes = round((a["seconds"] or 0) / 60)
        lines.append(f"- {a['activity']} ({PILLAR_LABELS.get(a['pillar'], a['pillar'])}, {minutes} min)")

    tally_text = "\n".join(lines)

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        system=PERSONALITY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": tally_text}],
    )
    text_block = next((b.text for b in response.content if b.type == "text"), "")
    return text_block or tally_text


def persist_and_get_nightly(chat_id: int) -> str | None:
    """Idempotent scheduled path. Returns None if today's digest was already sent."""
    date_local = _today_local()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT sent_at FROM daily_digests WHERE chat_id = ? AND digest_date = ?",
            (chat_id, date_local),
        ).fetchone()
        if existing and existing["sent_at"]:
            return None

    content = build_digest(chat_id, date_local)

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO daily_digests (chat_id, digest_date, content_text) VALUES (?, ?, ?)
               ON CONFLICT(chat_id, digest_date) DO UPDATE SET content_text = excluded.content_text""",
            (chat_id, date_local, content),
        )
    return content


def mark_sent(chat_id: int, date_local: str | None = None) -> None:
    date_local = _today_local(date_local)
    with get_conn() as conn:
        conn.execute(
            "UPDATE daily_digests SET sent_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
            "WHERE chat_id = ? AND digest_date = ?",
            (chat_id, date_local),
        )
