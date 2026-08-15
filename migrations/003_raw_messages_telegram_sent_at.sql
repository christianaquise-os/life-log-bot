-- Captures the true Telegram send time (update.message.date) distinctly from
-- received_at (processing time). NULL for non-Telegram callers (scripts/,
-- tests) and for any row inserted before this migration. Exists specifically
-- so a future backlog-drain-after-restart incident can be diagnosed by
-- comparing telegram_sent_at vs received_at directly in raw_messages, instead
-- of only inferring it after the fact from sessions.start_ts/end_ts gaps.
ALTER TABLE raw_messages ADD COLUMN telegram_sent_at TEXT NULL;
