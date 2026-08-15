from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src import db_backup, digest, notion_sync, session_hygiene
from src.config import DIGEST_TIME, TELEGRAM_ALLOWED_CHAT_ID, TIMEZONE

_scheduler = BackgroundScheduler(timezone=TIMEZONE)


def start(send_message_fn) -> None:
    hour, minute = (int(x) for x in DIGEST_TIME.split(":"))

    def _nightly_digest() -> None:
        content = digest.persist_and_get_nightly(TELEGRAM_ALLOWED_CHAT_ID)
        if content:
            send_message_fn(TELEGRAM_ALLOWED_CHAT_ID, content)
            digest.mark_sent(TELEGRAM_ALLOWED_CHAT_ID)

    _scheduler.add_job(_nightly_digest, CronTrigger(hour=hour, minute=minute))
    _scheduler.add_job(notion_sync.resync_unsynced, "interval", minutes=10)
    _scheduler.add_job(session_hygiene.close_stale_open_sessions, "interval", hours=1)
    _scheduler.add_job(db_backup.backup_and_prune, CronTrigger(hour=3, minute=0))
    _scheduler.start()


def shutdown() -> None:
    _scheduler.shutdown(wait=False)
