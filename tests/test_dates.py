"""Tests for date parsing and localization in bot.utils.dates."""

from __future__ import annotations

from freezegun import freeze_time

from bot.core.translations import t
from bot.utils.dates import format_end_date


@freeze_time('2026-04-19')
def test_none_input() -> None:
    assert format_end_date(None) == t('unknown_value', None)


@freeze_time('2026-04-19')
def test_na_input() -> None:
    assert format_end_date('N/A') == t('unknown_value', None)


@freeze_time('2026-04-19')
def test_expired_date() -> None:
    assert format_end_date('2026-04-18') is None


@freeze_time('2026-04-19')
def test_today() -> None:
    assert format_end_date('2026-04-19') == t('date_today', None)


@freeze_time('2026-04-19')
def test_tomorrow() -> None:
    assert format_end_date('2026-04-20') == t('date_tomorrow', None)


@freeze_time('2026-04-19')
def test_days_left() -> None:
    result = format_end_date('2026-04-22')

    assert result is not None
    assert '3' in result
    assert t('date_days_left', None) in result


@freeze_time('2099-12-01')
def test_datetime_string_format() -> None:
    result = format_end_date('2099-12-31 23:59:00')

    assert result is not None
    assert result.startswith('2099-12-31 (')
    assert t('date_days_left', None) in result


@freeze_time('2099-12-01')
def test_iso_format() -> None:
    result = format_end_date('2099-12-31T23:59:00')

    assert result is not None
    assert result.startswith('2099-12-31 (')
    assert t('date_days_left', None) in result


@freeze_time('2099-12-01')
def test_unknown_format() -> None:
    assert format_end_date('31 Dec 2099') == '31 Dec 2099'


@freeze_time('2026-04-19')
def test_localization_ru() -> None:
    assert format_end_date('2026-04-19', 'ru') == 'Сегодня'


@freeze_time('2026-04-19')
def test_localization_de() -> None:
    assert format_end_date('2026-04-20', 'de') == 'Morgen'
