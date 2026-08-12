-- Pillars are a real table, not a hardcoded enum, so summary queries never
-- need to special-case an "uncategorized" NULL — every session has a valid
-- pillar row to join against.
CREATE TABLE pillars (
    key         TEXT PRIMARY KEY,
    label       TEXT NOT NULL,
    sort_order  INTEGER NOT NULL
);

INSERT INTO pillars (key, label, sort_order) VALUES
    ('nutrition_body',   'Nutrition & Body',    1),
    ('finance',          'Finance',             2),
    ('mind_wellbeing',   'Mind & Well-being',   3),
    ('relationships',    'Relationships',       4),
    ('career_learning',  'Career & Learning',   5),
    ('leisure',          'Leisure',             6),
    ('uncategorized',    'Uncategorized',       7);

-- Multiple sessions can be open at once (laundry running while cooking is
-- real life) — see flows.py for how "done" disambiguates between them.
CREATE TABLE sessions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id             INTEGER NOT NULL,
    pillar              TEXT NOT NULL REFERENCES pillars(key),
    sub_track           TEXT NULL CHECK (
                            sub_track IS NULL
                            OR (pillar = 'relationships' AND sub_track IN ('girlfriend', 'friends_family'))
                        ),
    activity_name       TEXT NOT NULL,
    raw_text            TEXT NOT NULL,
    source_intent       TEXT NOT NULL CHECK (source_intent IN ('start_stop', 'log_duration')),
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

CREATE INDEX idx_sessions_open_by_chat ON sessions (chat_id, status) WHERE status = 'open';
CREATE INDEX idx_sessions_closed_by_day ON sessions (chat_id, start_ts) WHERE status = 'closed';
CREATE INDEX idx_sessions_notion_unsynced ON sessions (status, notion_page_id) WHERE status = 'closed' AND notion_page_id IS NULL;

-- Survives process restarts: an outstanding clarification the bot asked for
-- (e.g. "which of these 2 things are you done with?"), so a mid-conversation
-- crash/restart doesn't silently drop the ambiguity-resolution state.
CREATE TABLE pending_actions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id         INTEGER NOT NULL,
    kind            TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    expires_at      TEXT NULL
);

-- Audit log of every inbound message and what the extractor decided. Cheap,
-- and it's the thing to grep when the parser does something weird.
CREATE TABLE raw_messages (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id             INTEGER NOT NULL,
    telegram_message_id INTEGER NULL,
    raw_text            TEXT NOT NULL,
    received_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    parsed_intent_json  TEXT NULL,
    resulting_action    TEXT NULL
);

-- Idempotency + audit for the nightly/on-demand digest.
CREATE TABLE daily_digests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id         INTEGER NOT NULL,
    digest_date     TEXT NOT NULL,
    content_text    TEXT NOT NULL,
    generated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    sent_at         TEXT NULL,
    UNIQUE (chat_id, digest_date)
);
