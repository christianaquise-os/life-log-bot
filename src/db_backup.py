import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src import db

logger = logging.getLogger(__name__)

KEEP_LAST_N = 14


def _backup_dir() -> Path:
    backup_dir = db.DB_PATH.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def backup() -> Path:
    """Uses SQLite's online backup API (not a raw file copy) so a mid-write
    database is never copied in a torn state."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest_path = _backup_dir() / f"activity-{timestamp}.db"

    source_conn = sqlite3.connect(db.DB_PATH)
    dest_conn = sqlite3.connect(dest_path)
    try:
        source_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        source_conn.close()
    return dest_path


def prune(keep_last_n: int = KEEP_LAST_N) -> int:
    backups = sorted(_backup_dir().glob("activity-*.db"))
    to_delete = backups[:-keep_last_n] if len(backups) > keep_last_n else []
    for path in to_delete:
        path.unlink()
    return len(to_delete)


def backup_and_prune() -> None:
    """Scheduler entrypoint. A backup failure must never crash the scheduler
    thread -- log and continue."""
    try:
        path = backup()
        deleted = prune()
        logger.info("db backup created: %s (pruned %d old backup(s))", path, deleted)
    except Exception:
        logger.exception("db backup failed")
