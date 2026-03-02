"""Handlers for user commands: /start, /help, /settings, preferences."""

import asyncio
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert

from bot.core.config import settings
from bot.core.database import async_session
from bot.core.translations import LANG_LABELS, t
from bot.models.models import User

router = Router(name="user")

SETTINGS_PREFIX = "settings:"
LANG_CALLBACK_PREFIX = f"{SETTINGS_PREFIX}set_lang:"
TOGGLE_CALLBACK_PREFIX = f"{SETTINGS_PREFIX}toggle:"
OPEN_LANG_PICKER_CB = f"{SETTINGS_PREFIX}open_lang"
BACK_TO_SETTINGS_CB = f"{SETTINGS_PREFIX}back"

PLATFORM_FIELDS: dict[str, str] = {
    "steam": "pref_steam",
    "epic": "pref_epic",
    "gog": "pref_gog",
    "other": "pref_other",
}

# Rate-limiting: track user action timestamps
_user_rate_limit: dict[int, list[float]] = {}


def _is_rate_limited(tg_id: int) -> bool:
    """Check if user has exceeded rate limit (prevent spam/DoS)."""
    import time

    now = time.time()
    cutoff = now - 60  # Last minute

    if tg_id not in _user_rate_limit:
        _user_rate_limit[tg_id] = [now]
        return False

    # Remove old timestamps
    _user_rate_limit[tg_id] = [ts for ts in _user_rate_limit[tg_id] if ts > cutoff]

    if len(_user_rate_limit[tg_id]) >= settings.USER_RATE_LIMIT_PER_MINUTE:
        return True

    _user_rate_limit[tg_id].append(now)
    return False


def _validate_callback_data(data: str, max_length: int | None = None) -> bool:
    """Validate callback_query data to prevent injection/DoS attacks."""
    if max_length is None:
        max_length = settings.MAX_CALLBACK_LENGTH

    # Check length
    if len(data) > max_length:
        return False

    # Check for valid characters (alphanumeric, underscore, colon, hyphen)
    valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:-")
    if not all(c in valid_chars for c in data):
        return False

    return True


def _on_off(value: bool) -> str:
    return "✅" if value else "❌"


def _main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Build persistent reply keyboard with quick actions."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⚙️ Settings"), KeyboardButton(text="ℹ️ Help")],
        ],
        resize_keyboard=True,
    )


def _language_keyboard() -> InlineKeyboardMarkup:
    """Build language selection keyboard (2 buttons per row)."""
    buttons = [
        InlineKeyboardButton(
            text=label,
            callback_data=f"{LANG_CALLBACK_PREFIX}{code}",
        )
        for code, label in LANG_LABELS.items()
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="⬅️", callback_data=BACK_TO_SETTINGS_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _settings_keyboard(
    lang: str | None,
    pref_steam: bool,
    pref_epic: bool,
    pref_gog: bool,
    pref_other: bool,
) -> InlineKeyboardMarkup:
    """Build user settings keyboard with platform toggles and language button."""
    current_lang = lang if lang in LANG_LABELS else "en"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{_on_off(pref_steam)} {t('settings_btn_steam', lang)}",
                    callback_data=f"{TOGGLE_CALLBACK_PREFIX}steam",
                ),
                InlineKeyboardButton(
                    text=f"{_on_off(pref_epic)} {t('settings_btn_epic', lang)}",
                    callback_data=f"{TOGGLE_CALLBACK_PREFIX}epic",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"{_on_off(pref_gog)} {t('settings_btn_gog', lang)}",
                    callback_data=f"{TOGGLE_CALLBACK_PREFIX}gog",
                ),
                InlineKeyboardButton(
                    text=f"{_on_off(pref_other)} {t('settings_btn_other', lang)}",
                    callback_data=f"{TOGGLE_CALLBACK_PREFIX}other",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"🌍 {t('settings_btn_language', lang)}: {LANG_LABELS[current_lang]}",
                    callback_data=OPEN_LANG_PICKER_CB,
                )
            ],
        ]
    )


async def _ensure_user_exists(tg_id: int) -> None:
    """Create or reactivate user row, preserving existing preferences."""
    async with async_session() as session:
        stmt = (
            sqlite_upsert(User)
            .values(tg_id=tg_id, is_active=True)
            .on_conflict_do_update(
                index_elements=[User.tg_id],
                set_={"is_active": True},
            )
        )
        await session.execute(stmt)
        await session.commit()


async def _get_user_settings(
    tg_id: int,
) -> tuple[str | None, bool, bool, bool, bool]:
    """Fetch language and platform preferences for a user."""
    async with async_session() as session:
        result = await session.execute(
            select(
                User.language,
                User.pref_steam,
                User.pref_epic,
                User.pref_gog,
                User.pref_other,
            ).where(User.tg_id == tg_id)
        )
        row = result.first()

    if row is None:
        return None, True, True, False, False
    return row


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Register/reactivate user and show welcome message."""
    tg_id = message.from_user.id

    # Rate-limit check
    if _is_rate_limited(tg_id):
        await message.answer("⏳ Please wait a moment before the next action.")
        return

    await _ensure_user_exists(tg_id)
    lang, _, _, _, _ = await _get_user_settings(tg_id)

    await message.answer(
        t("start", lang),
        parse_mode="HTML",
        reply_markup=_main_menu_keyboard(),
    )
    await message.answer(
        t("settings_hint", lang),
        parse_mode="HTML",
        reply_markup=_main_menu_keyboard(),
    )

    logger.info("User {tg_id} started the bot", tg_id=tg_id)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Show help information in the user's language."""
    await _ensure_user_exists(message.from_user.id)
    lang, _, _, _, _ = await _get_user_settings(message.from_user.id)
    await message.answer(
        t("help", lang),
        parse_mode="HTML",
        reply_markup=_main_menu_keyboard(),
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    """Open settings panel with language and platform preferences."""
    tg_id = message.from_user.id

    # Rate-limit check
    if _is_rate_limited(tg_id):
        await message.answer("⏳ Please wait a moment before the next action.")
        return

    await _ensure_user_exists(tg_id)
    lang, pref_steam, pref_epic, pref_gog, pref_other = await _get_user_settings(tg_id)

    await message.answer(
        t("settings_hint", lang),
        parse_mode="HTML",
        reply_markup=_main_menu_keyboard(),
    )
    await message.answer(
        t("settings_title", lang),
        parse_mode="HTML",
        reply_markup=_settings_keyboard(lang, pref_steam, pref_epic, pref_gog, pref_other),
    )


@router.message(F.text == "⚙️ Settings")
async def open_settings_button(message: Message) -> None:
    """Open settings when user taps reply keyboard button."""
    await cmd_settings(message)


@router.message(F.text == "ℹ️ Help")
async def open_help_button(message: Message) -> None:
    """Open help when user taps reply keyboard button."""
    await cmd_help(message)


@router.callback_query(F.data == OPEN_LANG_PICKER_CB)
async def cb_open_language_picker(callback: CallbackQuery) -> None:
    """Open language picker from settings."""
    await _ensure_user_exists(callback.from_user.id)
    lang, _, _, _, _ = await _get_user_settings(callback.from_user.id)
    await callback.message.edit_text(
        t("settings_language_title", lang),
        parse_mode="HTML",
        reply_markup=_language_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == BACK_TO_SETTINGS_CB)
async def cb_back_to_settings(callback: CallbackQuery) -> None:
    """Return from language picker to settings menu."""
    await _ensure_user_exists(callback.from_user.id)
    lang, pref_steam, pref_epic, pref_gog, pref_other = await _get_user_settings(
        callback.from_user.id
    )
    await callback.message.edit_text(
        t("settings_title", lang),
        parse_mode="HTML",
        reply_markup=_settings_keyboard(lang, pref_steam, pref_epic, pref_gog, pref_other),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(TOGGLE_CALLBACK_PREFIX))
async def cb_toggle_platform(callback: CallbackQuery) -> None:
    """Toggle per-user platform preference in settings menu."""
    # Validate callback data
    if not _validate_callback_data(callback.data):
        logger.warning(
            "Invalid callback data from user {tg_id}: {data}",
            tg_id=callback.from_user.id,
            data=callback.data[:50],
        )
        await callback.answer("⚠️ Invalid request. Please try again.", show_alert=False)
        return

    platform = callback.data.removeprefix(TOGGLE_CALLBACK_PREFIX)
    field = PLATFORM_FIELDS.get(platform)
    if field is None or platform not in PLATFORM_FIELDS:
        logger.warning(
            "Invalid platform from user {tg_id}: {platform}",
            tg_id=callback.from_user.id,
            platform=platform,
        )
        await callback.answer()
        return

    tg_id = callback.from_user.id

    # Rate-limit check
    if _is_rate_limited(tg_id):
        await callback.answer("⏳ Too many requests. Please wait.", show_alert=False)
        return

    await _ensure_user_exists(tg_id)
    lang, pref_steam, pref_epic, pref_gog, pref_other = await _get_user_settings(tg_id)
    current = {
        "pref_steam": pref_steam,
        "pref_epic": pref_epic,
        "pref_gog": pref_gog,
        "pref_other": pref_other,
    }[field]

    async with async_session() as session:
        await session.execute(
            update(User)
            .where(User.tg_id == tg_id)
            .values(**{field: (not current)})
        )
        await session.commit()

    lang, pref_steam, pref_epic, pref_gog, pref_other = await _get_user_settings(tg_id)
    await callback.message.edit_text(
        t("settings_title", lang),
        parse_mode="HTML",
        reply_markup=_settings_keyboard(lang, pref_steam, pref_epic, pref_gog, pref_other),
    )
    await callback.answer(t("settings_saved", lang))


@router.callback_query(F.data.startswith(LANG_CALLBACK_PREFIX))
async def cb_set_language(callback: CallbackQuery) -> None:
    """Handle language selection callback from settings menu."""
    # Validate callback data
    if not _validate_callback_data(callback.data):
        logger.warning(
            "Invalid language callback from user {tg_id}",
            tg_id=callback.from_user.id,
        )
        await callback.answer("⚠️ Invalid request.", show_alert=False)
        return

    lang = callback.data.removeprefix(LANG_CALLBACK_PREFIX)
    tg_id = callback.from_user.id

    # Validate language code
    if lang not in LANG_LABELS:
        logger.warning(
            "Invalid language code from user {tg_id}: {lang}",
            tg_id=tg_id,
            lang=lang,
        )
        await callback.answer()
        return

    # Rate-limit check
    if _is_rate_limited(tg_id):
        await callback.answer("⏳ Too many requests. Please wait.", show_alert=False)
        return

    await _ensure_user_exists(tg_id)

    async with async_session() as session:
        await session.execute(
            update(User)
            .where(User.tg_id == tg_id)
            .values(language=lang, is_active=True)
        )
        await session.commit()

    logger.info("User {tg_id} set language to {lang}", tg_id=tg_id, lang=lang)

    _, pref_steam, pref_epic, pref_gog, pref_other = await _get_user_settings(tg_id)
    await callback.message.edit_text(
        f"{t('language_set', lang)}\n\n{t('settings_title', lang)}",
        parse_mode="HTML",
        reply_markup=_settings_keyboard(lang, pref_steam, pref_epic, pref_gog, pref_other),
    )
    await callback.answer()
