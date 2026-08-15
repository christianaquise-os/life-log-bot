import logging
from datetime import datetime, timedelta, timezone

from src import notion_sync
from src.db import get_conn

logger = logging.getLogger(__name__)

FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def close_stale_open_sessions(threshold_hours: int = 12) -> int:
    """Data hygiene only -- never sends a Telegram message. Auto-closes any
    session left open longer than threshold_hours (e.g. the bot crashed
    before the user said "done"), so it stops skewing pillar totals and
    disambiguation candidate lists forever. Marked distinctly in `notes` so
    it's never mistaken for a real close in the data or in Notion.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=threshold_hours)).strftime(FMT)
    closed_count = 0

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, start_ts, notes FROM sessions WHERE status = 'open' AND start_ts < ?",
            (cutoff,),
        ).fetchall()

        for row in rows:
            start_dt = datetime.strptime(row["start_ts"], FMT).replace(tzinfo=timezone.utc)
            end_ts = (start_dt + timedelta(hours=threshold_hours)).strftime(FMT)
            marker = "auto-closed: left open too long"
            notes = f"{row['notes']} | {marker}" if row["notes"] else marker
            conn.execute(
                """UPDATE sessions
                   SET end_ts = ?, duration_seconds = ?, status = 'closed', notes = ?, updated_at = ?
                   WHERE id = ?""",
                (end_ts, threshold_hours * 3600, notes, datetime.now(timezone.utc).strftime(FMT), row["id"]),
            )
            closed_count += 1

    for row in rows:
        notion_sync.enqueue(row["id"])

    if closed_count:
        logger.info("auto-closed %d stale open session(s)", closed_count)
    return closed_count
