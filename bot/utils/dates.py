"""Date formatting helpers for giveaway end dates."""

from __future__ import annotations

from datetime import datetime

from bot.core.translations import t


SUPPORTED_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y")


def format_end_date(end_date_raw: str | None, lang: str | None = None) -> str | None:
    """Parse end_date and return human-readable format with days remaining.

    Supports localization for relative dates (today, tomorrow).
    Returns None for expired games (to signal filtering).
    Tries common date formats and falls back to raw value if parsing fails.
    """
    if not end_date_raw or end_date_raw == "N/A":
        return t("unknown_value", lang)

    value = end_date_raw.strip()
    for fmt in SUPPORTED_DATE_FORMATS:
        try:
            end_date = datetime.strptime(value, fmt).date()
            today = datetime.now().date()
            delta = (end_date - today).days

            if delta < 0:
                return None
            if delta == 0:
                return t("date_today", lang)
            if delta == 1:
                return t("date_tomorrow", lang)
            return f"{value} ({delta} {t('date_days_left', lang)})"
        except ValueError:
            continue

    return value
