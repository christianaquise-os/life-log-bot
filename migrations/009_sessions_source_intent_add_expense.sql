-- SQLite has no ALTER TABLE ... ALTER CHECK. Rebuild sessions with the
-- source_intent CHECK expanded to include 'expense' (src/receipts.py inserts
-- a sessions row per logged receipt so it appears in the existing
-- digest/pillar-total machinery for free). Foreign keys are disabled for the
-- duration of the rebuild per SQLite's documented ALTER-TABLE procedure --
-- not strictly required today (nothing currently holds an incoming FK to
-- sessions), but keeps this migration correct if one is ever added.
-- executescript() issues an implicit COMMIT of any pending transaction
-- before running this script, so the PRAGMA below is not "mid-transaction"
-- and takes effect for the statements that follow.
PRAGMA foreign_keys = OFF;

CREATE TABLE sessions_new (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id             INTEGER NOT NULL,
    pillar              TEXT NOT NULL REFERENCES pillars(key),
    sub_track           TEXT NULL CHECK (
                            sub_track IS NULL
                            OR (pillar = 'relationships' AND sub_track IN ('girlfriend', 'friends_family'))
                        ),
    activity_name       TEXT NOT NULL,
    raw_text            TEXT NOT NULL,
    source_intent       TEXT NOT NULL CHECK (source_intent IN ('start_stop', 'log_duration', 'expense')),
    start_ts            TEXT NOT NULL,
    end_ts              TEXT NULL,
    duration_seconds    INTEGER NULL,
    status              TEXT NOT NULL CHECK (status IN ('open', 'closed')) DEFAULT 'open',
    notes               TEXT NULL,
    notion_page_id      TEXT NULL,
    notion_synced_at    TEXT NULL,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

INSERT INTO sessions_new
    (id, chat_id, pillar, sub_track, activity_name, raw_text, source_intent,
     start_ts, end_ts, duration_seconds, status, notes, notion_page_id,
     notion_synced_at, created_at, updated_at)
SELECT
    id, chat_id, pillar, sub_track, activity_name, raw_text, source_intent,
    start_ts, end_ts, duration_seconds, status, notes, notion_page_id,
    notion_synced_at, created_at, updated_at
FROM sessions;

DROP TABLE sessions;
ALTER TABLE sessions_new RENAME TO sessions;

-- Dropping the old table dropped its indexes -- recreate them verbatim.
CREATE INDEX idx_sessions_open_by_chat ON sessions (chat_id, status) WHERE status = 'open';
CREATE INDEX idx_sessions_closed_by_day ON sessions (chat_id, start_ts) WHERE status = 'closed';
CREATE INDEX idx_sessions_notion_unsynced ON sessions (status, notion_page_id) WHERE status = 'closed' AND notion_page_id IS NULL;

PRAGMA foreign_keys = ON;
