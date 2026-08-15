#!/usr/bin/env python3
"""Take an immediate backup of data/activity.db and prune old ones. This is
what the scheduled daily job runs -- use this to trigger one manually."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db_backup import backup, prune

if __name__ == "__main__":
    path = backup()
    deleted = prune()
    print(f"backup created: {path}")
    print(f"pruned {deleted} old backup(s)")
