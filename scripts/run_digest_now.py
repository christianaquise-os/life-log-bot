#!/usr/bin/env python3
"""Print today's digest immediately, without waiting for the nightly cron."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import TELEGRAM_ALLOWED_CHAT_ID
from src.digest import build_digest

if __name__ == "__main__":
    print(build_digest(TELEGRAM_ALLOWED_CHAT_ID))
