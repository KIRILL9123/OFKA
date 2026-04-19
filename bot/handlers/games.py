"""Handlers for game list requests and game action callbacks."""

from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy import select

from bot.core.database import async_session
from bot.core.translations import t
from bot.models.models import UserGame
from bot.services.game_display import show_active_games_to_user

router = Router(name="games")


def _extract_game_id(data: str, prefix: str) -> int | None:
    """Extract numeric game id from callback payload or return None."""
    try:
        value = int(data.removeprefix(prefix))
    except ValueError:
        return None
    return value if value > 0 else None


async def _upsert_user_game_state(
    tg_id: int,
    game_external_id: int,
    status: str,
    remind_at: datetime | None = None,
) -> None:
    """Store or update game action state for a user."""
    async with async_session() as session:
        existing_result = await session.execute(
            select(UserGame).where(
                UserGame.tg_id == tg_id,
                UserGame.game_external_id == game_external_id,
            )
        )
        row = existing_result.scalars().first()
        if row is None:
            session.add(
                UserGame(
                    tg_id=tg_id,
                    game_external_id=game_external_id,
                    status=status,
                    remind_at=remind_at,
                )
            )
        else:
            row.status = status
            row.remind_at = remind_at

        await session.commit()


@router.message(Command("games"))
async def cmd_games(message: Message) -> None:
    """Show current active giveaways for a user."""
    from bot.handlers.user import _get_or_create_user

    tg_id = message.from_user.id
    lang, _, _, _, _, _, _ = await _get_or_create_user(tg_id)
    await show_active_games_to_user(message.bot, tg_id, lang, message)


@router.callback_query(F.data.startswith("game:claim:"))
async def cb_game_claim(callback: CallbackQuery) -> None:
    """Mark game as claimed for a user."""
    from bot.handlers.user import _get_or_create_user

    if callback.data is None:
        await callback.answer()
        return

    game_id = _extract_game_id(callback.data, "game:claim:")
    if game_id is None:
        await callback.answer()
        return

    tg_id = callback.from_user.id
    lang, _, _, _, _, _, _ = await _get_or_create_user(tg_id)
    try:
        await _upsert_user_game_state(tg_id, game_id, "claimed")
        await callback.answer(t("toast_claimed", lang), show_alert=False)
    except Exception as exc:
        logger.error("Failed to mark game {game_id} as claimed for {tg_id}: {exc}", game_id=game_id, tg_id=tg_id, exc=exc)
        await callback.answer()


@router.callback_query(F.data.startswith("game:skip:"))
async def cb_game_skip(callback: CallbackQuery) -> None:
    """Mark game as skipped for a user."""
    from bot.handlers.user import _get_or_create_user

    if callback.data is None:
        await callback.answer()
        return

    game_id = _extract_game_id(callback.data, "game:skip:")
    if game_id is None:
        await callback.answer()
        return

    tg_id = callback.from_user.id
    lang, _, _, _, _, _, _ = await _get_or_create_user(tg_id)
    try:
        await _upsert_user_game_state(tg_id, game_id, "skipped")
        await callback.answer(t("toast_skipped", lang), show_alert=False)
    except Exception as exc:
        logger.error("Failed to mark game {game_id} as skipped for {tg_id}: {exc}", game_id=game_id, tg_id=tg_id, exc=exc)
        await callback.answer()


@router.callback_query(F.data.startswith("game:remind:"))
async def cb_game_remind(callback: CallbackQuery) -> None:
    """Set reminder state for a user and game."""
    from bot.handlers.user import _get_or_create_user

    if callback.data is None:
        await callback.answer()
        return

    game_id = _extract_game_id(callback.data, "game:remind:")
    if game_id is None:
        await callback.answer()
        return

    tg_id = callback.from_user.id
    lang, _, _, _, _, _, _ = await _get_or_create_user(tg_id)
    try:
        await _upsert_user_game_state(
            tg_id,
            game_id,
            "remind",
            remind_at=datetime.utcnow() + timedelta(days=1),
        )
        await callback.answer(t("toast_remind_set", lang), show_alert=False)
    except Exception as exc:
        logger.error("Failed to set reminder for game {game_id} and user {tg_id}: {exc}", game_id=game_id, tg_id=tg_id, exc=exc)
        await callback.answer()
