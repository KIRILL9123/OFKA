from __future__ import annotations

from datetime import date, timedelta

from bot.core.translations import t
from bot.services.broadcaster import _game_matches_preferences, build_game_caption
from bot.utils.dates import format_end_date


def test_game_matches_preferences_empty_platforms_never_matches() -> None:
    game = {"platforms": ""}

    assert _game_matches_preferences(game, False, False) is False
    assert _game_matches_preferences(game, True, True) is False


def test_game_matches_preferences_known_platforms() -> None:
    game = {"platforms": "Steam, Epic Games Store"}

    assert _game_matches_preferences(game, True, False) is True
    assert _game_matches_preferences(game, False, True) is True
    assert _game_matches_preferences(game, False, False) is False


def test_game_matches_preferences_steam_only() -> None:
    game = {"platforms": "Steam"}

    assert _game_matches_preferences(game, True, False) is True
    assert _game_matches_preferences(game, False, True) is False


def test_game_matches_preferences_unsupported_platform_never_matches() -> None:
    game = {"platforms": "Amazon Games"}

    assert _game_matches_preferences(game, False, False) is False
    assert _game_matches_preferences(game, True, True) is False


def test_game_matches_preferences_does_not_use_partial_substring_match() -> None:
    game = {"platforms": "Epicenter Store, Steamworks Hub"}

    assert _game_matches_preferences(game, True, False) is False
    assert _game_matches_preferences(game, False, True) is False


def test_build_game_caption_never_exceeds_telegram_caption_limit() -> None:
    game = {
        "title": "Very Long Title " * 80,
        "worth": "$99.99",
        "platforms": ", ".join(["Steam"] * 120),
        "end_date": "2099-12-31",
        "description": "Long description " * 300,
    }

    caption = build_game_caption(game, "en")
    assert len(caption) <= 1024


def test_format_end_date_na_returns_unknown() -> None:
    assert format_end_date("N/A", "en") == t("unknown_value", "en")


def test_format_end_date_today_and_tomorrow() -> None:
    today_str = date.today().strftime("%Y-%m-%d")
    tomorrow_str = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")

    assert format_end_date(today_str, "en") == t("date_today", "en")
    assert format_end_date(tomorrow_str, "en") == t("date_tomorrow", "en")


def test_format_end_date_expired_returns_none() -> None:
    yesterday_str = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    assert format_end_date(yesterday_str, "en") is None
