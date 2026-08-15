import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from src.config import OMDB_API_KEY
from src.db import get_conn

FMT = "%Y-%m-%dT%H:%M:%S.%fZ"
OMDB_URL = "https://www.omdbapi.com/"
NOT_CONFIGURED_REPLY = "Movie feature not configured -- ask Christian to set OMDB_API_KEY."


def _omdb_lookup(title: str) -> dict | None:
    """Isolated behind this one function so a future provider swap (e.g.
    TMDb) is a body-only change. Returns None on any failure (network error,
    not found, bad response) rather than raising -- callers treat None as
    'movie not found'."""
    params = urllib.parse.urlencode({"apikey": OMDB_API_KEY, "t": title})
    url = f"{OMDB_URL}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    if data.get("Response") != "True":
        return None
    return {
        "title": data.get("Title", title),
        "year": data.get("Year"),
        "genre": data.get("Genre"),
        "imdb_rating": data.get("imdbRating"),
    }


def add_movie(chat_id: int, title: str) -> str:
    title = (title or "").strip()
    if not title:
        return "Usage: /addmovie <title>"
    if not OMDB_API_KEY:
        return NOT_CONFIGURED_REPLY

    info = _omdb_lookup(title)
    if info is None:
        return f'Could not find "{title}" -- check the spelling?'

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO movies (chat_id, title, year, genre, imdb_rating, status)
               VALUES (?, ?, ?, ?, ?, 'to_watch')""",
            (chat_id, info["title"], info["year"], info["genre"], info["imdb_rating"]),
        )
    return f'Added "{info["title"]}" ({info["year"]}) — {info["genre"]}, IMDb {info["imdb_rating"]}'


def mark_watched(chat_id: int, title_query: str, rating: int | None) -> str:
    title_query = (title_query or "").strip()
    if not title_query:
        return "Usage: /watched <title> [rating 1-10]"
    if rating is not None and not (1 <= rating <= 10):
        return "Rating must be between 1 and 10."

    with get_conn() as conn:
        row = conn.execute(
            """SELECT id, title FROM movies WHERE chat_id = ? AND status = 'to_watch'
               AND lower(title) LIKE lower(?) ORDER BY added_at DESC LIMIT 1""",
            (chat_id, f"%{title_query}%"),
        ).fetchone()
        if row is None:
            return f'No unwatched movie matches "{title_query}".'

        watched_at = datetime.now(timezone.utc).strftime(FMT)
        conn.execute(
            "UPDATE movies SET status = 'watched', user_rating = ?, watched_at = ? WHERE id = ?",
            (rating, watched_at, row["id"]),
        )
    reply = f'Marked "{row["title"]}" as watched.'
    if rating is not None:
        reply += f" Your rating: {rating}/10"
    return reply


def list_watchlist(chat_id: int) -> str:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT title, year FROM movies WHERE chat_id = ? AND status = 'to_watch' ORDER BY added_at",
            (chat_id,),
        ).fetchall()
    if not rows:
        return "Your watchlist is empty. Add one with /addmovie <title>."
    lines = [f"- {r['title']}" + (f" ({r['year']})" if r["year"] else "") for r in rows]
    return "\n".join(lines)
