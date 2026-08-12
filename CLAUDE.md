# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## What this is

A single always-on Python process that runs a Telegram bot for personal
activity/time logging. Christian messages the bot in natural language
("started laundry", "done", "read for 45 min") and the bot infers what he
means, logs it, and tracks running totals per life pillar.

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

## Where future pillars/features hook in

This v1 does activity/time logging only. Adding a new *kind* of logged thing
generally does **not** require a schema change:

- **Finance / receipts**: would add its own ingestion path (e.g. a photo
  handler that OCRs a receipt) that writes rows into the existing `sessions`
  table — the `finance` pillar key already exists. No touch to `flows.py`'s
  start/stop/log_duration core.
- **Habit tracking, movie watchlist, mood/journal**: these aren't time-boxed
  activities, so they'd get their own table(s) entirely. Still no change to
  the sessions core.

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

## Working conventions

- **Adding a migration**: create a new numbered file in `migrations/`
  (`002_whatever.sql`), then re-run `python scripts/init_db.py` — it applies
  only files not yet recorded in `schema_migrations`.
- **Manual verification**: see the verification table in `README.md`. The
  short version: exercise the bot via Telegram, then check the actual SQLite
  rows (`sqlite3 data/activity.db "select ..."`) rather than trusting the
  bot's own reply text — the two can disagree, and that disagreement is the
  bug to find.
- **Don't touch** `~/nutrition-plan-export/` or `~/My_finance/Recibos/` —
  unrelated existing projects that happen to live as sibling directories.

## Deployment note

The always-on runner is either this Mac (`launchd`, template in
`deploy/com.christian.lifelogbot.plist`) or a small VPS (`systemd`, template
in `deploy/lifelogbot.service`). Neither is baked in as the "right" choice —
pick one and adjust the paths in the template to match.
