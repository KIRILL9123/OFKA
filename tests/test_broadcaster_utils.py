from __future__ import annotations

from datetime import date, timedelta

from bot.core.translations import t
from bot.services.broadcaster import _game_matches_preferences
from bot.utils.dates import format_end_date


def test_game_matches_preferences_empty_platforms_maps_to_other() -> None:
    game = {"platforms": ""}

    assert _game_matches_preferences(game, False, False, False, True) is True
    assert _game_matches_preferences(game, False, False, False, False) is False


def test_game_matches_preferences_known_platforms() -> None:
    game = {"platforms": "Steam, Epic Games Store"}

    assert _game_matches_preferences(game, True, False, False, False) is True
    assert _game_matches_preferences(game, False, True, False, False) is True
    assert _game_matches_preferences(game, False, False, True, False) is False


def test_game_matches_preferences_other_platform() -> None:
    game = {"platforms": "Amazon Games"}

    assert _game_matches_preferences(game, False, False, False, True) is True
    assert _game_matches_preferences(game, True, True, True, False) is False


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
