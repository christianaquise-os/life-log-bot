-- Quick mood check-ins: a 1-10 score and/or a short note. At least one of
-- the two is required (a bare /mood with nothing to say is rejected in
-- application code before it ever reaches here, but the CHECK is a backstop).
CREATE TABLE mood_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL,
    mood_score  INTEGER NULL CHECK (mood_score IS NULL OR (mood_score BETWEEN 1 AND 10)),
    note        TEXT NULL,
    entry_ts    TEXT NOT NULL,
    local_date  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (mood_score IS NOT NULL OR note IS NOT NULL)
);

CREATE INDEX idx_mood_entries_chat_date ON mood_entries (chat_id, local_date);
