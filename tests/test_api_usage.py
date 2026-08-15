from src.db import get_conn
from src import api_usage


class _FakeUsage:
    input_tokens = 123
    output_tokens = 45
    cache_read_input_tokens = 10
    cache_creation_input_tokens = None


class _FakeResponse:
    model = "claude-haiku-4-5"
    usage = _FakeUsage()


def test_record_inserts_row(tmp_db):
    api_usage.record(_FakeResponse(), purpose="extract_intent")

    with get_conn() as conn:
        row = conn.execute("SELECT * FROM api_usage").fetchone()

    assert row["model"] == "claude-haiku-4-5"
    assert row["purpose"] == "extract_intent"
    assert row["input_tokens"] == 123
    assert row["output_tokens"] == 45
    assert row["cache_read_input_tokens"] == 10


def test_record_never_raises_on_failure(tmp_db, monkeypatch):
    def broken_get_conn(*a, **kw):
        raise RuntimeError("db is on fire")

    monkeypatch.setattr("src.api_usage.get_conn", broken_get_conn)

    # Must not raise -- recording usage is never allowed to break the caller.
    api_usage.record(_FakeResponse(), purpose="extract_intent")
