"""Broadcasting service — sends game notifications to all active users."""

from __future__ import annotations

import asyncio
from typing import Any

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, URLInputFile
from loguru import logger
from sqlalchemy import select, update

from bot.core.database import async_session
from bot.core.translations import t
from bot.models.models import User

# Delay between messages to stay under Telegram rate limits (~20 msg/sec)
SEND_DELAY = 0.05


def build_game_caption(game: dict[str, Any], lang: str | None) -> str:
    """Format an HTML caption for a game giveaway notification."""
    return t(
        "game_caption",
        lang,
        title=game.get("title", "Unknown"),
        worth=game.get("worth", "N/A"),
        platforms=game.get("platforms", "N/A"),
        end_date=game.get("end_date", "N/A"),
        description=game.get("description", ""),
    )


def build_game_keyboard(game: dict[str, Any], lang: str | None) -> InlineKeyboardMarkup:
    """Build an inline keyboard with a 'Claim Game' button."""
    url = game.get("open_giveaway_url", "https://www.gamerpower.com")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("claim_button", lang), url=url)]
        ]
    )


async def send_game_to_user(
    bot: Bot,
    tg_id: int,
    game: dict[str, Any],
    lang: str | None,
) -> bool:
    """Send a single game notification to one user.

    Returns True if message was delivered, False if user should be deactivated.
    """
    caption = build_game_caption(game, lang)
    keyboard = build_game_keyboard(game, lang)
    thumbnail = game.get("thumbnail")

    try:
        if thumbnail:
            photo = URLInputFile(thumbnail)
            await bot.send_photo(
                chat_id=tg_id,
                photo=photo,
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
        return True

    except TelegramForbiddenError:
        logger.info("User {tg_id} blocked the bot, deactivating", tg_id=tg_id)
        return False

    except TelegramRetryAfter as exc:
        logger.warning(
            "Rate limited, sleeping {retry}s",
            retry=exc.retry_after,
        )
        await asyncio.sleep(exc.retry_after)
        return await send_game_to_user(bot, tg_id, game, lang)

    except Exception as exc:
        logger.error(
            "Failed to send game to {tg_id}: {exc}",
            tg_id=tg_id,
            exc=exc,
        )
        return True  # Don't deactivate on transient errors


async def broadcast_game(bot: Bot, game: dict[str, Any]) -> tuple[int, int]:
    """Send a game notification to every active user in their language.

    Returns (success_count, fail_count).
    """
    async with async_session() as session:
        result = await session.execute(
            select(User.tg_id, User.language).where(User.is_active.is_(True))
        )
        users: list[tuple[int, str | None]] = list(result.tuples().all())

    success = 0
    failed = 0
    deactivated_ids: list[int] = []

    for tg_id, lang in users:
        delivered = await send_game_to_user(bot, tg_id, game, lang)
        if delivered:
            success += 1
        else:
            failed += 1
            deactivated_ids.append(tg_id)
        await asyncio.sleep(SEND_DELAY)

    # Batch-deactivate blocked users
    if deactivated_ids:
        async with async_session() as session:
            await session.execute(
                update(User)
                .where(User.tg_id.in_(deactivated_ids))
                .values(is_active=False)
            )
            await session.commit()
        logger.info("Deactivated {count} blocked users", count=len(deactivated_ids))

    logger.info(
        "Broadcast complete: {ok} delivered, {fail} failed",
        ok=success,
        fail=failed,
    )
    return success, failed


async def broadcast_text(bot: Bot, text: str) -> tuple[int, int]:
    """Send a plain text message to every active user.

    Returns (success_count, fail_count).
    """
    async with async_session() as session:
        result = await session.execute(
            select(User.tg_id).where(User.is_active.is_(True))
        )
        user_ids: list[int] = list(result.scalars().all())

    success = 0
    failed = 0
    deactivated_ids: list[int] = []

    for tg_id in user_ids:
        try:
            await bot.send_message(
                chat_id=tg_id,
                text=text,
                parse_mode=ParseMode.HTML,
            )
            success += 1
        except TelegramForbiddenError:
            failed += 1
            deactivated_ids.append(tg_id)
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                await bot.send_message(
                    chat_id=tg_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                )
                success += 1
            except Exception:
                failed += 1
        except Exception as exc:
            logger.error("broadcast_text error for {tg_id}: {exc}", tg_id=tg_id, exc=exc)
            failed += 1

        await asyncio.sleep(SEND_DELAY)

    if deactivated_ids:
        async with async_session() as session:
            await session.execute(
                update(User)
                .where(User.tg_id.in_(deactivated_ids))
                .values(is_active=False)
            )
            await session.commit()

    return success, failed
