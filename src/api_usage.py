import logging

from src.db import get_conn

logger = logging.getLogger(__name__)


def record(response, purpose: str) -> None:
    """purpose is a short tag, e.g. 'extract_intent', 'digest', 'receipt_extract'.
    Never raises -- a failure to record usage must never break the actual
    bot response."""
    try:
        usage = response.usage
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO api_usage
                   (model, purpose, input_tokens, output_tokens,
                    cache_read_input_tokens, cache_creation_input_tokens)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    response.model,
                    purpose,
                    usage.input_tokens,
                    usage.output_tokens,
                    usage.cache_read_input_tokens,
                    usage.cache_creation_input_tokens,
                ),
            )
    except Exception:
        logger.exception("failed to record api usage for purpose=%s; continuing", purpose)
