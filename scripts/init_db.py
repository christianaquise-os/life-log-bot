#!/usr/bin/env python3
"""Apply all pending migrations to data/activity.db. Safe to re-run."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import apply_migrations

if __name__ == "__main__":
    apply_migrations()
    print("done")
