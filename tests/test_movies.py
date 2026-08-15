from src.db import get_conn
from src import movies


def fake_lookup_found(title):
    return {"title": "Inception", "year": "2010", "genre": "Sci-Fi", "imdb_rating": "8.8"}


def fake_lookup_not_found(title):
    return None


def test_add_movie_not_configured(tmp_db, monkeypatch):
    monkeypatch.setattr("src.movies.OMDB_API_KEY", "")
    reply = movies.add_movie(1, "Inception")
    assert reply == movies.NOT_CONFIGURED_REPLY


def test_add_movie_success(tmp_db, monkeypatch):
    monkeypatch.setattr("src.movies.OMDB_API_KEY", "fake-key")
    monkeypatch.setattr("src.movies._omdb_lookup", fake_lookup_found)

    reply = movies.add_movie(2, "inception")
    assert "Inception" in reply
    assert "2010" in reply

    with get_conn() as conn:
        row = conn.execute("SELECT title, status FROM movies WHERE chat_id = 2").fetchone()
    assert row["title"] == "Inception"
    assert row["status"] == "to_watch"


def test_add_movie_not_found(tmp_db, monkeypatch):
    monkeypatch.setattr("src.movies.OMDB_API_KEY", "fake-key")
    monkeypatch.setattr("src.movies._omdb_lookup", fake_lookup_not_found)

    reply = movies.add_movie(3, "asdkjhasdkjh")
    assert "Could not find" in reply


def test_watchlist_and_watched_flow(tmp_db, monkeypatch):
    monkeypatch.setattr("src.movies.OMDB_API_KEY", "fake-key")
    monkeypatch.setattr("src.movies._omdb_lookup", fake_lookup_found)

    movies.add_movie(4, "Inception")
    watchlist = movies.list_watchlist(4)
    assert "Inception" in watchlist

    reply = movies.mark_watched(4, "inception", 9)
    assert "watched" in reply
    assert "9/10" in reply

    watchlist_after = movies.list_watchlist(4)
    assert "empty" in watchlist_after


def test_watched_invalid_rating(tmp_db, monkeypatch):
    monkeypatch.setattr("src.movies.OMDB_API_KEY", "fake-key")
    monkeypatch.setattr("src.movies._omdb_lookup", fake_lookup_found)

    movies.add_movie(5, "Inception")
    reply = movies.mark_watched(5, "inception", 15)
    assert "between 1 and 10" in reply

    with get_conn() as conn:
        row = conn.execute("SELECT status FROM movies WHERE chat_id = 5").fetchone()
    assert row["status"] == "to_watch"


def test_watched_no_match(tmp_db):
    reply = movies.mark_watched(6, "nonexistent movie", None)
    assert "No unwatched movie matches" in reply
