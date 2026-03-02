"""Handlers for regular user commands: /start, /help, and language selection."""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert

from bot.core.database import async_session
from bot.core.translations import LANG_LABELS, t
from bot.models.models import User

router = Router(name="user")

LANG_CALLBACK_PREFIX = "set_lang:"


def _language_keyboard() -> InlineKeyboardMarkup:
    """Build an inline keyboard with language buttons (2 per row)."""
    buttons = [
        InlineKeyboardButton(
            text=label,
            callback_data=f"{LANG_CALLBACK_PREFIX}{code}",
        )
        for code, label in LANG_LABELS.items()
    ]
    # 2 buttons per row
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _get_user_lang(tg_id: int) -> str | None:
    """Fetch the user's language from DB (None if not set)."""
    async with async_session() as session:
        return await session.scalar(
            select(User.language).where(User.tg_id == tg_id)
        )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Register / reactivate the user. Show language picker on first visit."""
    tg_id = message.from_user.id

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

    lang = await _get_user_lang(tg_id)

    if lang is None:
        # First time — ask to pick a language
        await message.answer(
            "🌍 Choose your language / Выберите язык / Оберіть мову / Wähle deine Sprache:",
            reply_markup=_language_keyboard(),
        )
    else:
        # Returning user — greet in their language
        await message.answer(t("start", lang), parse_mode="HTML")

    logger.info("User {tg_id} started the bot", tg_id=tg_id)


@router.callback_query(F.data.startswith(LANG_CALLBACK_PREFIX))
async def cb_set_language(callback: CallbackQuery) -> None:
    """Handle language selection callback."""
    lang = callback.data.removeprefix(LANG_CALLBACK_PREFIX)
    tg_id = callback.from_user.id

    async with async_session() as session:
        stmt = (
            sqlite_upsert(User)
            .values(tg_id=tg_id, is_active=True, language=lang)
            .on_conflict_do_update(
                index_elements=[User.tg_id],
                set_={"is_active": True, "language": lang},
            )
        )
        await session.execute(stmt)
        await session.commit()

    logger.info("User {tg_id} set language to {lang}", tg_id=tg_id, lang=lang)

    # Remove the keyboard and confirm
    await callback.message.edit_text(t("language_set", lang), parse_mode="HTML")
    # Send welcome right after
    await callback.message.answer(t("start", lang), parse_mode="HTML")
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Show help information in the user's language."""
    lang = await _get_user_lang(message.from_user.id)
    await message.answer(t("help", lang), parse_mode="HTML")
