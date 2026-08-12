#!/usr/bin/env python3
import logging
import urllib.parse
import urllib.request

from src import scheduler
from src.config import TELEGRAM_BOT_TOKEN
from src.db import apply_migrations
from src.telegram_bot import build_application

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def _send_message_sync(chat_id: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    urllib.request.urlopen(url, data=data, timeout=10)


def main() -> None:
    apply_migrations()
    app = build_application()
    scheduler.start(_send_message_sync)
    try:
        app.run_polling()
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
