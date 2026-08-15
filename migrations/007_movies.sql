CREATE TABLE movies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL,
    title       TEXT NOT NULL,
    year        TEXT NULL,
    genre       TEXT NULL,
    imdb_rating TEXT NULL,
    status      TEXT NOT NULL CHECK (status IN ('to_watch', 'watched')) DEFAULT 'to_watch',
    user_rating INTEGER NULL CHECK (user_rating IS NULL OR (user_rating BETWEEN 1 AND 10)),
    added_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    watched_at  TEXT NULL
);

CREATE INDEX idx_movies_chat_status ON movies (chat_id, status);
