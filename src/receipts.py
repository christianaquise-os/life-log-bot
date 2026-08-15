from datetime import datetime, timezone

from src import notion_sync
from src.db import get_conn
from src.receipt_extract import extract_receipt

FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _resolve_purchased_at(extracted_date: str | None, message_sent_at: str) -> str:
    """Prefer the date read off the receipt; fall back to the real Telegram
    send time (not processing time) when the model couldn't read one."""
    if extracted_date:
        try:
            dt = datetime.strptime(extracted_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return dt.strftime(FMT)
        except ValueError:
            pass
    return message_sent_at


def handle_receipt_photo(
    chat_id: int,
    image_bytes: bytes,
    media_type: str,
    telegram_file_id: str,
    caption: str | None,
    message_sent_at: str,
) -> str:
    extracted = extract_receipt(image_bytes, media_type, caption)

    merchant = extracted.get("merchant") or "Unknown merchant"
    amount = extracted.get("amount")
    currency = extracted.get("currency") or "EUR"
    purchased_at = _resolve_purchased_at(extracted.get("purchased_at"), message_sent_at)

    if amount is None:
        return f"Could not read a total amount off that receipt from {merchant}. Try a clearer photo?"

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO expenses
               (chat_id, merchant, amount, currency, purchased_at, raw_text, telegram_file_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (chat_id, merchant, amount, currency, purchased_at, caption, telegram_file_id),
        )
        cur = conn.execute(
            """INSERT INTO sessions
               (chat_id, pillar, activity_name, raw_text, source_intent, start_ts, end_ts, duration_seconds, status)
               VALUES (?, 'finance', ?, ?, 'expense', ?, ?, 0, 'closed')""",
            (chat_id, merchant, caption or f"Receipt: {merchant}", purchased_at, purchased_at),
        )
        session_id = cur.lastrowid

    notion_sync.enqueue(session_id)
    return f"Logged {amount:.2f} {currency} at {merchant}."
