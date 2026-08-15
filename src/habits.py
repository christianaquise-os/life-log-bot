from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from src.config import TIMEZONE
from src.db import get_conn

FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _local_date(event_ts: str) -> str:
    dt = datetime.strptime(event_ts, FMT).replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")


def _today_local() -> str:
    return datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")


def create_habit(chat_id: int, name: str) -> str:
    name = (name or "").strip()
    if not name:
        return "Usage: /newhabit <name>"
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM habits WHERE chat_id = ? AND active = 1 AND lower(name) = lower(?)",
            (chat_id, name),
        ).fetchone()
        if existing:
            return f'You already have an active habit called "{name}".'
        conn.execute("INSERT INTO habits (chat_id, name) VALUES (?, ?)", (chat_id, name))
    return f'New habit created: "{name}". Log it with /log {name}'


def _match_habit(conn, chat_id: int, name_query: str):
    """Exact case-insensitive match first; else a single substring match
    (mirrors flows.py's disambiguation substring convention); else None with
    a list of ambiguous candidates (empty list means no match at all)."""
    query = name_query.strip().lower()
    rows = conn.execute("SELECT id, name FROM habits WHERE chat_id = ? AND active = 1", (chat_id,)).fetchall()

    exact = [r for r in rows if r["name"].lower() == query]
    if exact:
        return exact[0], []

    substring = [r for r in rows if query in r["name"].lower()]
    if len(substring) == 1:
        return substring[0], []
    return None, substring


def _logged_dates(conn, habit_id: int) -> set[str]:
    rows = conn.execute("SELECT logged_local_date FROM habit_logs WHERE habit_id = ?", (habit_id,)).fetchall()
    return {r["logged_local_date"] for r in rows}


def _compute_streak(logged_dates: set[str], as_of_local_date: str) -> int:
    """Consecutive local-calendar days ending on as_of_local_date or the day
    before it. A gap of 2+ days as of as_of_local_date returns 0 -- the
    'never miss twice' rule."""
    if not logged_dates:
        return 0
    parsed = {datetime.strptime(d, "%Y-%m-%d").date() for d in logged_dates}
    as_of = datetime.strptime(as_of_local_date, "%Y-%m-%d").date()
    most_recent = max(parsed)

    if (as_of - most_recent).days >= 2:
        return 0

    streak = 0
    cursor = most_recent
    while cursor in parsed:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def log_habit(chat_id: int, name_query: str, event_ts: str) -> str:
    name_query = (name_query or "").strip()
    if not name_query:
        return "Usage: /log <habit name>"

    local_date = _local_date(event_ts)

    with get_conn() as conn:
        match, ambiguous = _match_habit(conn, chat_id, name_query)
        if match is None:
            if ambiguous:
                names = ", ".join(r["name"] for r in ambiguous)
                return f"Which habit did you mean? {names}"
            return f'No active habit matches "{name_query}". Create one with /newhabit {name_query}'

        habit_id, habit_name = match["id"], match["name"]
        already_logged = conn.execute(
            "SELECT id FROM habit_logs WHERE habit_id = ? AND logged_local_date = ?",
            (habit_id, local_date),
        ).fetchone()
        if already_logged:
            return f'Already logged "{habit_name}" today.'

        prior_dates = _logged_dates(conn, habit_id)
        broken_streak_length = 0
        if prior_dates:
            most_recent = max(datetime.strptime(d, "%Y-%m-%d").date() for d in prior_dates)
            gap = (datetime.strptime(local_date, "%Y-%m-%d").date() - most_recent).days
            if gap >= 2:
                broken_streak_length = _compute_streak(prior_dates, most_recent.strftime("%Y-%m-%d"))

        conn.execute(
            "INSERT INTO habit_logs (habit_id, chat_id, logged_local_date, logged_at) VALUES (?, ?, ?, ?)",
            (habit_id, chat_id, local_date, event_ts),
        )

        new_streak = _compute_streak(prior_dates | {local_date}, local_date)

    reply = f'Logged "{habit_name}"! Streak: {new_streak}'
    if broken_streak_length > 0:
        reply += f" (previous streak of {broken_streak_length} was broken)"
    return reply


def list_habits(chat_id: int) -> str:
    today = _today_local()
    with get_conn() as conn:
        habits = conn.execute(
            "SELECT id, name FROM habits WHERE chat_id = ? AND active = 1 ORDER BY name", (chat_id,)
        ).fetchall()
        if not habits:
            return "No habits yet. Create one with /newhabit <name>."

        lines = []
        for h in habits:
            dates = _logged_dates(conn, h["id"])
            streak = _compute_streak(dates, today)
            last_logged = max(dates) if dates else "never"
            lines.append(f"- {h['name']}: streak {streak}, last logged {last_logged}")
    return "\n".join(lines)
