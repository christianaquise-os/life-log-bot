-- Records every Claude API call's token usage so cost is auditable without
-- cross-referencing the Anthropic console. Never load-bearing for the bot's
-- actual response -- see src/api_usage.py::record, which swallows its own
-- failures.
CREATE TABLE api_usage (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    called_at                   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    model                       TEXT NOT NULL,
    purpose                     TEXT NOT NULL,
    input_tokens                INTEGER NOT NULL,
    output_tokens                INTEGER NOT NULL,
    cache_read_input_tokens     INTEGER NULL,
    cache_creation_input_tokens INTEGER NULL
);

CREATE INDEX idx_api_usage_called_at ON api_usage (called_at);
