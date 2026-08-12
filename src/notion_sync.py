import logging
from concurrent.futures import ThreadPoolExecutor

from notion_client import Client

from src.config import NOTION_API_KEY, NOTION_DATABASE_ID
from src.db import get_conn

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)


def _client():
    if not NOTION_API_KEY:
        return None
    return Client(auth=NOTION_API_KEY)


def enqueue(session_id: int) -> None:
    """Fire-and-forget: schedule a Notion push, never block the caller."""
    _executor.submit(_safe_push, session_id)


def _safe_push(session_id: int) -> None:
    try:
        push(session_id)
    except Exception:
        logger.exception("notion sync failed for session %s; will retry via sweep", session_id)


def push(session_id: int) -> None:
    client = _client()
    if client is None or not NOTION_DATABASE_ID:
        return

    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None or row["status"] != "closed":
            return

        existing = client.databases.query(
            database_id=NOTION_DATABASE_ID,
            filter={"property": "SQLite ID", "number": {"equals": row["id"]}},
        )
        properties = _build_properties(row)

        if existing["results"]:
            page_id = existing["results"][0]["id"]
            client.pages.update(page_id=page_id, properties=properties)
        else:
            page = client.pages.create(parent={"database_id": NOTION_DATABASE_ID}, properties=properties)
            page_id = page["id"]

        conn.execute(
            "UPDATE sessions SET notion_page_id = ?, notion_synced_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
            "WHERE id = ?",
            (page_id, row["id"]),
        )


def _build_properties(row) -> dict:
    properties = {
        "Name": {"title": [{"text": {"content": row["activity_name"]}}]},
        "Pillar": {"select": {"name": row["pillar"]}},
        "Start": {"date": {"start": row["start_ts"]}},
        "Source": {"select": {"name": row["source_intent"]}},
        "Raw text": {"rich_text": [{"text": {"content": row["raw_text"][:2000]}}]},
        "SQLite ID": {"number": row["id"]},
    }
    if row["end_ts"]:
        properties["End"] = {"date": {"start": row["end_ts"]}}
    if row["duration_seconds"] is not None:
        properties["Duration (min)"] = {"number": round(row["duration_seconds"] / 60, 1)}
    if row["sub_track"]:
        properties["Sub-track"] = {"select": {"name": row["sub_track"]}}
    return properties


def resync_unsynced() -> int:
    """Reconciliation sweep: retry any closed session missing a notion_page_id."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM sessions WHERE status = 'closed' AND notion_page_id IS NULL"
        ).fetchall()
    for row in rows:
        _safe_push(row["id"])
    return len(rows)
