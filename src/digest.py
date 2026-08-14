import hashlib
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic

from src.config import ANTHROPIC_API_KEY, TIMEZONE
from src.db import get_conn

logger = logging.getLogger(__name__)

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


def _compute_tally_hash(tally: dict) -> str:
    # Normalize independently of the SQL row order (_tally()'s query has no
    # ORDER BY) so two calls against identical underlying data always hash
    # the same.
    normalized = {
        "by_pillar": dict(sorted(tally["by_pillar"].items())),
        "activities": sorted(
            (
                {"activity": a["activity"], "pillar": a["pillar"], "seconds": a["seconds"] or 0}
                for a in tally["activities"]
            ),
            key=lambda a: (a["pillar"], a["activity"], a["seconds"]),
        ),
    }
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_digest(chat_id: int, date_local: str | None = None) -> str:
    date_local = _today_local(date_local)
    tally = _tally(chat_id, date_local)
    tally_hash = _compute_tally_hash(tally)

    with get_conn() as conn:
        cached = conn.execute(
            "SELECT content_text, tally_hash FROM daily_digests WHERE chat_id = ? AND digest_date = ?",
            (chat_id, date_local),
        ).fetchone()
    if cached and cached["tally_hash"] == tally_hash:
        logger.info("digest cache hit for chat_id=%s date=%s", chat_id, date_local)
        return cached["content_text"]

    if not tally["activities"]:
        content = f"Nothing logged yet for {date_local}."
    else:
        lines = [f"Date: {date_local}"]
        for pillar, seconds in sorted(tally["by_pillar"].items(), key=lambda kv: -kv[1]):
            minutes = round(seconds / 60)
            lines.append(f"- {PILLAR_LABELS.get(pillar, pillar)}: {minutes} min")
        lines.append("Activities:")
        for a in tally["activities"]:
            minutes = round((a["seconds"] or 0) / 60)
            lines.append(f"- {a['activity']} ({PILLAR_LABELS.get(a['pillar'], a['pillar'])}, {minutes} min)")
        tally_text = "\n".join(lines)

        logger.info("digest cache miss for chat_id=%s date=%s; calling Claude", chat_id, date_local)
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=300,
            system=PERSONALITY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": tally_text}],
        )
        text_block = next((b.text for b in response.content if b.type == "text"), "")
        content = text_block or tally_text

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO daily_digests (chat_id, digest_date, content_text, tally_hash)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(chat_id, digest_date) DO UPDATE SET
                   content_text = excluded.content_text,
                   tally_hash = excluded.tally_hash""",
            (chat_id, date_local, content, tally_hash),
        )
    return content


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
    return build_digest(chat_id, date_local)


def mark_sent(chat_id: int, date_local: str | None = None) -> None:
    date_local = _today_local(date_local)
    with get_conn() as conn:
        conn.execute(
            "UPDATE daily_digests SET sent_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
            "WHERE chat_id = ? AND digest_date = ?",
            (chat_id, date_local),
        )
