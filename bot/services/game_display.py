"""Shared helper for displaying active game giveaways to users."""

from __future__ import annotations

import time as _time_module
from typing import Any

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import Message, URLInputFile
from loguru import logger
from sqlalchemy import and_, select

from bot.core.database import async_session
from bot.core.translations import t
from bot.models.models import UserGame
from bot.services.api_client import fetch_free_games, get_cached_games
from bot.services.broadcaster import build_game_caption, build_game_keyboard


async def show_active_games_to_user(
    bot: Bot,
    tg_id: int,
    lang: str | None,
    reply_target: Message,
) -> None:
    """Fetch active giveaways and send a short actionable list to one user."""
    try:
        await reply_target.answer(t("loading_games", lang), parse_mode=ParseMode.HTML)
    except TelegramForbiddenError:
        logger.info("Cannot send loading state to blocked user {tg_id}", tg_id=tg_id)
        return

    cached_games, cache_ts = get_cached_games()
    cache_age = _time_module.monotonic() - cache_ts if cache_ts > 0 else float("inf")

    if cached_games and cache_age < 1800:  # 30 minutes
        games = cached_games
    else:
        games = await fetch_free_games()
    if not games:
        try:
            await reply_target.answer(t("no_active_games", lang), parse_mode=ParseMode.HTML)
        except TelegramForbiddenError:
            logger.info("Cannot send empty games state to blocked user {tg_id}", tg_id=tg_id)
        return

    game_by_id: dict[int, dict[str, Any]] = {}
    for game in games:
        external_id = game.get("id")
        if isinstance(external_id, int) and game.get("status", "").lower() == "active":
            game_by_id[external_id] = game

    if not game_by_id:
        try:
            await reply_target.answer(t("no_active_games", lang), parse_mode=ParseMode.HTML)
        except TelegramForbiddenError:
            logger.info("Cannot send empty normalized games state to blocked user {tg_id}", tg_id=tg_id)
        return

    filtered_games: list[dict[str, Any]] = list(game_by_id.values())
    try:
        async with async_session() as session:
            status_result = await session.execute(
                select(UserGame.game_external_id).where(
                    and_(
                        UserGame.tg_id == tg_id,
                        UserGame.status.in_(("claimed", "skipped")),
                        UserGame.game_external_id.in_(tuple(game_by_id.keys())),
                    )
                )
            )
            hidden_ids = set(status_result.scalars().all())
        filtered_games = [
            game for game in game_by_id.values()
            if isinstance(game.get("id"), int) and game.get("id") not in hidden_ids
        ]
    except Exception as exc:
        logger.warning("UserGame filter skipped for user {tg_id}: {exc}", tg_id=tg_id, exc=exc)

    if not filtered_games:
        try:
            await reply_target.answer(t("all_games_claimed", lang), parse_mode=ParseMode.HTML)
        except TelegramForbiddenError:
            logger.info("Cannot send all-claimed state to blocked user {tg_id}", tg_id=tg_id)
        return

    shown_games = filtered_games[:5]
    try:
        await reply_target.answer(
            t("games_showing_n", lang, shown=len(shown_games), total=len(filtered_games)),
            parse_mode=ParseMode.HTML,
        )
    except TelegramForbiddenError:
        logger.info("Cannot send games summary to blocked user {tg_id}", tg_id=tg_id)
        return

    for game in shown_games:
        caption = build_game_caption(game, lang)
        keyboard = build_game_keyboard(game, lang)
        thumbnail = game.get("thumbnail")

        try:
            if isinstance(thumbnail, str) and thumbnail:
                await bot.send_photo(
                    chat_id=tg_id,
                    photo=URLInputFile(thumbnail),
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                )
            else:
                await bot.send_message(
                    chat_id=tg_id,
                    text=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                )
        except TelegramForbiddenError:
            logger.info("User {tg_id} blocked bot while listing games", tg_id=tg_id)
            return
        except Exception as exc:
            logger.warning(
                "Failed to send game {game_id} to user {tg_id}: {exc}",
                game_id=game.get("id"),
                tg_id=tg_id,
                exc=exc,
            )
