"""Handlers for user commands: /start, /help, /settings, preferences."""

import asyncio
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from loguru import logger
from sqlalchemy import and_, func, select, text, update

from bot.core.config import settings
from bot.core.database import async_session
from bot.core.translations import LANG_LABELS, t
from bot.models.models import User, UserGame
from bot.services.game_display import show_active_games_to_user
from bot.services.user_service import (
    get_or_create_user,
    is_rate_limited,
)

router = Router(name="user")

SETTINGS_PREFIX = "settings:"
LANG_CALLBACK_PREFIX = f"{SETTINGS_PREFIX}set_lang:"
TOGGLE_CALLBACK_PREFIX = f"{SETTINGS_PREFIX}toggle:"
OPEN_LANG_PICKER_CB = f"{SETTINGS_PREFIX}open_lang"
BACK_TO_SETTINGS_CB = f"{SETTINGS_PREFIX}back"
UNSUBSCRIBE_CB = f"{SETTINGS_PREFIX}unsubscribe"
DONE_CB = f"{SETTINGS_PREFIX}done"

PLATFORM_FIELDS: dict[str, str] = {
    "steam": "pref_steam",
    "epic": "pref_epic",
    "gog": "pref_gog",
    "other": "pref_other",
}

# Backwards-compat shims — re-exported for tests and other modules
# that previously imported the underscore-prefixed names from this module.
_is_rate_limited = is_rate_limited
_get_or_create_user = get_or_create_user


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


def _main_menu_keyboard(lang: str | None = None) -> ReplyKeyboardMarkup:
    """Build persistent reply keyboard with quick actions."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_games", lang)), KeyboardButton(text=t("btn_stats", lang))],
            [KeyboardButton(text=t("btn_settings", lang)), KeyboardButton(text=t("btn_help", lang))],
        ],
        resize_keyboard=True,
    )


def _language_keyboard(lang: str | None = None) -> InlineKeyboardMarkup:
    """Build language selection keyboard (2 buttons per row)."""
    buttons = [
        InlineKeyboardButton(
            text=label,
            callback_data=f"{LANG_CALLBACK_PREFIX}{code}",
        )
        for code, label in LANG_LABELS.items()
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text=t("btn_back", lang), callback_data=BACK_TO_SETTINGS_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _settings_keyboard(
    lang: str | None,
    pref_steam: bool,
    pref_epic: bool,
    pref_gog: bool,
    pref_other: bool,
) -> InlineKeyboardMarkup:
    """Build user settings keyboard with platform toggles, language button, and unsubscribe."""
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
            [
                InlineKeyboardButton(
                    text=t("btn_unsubscribe", lang),
                    callback_data=UNSUBSCRIBE_CB,
                ),
                InlineKeyboardButton(
                    text=t("btn_done", lang),
                    callback_data=DONE_CB,
                ),
            ],
        ]
    )


def _parse_worth_value(value: str) -> float:
    """Parse money-like worth strings to float values, return 0.0 for unknown formats."""
    normalized = value.replace("$", "").replace("€", "").replace("£", "").strip()
    normalized = normalized.replace(",", ".")
    return float(normalized)


async def _get_or_create_user(
    tg_id: int,
) -> tuple[str | None, bool, bool, bool, bool, bool, bool]:
    """Fetch user settings in one query, creating/reactivating the user when needed."""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalars().first()

        created = False
        reactivated = False
        if user is None:
            created = True
            user = User(tg_id=tg_id, is_active=True)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        elif not user.is_active:
            reactivated = True
            user.is_active = True
            await session.commit()

        return (
            user.language,
            user.pref_steam,
            user.pref_epic,
            user.pref_gog,
            user.pref_other,
            created,
            reactivated,
        )


async def _show_games_on_start(bot: Bot, tg_id: int, lang: str | None, message: Message) -> None:
    """Background task: show active giveaways after welcome message."""
    try:
        await asyncio.sleep(0.8)  # Let welcome message render first
        await show_active_games_to_user(bot, tg_id, lang, message)
    except Exception as exc:
        logger.warning(
            "Failed to show games on start for {tg_id}: {exc}",
            tg_id=tg_id,
            exc=exc,
        )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Register/reactivate user and show welcome + subscription confirmation."""
    tg_id = message.from_user.id

    # Rate-limit check
    if await _is_rate_limited(tg_id):
        lang, _, _, _, _, _, _ = await _get_or_create_user(tg_id)
        await message.answer(
            t("rate_limit_message", lang),
            parse_mode="HTML",
        )
        return

    lang, _, _, _, _, created, reactivated = await _get_or_create_user(tg_id)

    if reactivated:
        logger.info("User {tg_id} resubscribed lang={lang}", tg_id=tg_id, lang=lang)
        await message.answer(
            t("resubscribed", lang),
            parse_mode="HTML",
            reply_markup=_main_menu_keyboard(lang),
        )
    else:
        await message.answer(
            t("start", lang),
            parse_mode="HTML",
            reply_markup=_main_menu_keyboard(lang),
        )
        if created:
            await message.answer(
                t("subscription_confirmed", lang),
                parse_mode="HTML",
            )

    # Show active giveaways to new and returning users
    asyncio.create_task(_show_games_on_start(message.bot, tg_id, lang, message))

    logger.info(
        "User {tg_id} started the bot (created={created}, reactivated={reactivated}, lang={lang})",
        tg_id=tg_id,
        created=created,
        reactivated=reactivated,
        lang=lang,
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Show help information in the user's language."""
    lang, _, _, _, _, _, _ = await _get_or_create_user(message.from_user.id)
    await message.answer(
        t("help", lang),
        parse_mode="HTML",
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    """Open settings panel with language and platform preferences."""
    tg_id = message.from_user.id

    # Rate-limit check
    if await _is_rate_limited(tg_id):
        lang, _, _, _, _, _, _ = await _get_or_create_user(tg_id)
        await message.answer(
            t("rate_limit_message", lang),
            parse_mode="HTML",
        )
        return

    lang, pref_steam, pref_epic, pref_gog, pref_other, _, _ = await _get_or_create_user(tg_id)

    await message.answer(
        t("settings_title", lang),
        parse_mode="HTML",
        reply_markup=_settings_keyboard(lang, pref_steam, pref_epic, pref_gog, pref_other),
    )


@router.message(F.text.in_({t("btn_settings", "ru"), t("btn_settings", "uk"), t("btn_settings", "en"), t("btn_settings", "de")}))
async def open_settings_button(message: Message) -> None:
    """Open settings when user taps reply keyboard button."""
    await cmd_settings(message)


@router.message(F.text.in_({t("btn_help", "ru"), t("btn_help", "uk"), t("btn_help", "en"), t("btn_help", "de")}))
async def open_help_button(message: Message) -> None:
    """Open help when user taps reply keyboard button."""
    await cmd_help(message)


@router.message(F.text.startswith("🎮"))
async def open_games_button(message: Message) -> None:
    """Open active games list when user taps the Games button."""
    tg_id = message.from_user.id
    if await _is_rate_limited(tg_id):
        lang, _, _, _, _, _, _ = await _get_or_create_user(tg_id)
        try:
            await message.answer(t("rate_limit_message", lang), parse_mode="HTML")
        except TelegramForbiddenError:
            logger.info("User {tg_id} blocked the bot in games button", tg_id=tg_id)
        return

    lang, _, _, _, _, _, _ = await _get_or_create_user(tg_id)
    await show_active_games_to_user(message.bot, tg_id, lang, message)


@router.message(F.text.startswith("📊"))
async def cmd_stats_user(message: Message) -> None:
    """Show per-user claim/skip/savings stats."""
    tg_id = message.from_user.id
    if await _is_rate_limited(tg_id):
        lang, _, _, _, _, _, _ = await _get_or_create_user(tg_id)
        try:
            await message.answer(t("rate_limit_message", lang), parse_mode="HTML")
        except TelegramForbiddenError:
            logger.info("User {tg_id} blocked the bot in stats button", tg_id=tg_id)
        return

    lang, _, _, _, _, _, _ = await _get_or_create_user(tg_id)

    claimed_count = 0
    skipped_count = 0
    total_saved = 0.0
    async with async_session() as session:
        try:
            claimed_count = int(
                await session.scalar(
                    select(func.count(UserGame.id)).where(
                        and_(UserGame.tg_id == tg_id, UserGame.status == "claimed")
                    )
                )
                or 0
            )
            skipped_count = int(
                await session.scalar(
                    select(func.count(UserGame.id)).where(
                        and_(UserGame.tg_id == tg_id, UserGame.status == "skipped")
                    )
                )
                or 0
            )

            worth_result = await session.execute(
                text(
                    """
                    SELECT g.worth
                    FROM games AS g
                    JOIN user_games AS ug ON ug.game_external_id = g.external_id
                    WHERE ug.tg_id = :tg_id
                      AND ug.status = 'claimed'
                      AND g.worth IS NOT NULL
                      AND g.worth != 'N/A'
                    """
                ),
                {"tg_id": tg_id},
            )
            worth_values = worth_result.scalars().all()
            for raw_value in worth_values:
                try:
                    if isinstance(raw_value, str):
                        total_saved += _parse_worth_value(raw_value)
                except (ValueError, TypeError, AttributeError):
                    continue
        except Exception as exc:
            logger.warning("User stats query failed for {tg_id}: {exc}", tg_id=tg_id, exc=exc)

    try:
        await message.answer(
            t(
                "user_stats",
                lang,
                claimed=claimed_count,
                skipped=skipped_count,
                saved=f"${total_saved:.2f}",
            ),
            parse_mode="HTML",
        )
    except TelegramForbiddenError:
        logger.info("Cannot send stats to blocked user {tg_id}", tg_id=tg_id)


@router.callback_query(F.data == OPEN_LANG_PICKER_CB)
async def cb_open_language_picker(callback: CallbackQuery) -> None:
    """Open language picker from settings."""
    # Rate-limit check
    if await _is_rate_limited(callback.from_user.id):
        lang, _, _, _, _, _, _ = await _get_or_create_user(callback.from_user.id)
        await callback.answer(t("rate_limit_message", lang), show_alert=False)
        return

    lang, _, _, _, _, _, _ = await _get_or_create_user(callback.from_user.id)
    await callback.message.edit_text(
        t("settings_language_title", lang),
        parse_mode="HTML",
        reply_markup=_language_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(F.data == BACK_TO_SETTINGS_CB)
async def cb_back_to_settings(callback: CallbackQuery) -> None:
    """Return from language picker to settings menu."""
    # Rate-limit check
    if await _is_rate_limited(callback.from_user.id):
        lang, _, _, _, _, _, _ = await _get_or_create_user(callback.from_user.id)
        await callback.answer(t("rate_limit_message", lang), show_alert=False)
        return

    lang, pref_steam, pref_epic, pref_gog, pref_other, _, _ = await _get_or_create_user(
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
    if await _is_rate_limited(tg_id):
        lang, _, _, _, _, _, _ = await _get_or_create_user(tg_id)
        await callback.answer(t("rate_limit_message", lang), show_alert=False)
        return

    lang, pref_steam, pref_epic, pref_gog, pref_other, _, _ = await _get_or_create_user(tg_id)
    current = {
        "pref_steam": pref_steam,
        "pref_epic": pref_epic,
        "pref_gog": pref_gog,
        "pref_other": pref_other,
    }[field]

    # Calculate new state after toggle
    new_state = {
        "pref_steam": pref_steam if field != "pref_steam" else not current,
        "pref_epic": pref_epic if field != "pref_epic" else not current,
        "pref_gog": pref_gog if field != "pref_gog" else not current,
        "pref_other": pref_other if field != "pref_other" else not current,
    }
    
    # Validate: at least one platform must be enabled
    if not any(new_state.values()):
        await callback.answer(t("platform_all_disabled", lang), show_alert=True)
        return

    async with async_session() as session:
        await session.execute(
            update(User)
            .where(User.tg_id == tg_id)
            .values(**{field: (not current)})
        )
        await session.commit()

    # Log platform toggle
    logger.info(
        "User {tg_id} toggled {platform} to {state}",
        tg_id=tg_id,
        platform=platform,
        state=not current,
    )

    # Optimization: use calculated new_state instead of re-fetching from DB
    new_pref_steam = new_state["pref_steam"]
    new_pref_epic = new_state["pref_epic"]
    new_pref_gog = new_state["pref_gog"]
    new_pref_other = new_state["pref_other"]
    
    await callback.message.edit_text(
        t("settings_title", lang),
        parse_mode="HTML",
        reply_markup=_settings_keyboard(lang, new_pref_steam, new_pref_epic, new_pref_gog, new_pref_other),
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
    if await _is_rate_limited(tg_id):
        await callback.answer("⏳ Too many requests. Please wait.", show_alert=False)
        return

    async with async_session() as session:
        await session.execute(
            update(User)
            .where(User.tg_id == tg_id)
            .values(language=lang, is_active=True)
        )
        await session.commit()

    logger.info("User {tg_id} set language to {lang}", tg_id=tg_id, lang=lang)

    _, pref_steam, pref_epic, pref_gog, pref_other, _, _ = await _get_or_create_user(tg_id)
    await callback.message.edit_text(
        f"{t('language_set', lang)}\n\n{t('settings_title', lang)}",
        parse_mode="HTML",
        reply_markup=_settings_keyboard(lang, pref_steam, pref_epic, pref_gog, pref_other),
    )
    await callback.answer()


@router.callback_query(F.data == DONE_CB)
async def cb_done_settings(callback: CallbackQuery) -> None:
    """Close settings panel and return to main menu."""
    # Validate callback data
    if not _validate_callback_data(callback.data):
        logger.warning(
            "Invalid callback data in DONE_CB from user {tg_id}",
            tg_id=callback.from_user.id,
        )
        await callback.answer("⚠️ Invalid request.", show_alert=False)
        return
    
    # Rate-limit check
    if await _is_rate_limited(callback.from_user.id):
        lang, _, _, _, _, _, _ = await _get_or_create_user(callback.from_user.id)
        await callback.answer(t("rate_limit_message", lang), show_alert=False)
        return

    lang, _, _, _, _, _, _ = await _get_or_create_user(callback.from_user.id)
    await callback.message.delete()
    await callback.answer(t("settings_saved", lang))


@router.callback_query(F.data == UNSUBSCRIBE_CB)
async def cb_unsubscribe(callback: CallbackQuery) -> None:
    """Disable notifications for the user."""
    tg_id = callback.from_user.id

    # Rate-limit check
    if await _is_rate_limited(tg_id):
        lang, _, _, _, _, _, _ = await _get_or_create_user(tg_id)
        await callback.answer(t("rate_limit_message", lang), show_alert=False)
        return

    lang, _, _, _, _, _, _ = await _get_or_create_user(tg_id)

    async with async_session() as session:
        await session.execute(
            update(User)
            .where(User.tg_id == tg_id)
            .values(is_active=False)
        )
        await session.commit()

    logger.info("User {tg_id} unsubscribed from notifications", tg_id=tg_id)
    
    await callback.message.delete()
    await callback.bot.send_message(
        chat_id=tg_id,
        text=t("unsubscribe_confirmed", lang),
        parse_mode="HTML",
    )
    await callback.answer()
