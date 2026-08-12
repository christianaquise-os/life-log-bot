import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "activity.db"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_CHAT_ID = int(os.environ.get("TELEGRAM_ALLOWED_CHAT_ID", "0") or 0)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
# The data source ID (not the legacy "database ID") — Notion's current API
# addresses the queryable/writable collection this way. Find it in a
# database's fetch/create response under <data-source url="collection://...">.
NOTION_DATA_SOURCE_ID = os.environ.get("NOTION_DATA_SOURCE_ID", "")

TIMEZONE = os.environ.get("TIMEZONE", "Europe/Madrid")
DIGEST_TIME = os.environ.get("DIGEST_TIME", "22:00")

# Pillar keys must match migrations/001_init.sql exactly.
PILLARS = [
    "nutrition_body",
    "finance",
    "mind_wellbeing",
    "relationships",
    "career_learning",
    "leisure",
    "uncategorized",
]
SUB_TRACKS = ["girlfriend", "friends_family"]
