-- Adds a stable content hash of the day's tally so build_digest() can skip
-- the Claude call when nothing has changed since the last generated digest
-- for that (chat_id, digest_date). NULL for pre-existing rows -- they're
-- simply treated as a cache miss once, then backfilled on next write.
ALTER TABLE daily_digests ADD COLUMN tally_hash TEXT NULL;

-- Supports the message-level dedup check in flows.py::route_message
-- (lookup by chat_id + telegram_message_id before inserting a new raw_messages row).
CREATE INDEX idx_raw_messages_dedup ON raw_messages (chat_id, telegram_message_id)
    WHERE telegram_message_id IS NOT NULL;
