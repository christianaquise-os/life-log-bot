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

OMDB_API_KEY = os.environ.get("OMDB_API_KEY", "")

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


class ConfigError(RuntimeError):
    """Raised when required environment configuration is missing at startup."""


def validate_config() -> None:
    """Refuse to start rather than run silently broken. Notion vars are
    optional/best-effort by design (see CLAUDE.md) and are NOT checked here."""
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_ALLOWED_CHAT_ID:  # also catches the "unset -> defaults to 0" case
        missing.append("TELEGRAM_ALLOWED_CHAT_ID")
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")

    if missing:
        names = ", ".join(missing)
        raise ConfigError(
            f"Missing required configuration: {names}. "
            f"Set {'it' if len(missing) == 1 else 'them'} in .env "
            f"(copy .env.example to .env if you haven't yet) before starting the bot."
        )
