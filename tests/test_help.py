from src.telegram_bot import HELP_TEXT

EXPECTED_COMMANDS = [
    "/today",
    "/mood",
    "/newhabit",
    "/log",
    "/habits",
    "/addmovie",
    "/watched",
    "/watchlist",
    "/help",
]


def test_help_text_mentions_every_command():
    for command in EXPECTED_COMMANDS:
        assert command in HELP_TEXT, f"{command} missing from HELP_TEXT"
