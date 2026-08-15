from datetime import datetime, timedelta, timezone

from src.db import get_conn
from src import digest

FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


class _FakeTextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeResponse:
    model = "claude-sonnet-5"

    def __init__(self, text="A short digest."):
        self.content = [_FakeTextBlock(text)]
        self.usage = _FakeUsage()


class _FakeUsage:
    input_tokens = 10
    output_tokens = 5
    cache_read_input_tokens = None
    cache_creation_input_tokens = None


def _seed_session(chat_id, activity_name, minutes_ago_start=60, duration_seconds=3600):
    now = datetime.now(timezone.utc)
    end_ts = now.strftime(FMT)
    start_ts = (now - timedelta(seconds=duration_seconds)).strftime(FMT)
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO sessions
               (chat_id, pillar, activity_name, raw_text, source_intent, start_ts, end_ts, duration_seconds, status)
               VALUES (?, 'leisure', ?, 'test', 'log_duration', ?, ?, ?, 'closed')""",
            (chat_id, activity_name, start_ts, end_ts, duration_seconds),
        )


def test_cache_hit_on_unchanged_tally(tmp_db, monkeypatch):
    chat_id = 10
    _seed_session(chat_id, "reading")

    calls = {"n": 0}

    def counting_create(*a, **kw):
        calls["n"] += 1
        return _FakeResponse()

    monkeypatch.setattr("src.digest.client.messages.create", counting_create)

    r1 = digest.build_digest(chat_id)
    r2 = digest.build_digest(chat_id)

    assert r1 == r2
    assert calls["n"] == 1


def test_cache_invalidates_on_new_session(tmp_db, monkeypatch):
    chat_id = 11
    _seed_session(chat_id, "reading")

    calls = {"n": 0}

    def counting_create(*a, **kw):
        calls["n"] += 1
        return _FakeResponse()

    monkeypatch.setattr("src.digest.client.messages.create", counting_create)

    digest.build_digest(chat_id)
    _seed_session(chat_id, "studying", duration_seconds=1800)
    digest.build_digest(chat_id)

    assert calls["n"] == 2


def test_mood_only_day_is_not_nothing_logged(tmp_db, monkeypatch):
    chat_id = 12
    monkeypatch.setattr("src.digest.client.messages.create", lambda *a, **kw: _FakeResponse())

    from src.mood import log_mood

    now = datetime.now(timezone.utc).strftime(FMT)
    log_mood(chat_id, "8 great day", now)

    reply = digest.build_digest(chat_id)
    assert "Nothing logged" not in reply


def test_cache_invalidates_on_new_mood_entry(tmp_db, monkeypatch):
    chat_id = 13
    _seed_session(chat_id, "reading")

    calls = {"n": 0}

    def counting_create(*a, **kw):
        calls["n"] += 1
        return _FakeResponse()

    monkeypatch.setattr("src.digest.client.messages.create", counting_create)

    digest.build_digest(chat_id)

    from src.mood import log_mood

    now = datetime.now(timezone.utc).strftime(FMT)
    log_mood(chat_id, "6", now)
    digest.build_digest(chat_id)

    assert calls["n"] == 2
