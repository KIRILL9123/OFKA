"""All bot text localised into 4 languages."""

from __future__ import annotations

from typing import Any

# Supported language codes
LANGUAGES = ("ru", "uk", "en", "de")
DEFAULT_LANG = "en"

# Map code → display label (used in the picker)
LANG_LABELS: dict[str, str] = {
    "ru": "🇷🇺 Русский",
    "uk": "🇺🇦 Українська",
    "en": "🇬🇧 English",
    "de": "🇩🇪 Deutsch",
}

# ── All translatable strings keyed by (key, lang) ────────────────────────

_TEXTS: dict[str, dict[str, str]] = {
    "pick_language": {
        "ru": "🌍 Выберите язык:",
        "uk": "🌍 Оберіть мову:",
        "en": "🌍 Choose your language:",
        "de": "🌍 Wähle deine Sprache:",
    },
    "language_set": {
        "ru": "✅ Язык установлен: <b>Русский</b>",
        "uk": "✅ Мову встановлено: <b>Українська</b>",
        "en": "✅ Language set: <b>English</b>",
        "de": "✅ Sprache eingestellt: <b>Deutsch</b>",
    },
    "start": {
        "ru": (
            "👋 <b>Добро пожаловать!</b>\n\n"
            "Я буду уведомлять тебя, когда появляется новая "
            "<b>100% бесплатная игра</b> (навсегда) в <b>Steam</b>, "
            "<b>Epic Games Store</b> или <b>GOG</b>.\n\n"
            "Ничего делать не нужно — просто жди сообщений.\n\n"
            "Команды: /help"
        ),
        "uk": (
            "👋 <b>Ласкаво просимо!</b>\n\n"
            "Я повідомлятиму тебе, коли з'являється нова "
            "<b>100% безкоштовна гра</b> (назавжди) у <b>Steam</b>, "
            "<b>Epic Games Store</b> або <b>GOG</b>.\n\n"
            "Нічого робити не потрібно — просто чекай повідомлень.\n\n"
            "Команди: /help"
        ),
        "en": (
            "👋 <b>Welcome!</b>\n\n"
            "I will notify you whenever a new <b>100% free game</b> "
            "(free to keep forever) appears on <b>Steam</b>, "
            "<b>Epic Games Store</b>, or <b>GOG</b>.\n\n"
            "You don't need to do anything — just keep this chat "
            "and I'll message you when a new giveaway drops.\n\n"
            "Commands: /help"
        ),
        "de": (
            "👋 <b>Willkommen!</b>\n\n"
            "Ich benachrichtige dich, sobald ein neues "
            "<b>100% kostenloses Spiel</b> (dauerhaft) auf <b>Steam</b>, "
            "<b>Epic Games Store</b> oder <b>GOG</b> verfügbar ist.\n\n"
            "Du musst nichts tun — warte einfach auf Nachrichten.\n\n"
            "Befehle: /help"
        ),
    },
    "help": {
        "ru": (
            "ℹ️ <b>Как это работает</b>\n\n"
            "Каждые 15 минут я проверяю GamerPower API на наличие "
            "бесплатных PC-игр в Steam, Epic Games Store и GOG.\n\n"
            "Когда появляется новая <b>бесплатная навсегда</b> игра — "
            "ты получишь уведомление со ссылкой.\n\n"
            "<b>Команды:</b>\n"
            "/start — Подписаться / сменить язык\n"
            "/help — Это сообщение"
        ),
        "uk": (
            "ℹ️ <b>Як це працює</b>\n\n"
            "Кожні 15 хвилин я перевіряю GamerPower API на наявність "
            "безкоштовних PC-ігор у Steam, Epic Games Store та GOG.\n\n"
            "Коли з'являється нова <b>безкоштовна назавжди</b> гра — "
            "ти отримаєш повідомлення з посиланням.\n\n"
            "<b>Команди:</b>\n"
            "/start — Підписатися / змінити мову\n"
            "/help — Це повідомлення"
        ),
        "en": (
            "ℹ️ <b>How it works</b>\n\n"
            "Every 15 minutes I check the GamerPower API for new "
            "PC game giveaways on Steam, Epic Games Store, and GOG.\n\n"
            "When a new <b>free-to-keep</b> game appears, I send you "
            "a notification with a direct link to claim it.\n\n"
            "<b>Commands:</b>\n"
            "/start — Subscribe / change language\n"
            "/help — This message"
        ),
        "de": (
            "ℹ️ <b>So funktioniert's</b>\n\n"
            "Alle 15 Minuten prüfe ich die GamerPower API auf neue "
            "kostenlose PC-Spiele bei Steam, Epic Games Store und GOG.\n\n"
            "Wenn ein neues <b>dauerhaft kostenloses</b> Spiel erscheint, "
            "sende ich dir eine Benachrichtigung mit Link.\n\n"
            "<b>Befehle:</b>\n"
            "/start — Abonnieren / Sprache ändern\n"
            "/help — Diese Nachricht"
        ),
    },
    "game_caption": {
        "ru": (
            "🎮 <b>{title}</b>\n"
            "💰 Цена: <s>{worth}</s> → <b>БЕСПЛАТНО</b>\n"
            "🏪 Платформа: {platforms}\n"
            "⏳ До: {end_date}\n\n"
            "<i>{description}</i>"
        ),
        "uk": (
            "🎮 <b>{title}</b>\n"
            "💰 Ціна: <s>{worth}</s> → <b>БЕЗКОШТОВНО</b>\n"
            "🏪 Платформа: {platforms}\n"
            "⏳ До: {end_date}\n\n"
            "<i>{description}</i>"
        ),
        "en": (
            "🎮 <b>{title}</b>\n"
            "💰 Price: <s>{worth}</s> → <b>FREE</b>\n"
            "🏪 Platform: {platforms}\n"
            "⏳ Ends: {end_date}\n\n"
            "<i>{description}</i>"
        ),
        "de": (
            "🎮 <b>{title}</b>\n"
            "💰 Preis: <s>{worth}</s> → <b>KOSTENLOS</b>\n"
            "🏪 Plattform: {platforms}\n"
            "⏳ Bis: {end_date}\n\n"
            "<i>{description}</i>"
        ),
    },
    "claim_button": {
        "ru": "🎁 Забрать игру",
        "uk": "🎁 Забрати гру",
        "en": "🎁 Claim Game",
        "de": "🎁 Spiel holen",
    },
}


def t(key: str, lang: str | None = None, **kwargs: Any) -> str:
    """Get a translated string by key and language code.

    Falls back to English if the key or language is missing.
    Supports str.format() kwargs for templates like game_caption.
    """
    lang = lang if lang in LANGUAGES else DEFAULT_LANG
    texts = _TEXTS.get(key, {})
    text = texts.get(lang, texts.get(DEFAULT_LANG, key))
    if kwargs:
        return text.format(**kwargs)
    return text
