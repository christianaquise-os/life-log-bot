import threading
import time

from src.db import get_conn


def test_concurrent_writers_retry_instead_of_failing_locked(tmp_db):
    """Reproduces the exact scenario that surfaced live: one connection
    holds an open write transaction (route_message's outer `with get_conn()`)
    while a second, independent connection tries to write (api_usage.record()
    opening its own connection mid-request). Without busy_timeout, the
    second connection fails immediately with 'database is locked' instead of
    waiting for the first to commit."""
    results = {}

    def second_writer():
        time.sleep(0.05)  # let the outer transaction grab the write lock first
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO api_usage (model, purpose, input_tokens, output_tokens) VALUES ('m', 'p', 1, 1)"
            )
        results["second_writer_ok"] = True

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO api_usage (model, purpose, input_tokens, output_tokens) VALUES ('m', 'p', 1, 1)"
        )
        t = threading.Thread(target=second_writer)
        t.start()
        time.sleep(0.3)  # hold the outer transaction open while the second writer attempts to write

    t.join(timeout=5)
    assert results.get("second_writer_ok") is True

    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM api_usage").fetchone()["c"]
    assert count == 2
