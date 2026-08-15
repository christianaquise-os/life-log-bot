-- Essentials only: merchant, date, total amount -- no line items (v1 scope).
-- The receipt photo itself is never stored locally; telegram_file_id lets it
-- be re-fetched from Telegram if ever needed.
CREATE TABLE expenses (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id          INTEGER NOT NULL,
    merchant         TEXT NOT NULL,
    amount           REAL NOT NULL,
    currency         TEXT NOT NULL DEFAULT 'EUR',
    purchased_at     TEXT NOT NULL,
    raw_text         TEXT NULL,
    telegram_file_id TEXT NOT NULL,
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX idx_expenses_chat_date ON expenses (chat_id, purchased_at);
