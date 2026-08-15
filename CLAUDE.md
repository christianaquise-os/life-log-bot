# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## What this is

A single always-on Python process that runs a Telegram bot for personal
life tracking. The core is activity/time logging via natural language
("started laundry", "done", "read for 45 min") — the bot infers what
Christian means, logs it, and tracks running totals per life pillar. Layered
on top: mood/journal check-ins, passive habit tracking with streaks, a movie
watchlist, and receipt-photo expense logging. Every new pillar beyond the
core is a **dedicated Telegram slash command**, not a new intent on
`src/claude_extract.py`'s extraction tool — see *Adding a new pillar* below
for why that boundary is load-bearing, not incidental.

**SQLite (`data/activity.db`) is the only source of truth.** Notion is a
best-effort, read-only mirror — see *Why SQLite is authoritative* below for
the mechanism that guarantees Notion can never block or corrupt logging.

There is no build step. `pip install -r requirements.txt` into `.venv/`, then
run `python main.py` (after `python scripts/init_db.py` once).

## Person / usage context

Solo user (Christian), Barcelona, `Europe/Madrid` timezone (see
`~/nutrition-plan-export/CLAUDE.md` for that context — this project is a
sibling, not a subfolder, and this repo never touches `nutrition-plan-export/`
or `My_finance/Recibos/`). The bot is reachable only via the Telegram chat ID
in `TELEGRAM_ALLOWED_CHAT_ID` (`.env`) — every other chat is silently
ignored. This is the only auth boundary; there's no user/password layer
because there's exactly one intended user.

## The pillar taxonomy

Six life pillars plus a default bucket, defined in `migrations/001_init.sql`
and mirrored in `src/config.py::PILLARS`:

1. `nutrition_body` — Nutrition & Body
2. `finance` — Finance
3. `mind_wellbeing` — Mind & Well-being
4. `relationships` — Relationships (sub-tracks: `girlfriend`, `friends_family`)
5. `career_learning` — Career & Learning
6. `leisure` — Leisure
7. `uncategorized` — the default for chores and anything the extractor isn't
   confident about (see `src/claude_extract.py`). Chores default here rather
   than being forced into Leisure or Career, because forcing a guess would
   corrupt pillar totals; better an honest "uncategorized" than a wrong pillar.

## Adding a new pillar

`src/claude_extract.py`'s `EXTRACTION_TOOL` is deliberately narrow — five
intents for the core activity-logging loop, nothing else. It stays that way:
bloating its schema has a real cost (Claude Haiku 4.5 needs a 4096-token
stable prefix before Anthropic's prompt caching would even help, so there's
no caching upside) and risks cross-intent ambiguity between activity logging
and whatever the new pillar is. Every pillar added after v1 is instead a
**dedicated slash command** with its own handler in `src/telegram_bot.py`
and its own module in `src/`:

- **Mood/journal** (`src/mood.py`, `/mood`) — a 1-10 score and/or a note.
  The one pillar that *does* feed the digest: `digest.py::_tally()` reads
  `mood_entries` directly, and `_compute_tally_hash()` includes it so the
  digest cache still invalidates correctly when a mood entry changes.
- **Habits** (`src/habits.py`, `/newhabit`, `/log`, `/habits`) — passive
  logging only, no proactive reminders, ever. Streaks are pure local-date
  arithmetic (`_compute_streak`); the "never miss twice" framing only
  surfaces in the `/log` reply, never as an unprompted message.
- **Movies** (`src/movies.py`, `/addmovie`, `/watched`, `/watchlist`) — the
  one pillar with an external dependency (`OMDB_API_KEY`, optional, same
  "reply gracefully if unset" convention as the Notion vars below).
- **Receipts/finance** (`src/receipt_extract.py` + `src/receipts.py`,
  photo handler) — the one pillar that *does* write into `sessions`
  (pillar `finance`, `source_intent='expense'`, zero duration) so it flows
  through the existing digest/Notion machinery for free, alongside its own
  `expenses` table for the money-specific fields (merchant/amount/currency).
  This is why `sessions.source_intent`'s CHECK constraint had to grow a
  third value — see *Extending a CHECK constraint* below, since that's the
  one migration in this repo that isn't a plain `CREATE`/`ALTER ADD COLUMN`.

Whether a new pillar should also write a `sessions` row (free digest/Notion
integration, like receipts) or live entirely in its own table (like habits)
depends on whether it's naturally a point-in-time or duration event that
belongs in a pillar total — habits and movies aren't, mood and expenses are.

## Extending a CHECK constraint

SQLite has no `ALTER TABLE ... ALTER CHECK`. `migrations/009_*.sql` is the
reference pattern for when a future change needs to widen one: create a
`_new` table with the updated CHECK, copy every row across, drop the old
table, rename, then recreate any indexes (dropped along with the old table).
`tests/test_migration_009.py` is the reference pattern for testing one —
apply migrations up to but not including the rebuild, seed a row under the
old constraint, apply the rebuild, then assert the row survived and both the
new and old constraint values behave correctly.

## Why SQLite is authoritative and Notion is not

Every write to `sessions` happens in SQLite first, inside the request path.
Notion sync (`src/notion_sync.py`) is only ever reached through
`notion_sync.enqueue(session_id)`, which submits to a background thread pool
and returns immediately — nothing in the request path awaits it or checks its
result. If Notion is down, misconfigured, or the API key is missing entirely,
`enqueue` silently no-ops or fails in the background; the SQLite write and
the Telegram reply already happened.

Recovery from a Notion outage is automatic: `src/scheduler.py` runs
`notion_sync.resync_unsynced()` every 10 minutes, which re-pushes any closed
session still missing a `notion_page_id`. Never call `notion_sync.push()`
directly from request-handling code — only `enqueue()`.

## The ambiguity-handling contract

"Done" (or "finished") must never silently no-op. `src/flows.py::_handle_intent`
enforces this:

- **0 open sessions** → the bot asks what was just finished and stores a
  `pending_actions` row (`kind='confirm_intent'`) so the *next* message is
  known to be a clarification, not a fresh unrelated message.
- **1 open session** → closes it directly.
- **2+ open sessions** → the bot lists them and asks which one, storing
  `kind='disambiguate_stop'` with the candidate IDs.

`pending_actions` is a real table, not an in-process dict, specifically so a
bot restart mid-clarification doesn't lose the "what did you mean" state —
the next message from that chat is checked against it before going through
the LLM extractor again (see `flows.py::route_message`).

## Timestamp convention

Everything in `sessions.start_ts` / `end_ts` is stored as **UTC ISO-8601**
(`strftime('%Y-%m-%dT%H:%M:%S.%fZ')` format, matching Python's
`datetime.now(timezone.utc)` strftime call in `flows.py::now_utc_iso`).
Local-time boundaries — "what counts as today" for the digest, `TIMEZONE`
in `.env` — are computed only in query/display code (`src/digest.py`), never
in storage. Don't let a local-time value leak into a stored timestamp.

**Use the message's real send time, not processing time.** `route_message()`
threads a single `event_ts` (Telegram's `update.message.date`, not
`datetime.now()`) through every function that stamps a domain timestamp —
`_open_session`, `_close_session`, `_log_completed`, `_resolve_disambiguate_stop`.
This matters because the bot can process a backlog after being offline: two
messages sent minutes apart but drained within milliseconds of each other on
restart must still produce a correct duration, not a near-zero one. Every
new pillar's Telegram handler follows the same pattern — read
`update.message.date`, pass it down, never call `datetime.now()` for a
domain event. `raw_messages.telegram_sent_at` stores this separately from
`received_at` (processing time) specifically so this class of bug is
directly visible by comparing the two columns.

## Working conventions

- **Adding a migration**: create a new numbered file in `migrations/`
  (`010_whatever.sql`, continuing the sequence), then re-run
  `python scripts/init_db.py` — it applies only files not yet recorded in
  `schema_migrations`.
- **Tests**: `pytest` (`pip install -r requirements-dev.txt` first) — fast,
  free, zero live API calls. Every Claude call site is mocked; the
  `tmp_db` fixture in `tests/conftest.py` isolates each test's database.
  **Patch `src.db.DB_PATH`, not `src.config.DB_PATH`** — `src/db.py` binds
  the name into its own namespace at import time, so patching the original
  has no effect. `scripts/test_extraction.py` is a separate, deliberately
  live-API sanity script — run it after touching `claude_extract.py`, not
  as part of `pytest`.
- **Manual verification**: see the verification table in `README.md`. The
  short version: exercise the bot via Telegram, then check the actual SQLite
  rows (`sqlite3 data/activity.db "select ..."`) rather than trusting the
  bot's own reply text — the two can disagree, and that disagreement is the
  bug to find.
- **Cost visibility**: `python scripts/usage_report.py` sums today's/this
  month's token spend from the `api_usage` table (populated by
  `src/api_usage.py::record`, called after every Claude API call). Never
  load-bearing — a recording failure is logged and swallowed, never breaks
  the actual bot response.
- **Backups**: `python scripts/backup_db.py` for an on-demand backup; the
  scheduler also runs one daily at 3am, keeping the last 14
  (`src/db_backup.py`, `data/backups/`, gitignored).
- **Don't touch** `~/nutrition-plan-export/` or `~/My_finance/Recibos/` —
  unrelated existing projects that happen to live as sibling directories.

## Deployment note

The always-on runner is either this Mac (`launchd`, template in
`deploy/com.christian.lifelogbot.plist`) or a small VPS (`systemd`, template
in `deploy/lifelogbot.service`). Neither is baked in as the "right" choice —
pick one and adjust the paths in the template to match.
