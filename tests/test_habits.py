from src.db import get_conn
from src.habits import create_habit, log_habit, list_habits, _compute_streak

# Noon UTC always maps to the same local calendar date in Europe/Madrid
# (UTC+1/+2), regardless of DST -- avoids day-boundary flakiness in tests.
DAY1 = "2026-03-01T12:00:00.000000Z"
DAY2 = "2026-03-02T12:00:00.000000Z"
DAY3 = "2026-03-03T12:00:00.000000Z"
DAY4 = "2026-03-04T12:00:00.000000Z"  # 2-day gap from DAY2


def test_create_and_duplicate_habit(tmp_db):
    reply = create_habit(1, "flossing")
    assert "New habit created" in reply

    dup = create_habit(1, "flossing")
    assert "already have" in dup


def test_consecutive_days_build_streak(tmp_db):
    create_habit(2, "flossing")
    log_habit(2, "flossing", DAY1)
    log_habit(2, "flossing", DAY2)
    reply = log_habit(2, "flossing", DAY3)

    assert "Streak: 3" in reply
    assert "broken" not in reply


def test_gap_breaks_streak_with_framing(tmp_db):
    create_habit(3, "flossing")
    log_habit(3, "flossing", DAY1)
    log_habit(3, "flossing", DAY2)
    # DAY4 is a 2-day gap from DAY2 (the last log) -- day 3 was missed -- broken.
    reply = log_habit(3, "flossing", DAY4)

    assert "Streak: 1" in reply
    assert "previous streak of 2 was broken" in reply


def test_same_day_double_log_rejected(tmp_db):
    create_habit(4, "flossing")
    log_habit(4, "flossing", DAY1)
    reply = log_habit(4, "flossing", DAY1)

    assert "Already logged" in reply
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM habit_logs").fetchone()["c"]
    assert count == 1


def test_ambiguous_substring_match(tmp_db):
    create_habit(5, "morning run")
    create_habit(5, "morning yoga")
    reply = log_habit(5, "morning", DAY1)

    assert "Which habit did you mean?" in reply
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM habit_logs").fetchone()["c"]
    assert count == 0


def test_no_match_suggests_newhabit(tmp_db):
    reply = log_habit(6, "meditation", DAY1)
    assert "No active habit matches" in reply
    assert "/newhabit" in reply


def test_list_habits(tmp_db):
    create_habit(7, "flossing")
    log_habit(7, "flossing", DAY1)
    log_habit(7, "flossing", DAY2)

    reply = list_habits(7)
    assert "flossing" in reply
    assert "streak" in reply


def test_compute_streak_pure_logic():
    assert _compute_streak(set(), "2026-03-03") == 0
    assert _compute_streak({"2026-03-01", "2026-03-02", "2026-03-03"}, "2026-03-03") == 3
    # gap of exactly 1 day (yesterday logged) is still current
    assert _compute_streak({"2026-03-02"}, "2026-03-03") == 1
    # gap of 2+ days resets to 0
    assert _compute_streak({"2026-03-01"}, "2026-03-03") == 0
