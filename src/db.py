import sqlite3
from contextlib import contextmanager

from src.config import DB_PATH, MIGRATIONS_DIR


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # This app opens multiple independent connections concurrently by design
    # (asyncio.to_thread per request + background scheduler jobs + nested
    # connections like api_usage.record() opening its own while an outer
    # request connection is still uncommitted) -- a "database is locked"
    # error surfaced live from exactly this pattern. WAL lets readers and a
    # writer proceed without blocking each other; busy_timeout is an
    # explicit backstop for writer-vs-writer contention (Python's sqlite3
    # already retries for 5s by default, but don't rely on that default
    # going unchanged -- state it here).
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def apply_migrations() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        applied = {row["filename"] for row in conn.execute("SELECT filename FROM schema_migrations")}
        pending = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql") if p.name not in applied)
        for filename in pending:
            sql = (MIGRATIONS_DIR / filename).read_text()
            conn.executescript(sql)
            conn.execute("INSERT INTO schema_migrations (filename) VALUES (?)", (filename,))
            print(f"applied migration: {filename}")
