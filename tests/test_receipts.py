from datetime import datetime, timezone

from src.db import get_conn
from src import receipts

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def fake_extract(image_bytes, media_type, caption):
    return {
        "merchant": "Mercadona",
        "purchased_at": "2026-03-01",
        "amount": 23.45,
        "currency": "EUR",
        "confidence": "high",
    }


def fake_extract_no_amount(image_bytes, media_type, caption):
    return {"merchant": "Blurry Shop", "purchased_at": None, "amount": None, "currency": None, "confidence": "low"}


def test_handle_receipt_creates_expense_and_session(tmp_db, monkeypatch):
    monkeypatch.setattr("src.receipts.extract_receipt", fake_extract)

    reply = receipts.handle_receipt_photo(1, b"fake-bytes", "image/jpeg", "file123", "groceries", NOW)
    assert "23.45" in reply
    assert "Mercadona" in reply

    with get_conn() as conn:
        expense = conn.execute("SELECT * FROM expenses WHERE chat_id = 1").fetchone()
        session = conn.execute(
            "SELECT * FROM sessions WHERE chat_id = 1 AND source_intent = 'expense'"
        ).fetchone()

    assert expense["merchant"] == "Mercadona"
    assert expense["amount"] == 23.45
    assert expense["telegram_file_id"] == "file123"
    assert session["pillar"] == "finance"
    assert session["status"] == "closed"
    assert session["duration_seconds"] == 0


def test_handle_receipt_no_amount_extracted(tmp_db, monkeypatch):
    monkeypatch.setattr("src.receipts.extract_receipt", fake_extract_no_amount)

    reply = receipts.handle_receipt_photo(2, b"fake-bytes", "image/jpeg", "file456", None, NOW)
    assert "Could not read a total amount" in reply

    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM expenses WHERE chat_id = 2").fetchone()["c"]
    assert count == 0


def test_purchased_at_falls_back_to_message_time_when_unreadable(tmp_db, monkeypatch):
    def fake_no_date(image_bytes, media_type, caption):
        return {"merchant": "Cafe", "purchased_at": None, "amount": 5.0, "currency": "EUR", "confidence": "medium"}

    monkeypatch.setattr("src.receipts.extract_receipt", fake_no_date)
    receipts.handle_receipt_photo(3, b"x", "image/jpeg", "file789", None, NOW)

    with get_conn() as conn:
        expense = conn.execute("SELECT purchased_at FROM expenses WHERE chat_id = 3").fetchone()
    assert expense["purchased_at"] == NOW
