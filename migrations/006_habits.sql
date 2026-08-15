-- Passive habit tracking: define a habit, log completions, track streaks.
-- No proactive reminders by design -- the bot never messages you unprompted
-- about a missed habit; the "never miss twice" framing only ever surfaces in
-- the reply to a /log call.
CREATE TABLE habits (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    INTEGER NOT NULL,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    active     INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

-- UNIQUE(habit_id, logged_local_date) is the "once per day" enforcement --
-- application code pre-checks before insert so a repeat /log gets a friendly
-- "already logged today" reply instead of a raw IntegrityError.
CREATE TABLE habit_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id          INTEGER NOT NULL REFERENCES habits(id),
    chat_id           INTEGER NOT NULL,
    logged_local_date TEXT NOT NULL,
    logged_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (habit_id, logged_local_date)
);

CREATE INDEX idx_habit_logs_habit_date ON habit_logs (habit_id, logged_local_date);
