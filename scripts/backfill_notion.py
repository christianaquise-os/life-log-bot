#!/usr/bin/env python3
"""One-off: sync any closed session missing a Notion page. Also what the
scheduled reconciliation sweep runs every 10 minutes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.notion_sync import resync_unsynced

if __name__ == "__main__":
    count = resync_unsynced()
    print(f"resynced {count} session(s)")
