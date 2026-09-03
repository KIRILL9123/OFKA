"""Broadcasting service — sends game notifications to all active users."""

from __future__ import annotations

import asyncio
import html
import re
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, URLInputFile
from loguru import logger
from sqlalchemy import and_, func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from bot.core.database import async_session
from bot.core.translations import t
from bot.models.models import Game, User, UserGame
from bot.utils.dates import format_end_date

# Delay between messages to stay under Telegram rate limits (~20 msg/sec)
SEND_DELAY = 0.05
MAX_RETRY_ATTEMPTS = 5
MAX_CAPTION_LENGTH = 1024
BROADCAST_PAGE_SIZE = 500

_STEAM_RE = re.compile(r"\bsteam\b")
_EPIC_RE = re.compile(r"\bepic\b")


def _format_platform_names(platforms_raw: str | None) -> str:
    """Format platform names with emojis and clean text.

    Handles duplicates and matches exact platform names only.
    """
    if not platforms_raw or not platforms_raw.strip():
        return "🎮 Unknown"

    platform_emoji_map = {
        "steam": "🎮 Steam",
        "epic": "🎮 Epic Games",
    }

    # Split, lowercase, deduplicate using set comprehension for better performance
    seen = set()
    platforms = []
    for p in platforms_raw.split(","):
        p_clean = p.strip().lower()
        if p_clean and p_clean not in seen:
            seen.add(p_clean)
            platforms.append(p_clean)

    formatted = []
    for platform in platforms:
        # Exact match (platforms already lowercased and stripped above)
        if platform in platform_emoji_map:
            formatted.append(platform_emoji_map[platform])
        else:
            # Fallback: capitalize and add generic emoji
            formatted.append(f"🎮 {platform.title()}")

    return ", ".join(formatted) if formatted else "🎮 Unknown"


def _format_end_date(end_date_raw: str | None, lang: str | None = None) -> str | None:
    """Backward-compatible wrapper around shared date formatter."""
    return format_end_date(end_date_raw, lang)


def _game_matches_preferences(
    game: dict[str, Any],
    pref_steam: bool,
    pref_epic: bool,
) -> bool:
    """Return True if the giveaway is on Steam or Epic and the user wants it.

    Only Steam and Epic Games Store are supported; games on other platforms
    (or with unknown/empty platforms) never match.
    """
    platforms_raw = str(game.get("platforms", "")).strip().lower()
    if not platforms_raw:
        return False

    # Normalize: split, strip, deduplicate using set for performance
    seen_platforms: set[str] = set()
    platform_list: list[str] = []
    for p in platforms_raw.split(","):
        p_clean = p.strip()
        if p_clean and p_clean not in seen_platforms:
            seen_platforms.add(p_clean)
            platform_list.append(p_clean)

    if pref_steam and any(_STEAM_RE.search(p) for p in platform_list):
        return True
    return bool(pref_epic and any(_EPIC_RE.search(p) for p in platform_list))


def build_game_caption(game: dict[str, Any], lang: str | None) -> str:
    """Format an HTML caption for a game giveaway notification.

    Handles N/A values gracefully, truncates long descriptions and titles,
    formats dates and platforms with emojis.
    """
    unknown = t("unknown_value", lang)
    # 800 chars for description leaves ~224 chars headroom for title,
    # worth, platforms, end_date and HTML tags within Telegram's 1024-char caption limit.
    MAX_DESCRIPTION_LENGTH = 800
    MAX_TITLE_LENGTH = 200

    # Truncate title to prevent caption from exceeding 1024 char limit
    title = game.get("title") or unknown  # Handle empty string
    if len(title) > MAX_TITLE_LENGTH:
        title = title[:MAX_TITLE_LENGTH].rstrip() + "…"

    worth = game.get("worth", "N/A")
    if worth == "N/A":
        worth = unknown

    # Format platforms with emojis
    platforms_raw = game.get("platforms", "")
    platforms = _format_platform_names(platforms_raw) if platforms_raw else unknown

    # Format end date with days remaining
    end_date_raw = game.get("end_date", "")
    end_date = (
        _format_end_date(end_date_raw, lang)
        if (end_date_raw and end_date_raw != "N/A")
        else unknown
    )

    # Build description section: truncate if too long
    description = (game.get("description") or "").strip()
    if len(description) > MAX_DESCRIPTION_LENGTH:
        description = description[:MAX_DESCRIPTION_LENGTH].rstrip() + "..."
    description_section = f"\n\n<i>{description}</i>" if description else ""

    caption = t(
        "game_caption",
        lang,
        title=title,
        worth=worth,
        platforms=platforms,
        end_date=end_date,
        description_section=description_section,
    )

    if len(caption) <= MAX_CAPTION_LENGTH:
        return caption

    # First, drop description completely if needed.
    caption = t(
        "game_caption",
        lang,
        title=title,
        worth=worth,
        platforms=platforms,
        end_date=end_date,
        description_section="",
    )
    if len(caption) <= MAX_CAPTION_LENGTH:
        return caption

    # If still too long, trim title further to stay within Telegram caption limit.
    overflow = len(caption) - MAX_CAPTION_LENGTH
    if overflow > 0:
        min_title_len = 16
        keep_len = max(min_title_len, len(title) - overflow - 1)
        if keep_len < len(title):
            title = title[:keep_len].rstrip() + "…"

    caption = t(
        "game_caption",
        lang,
        title=title,
        worth=worth,
        platforms=platforms,
        end_date=end_date,
        description_section="",
    )
    return caption[:MAX_CAPTION_LENGTH]


def _build_action_keyboard(
    game_external_id: int | None,
    url: str,
    lang: str | None,
) -> InlineKeyboardMarkup:
    """Build game action keyboard with claim URL and quick status actions."""
    if game_external_id is None:
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=t("btn_claim_game", lang), url=url)]]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_claim_game", lang), url=url)],
            [
                InlineKeyboardButton(
                    text=t("btn_claimed", lang),
                    callback_data=f"game:claim:{game_external_id}",
                ),
                InlineKeyboardButton(
                    text=t("btn_skip", lang),
                    callback_data=f"game:skip:{game_external_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_remind", lang),
                    callback_data=f"game:remind:{game_external_id}",
                )
            ],
        ]
    )


def build_game_keyboard(game: dict[str, Any], lang: str | None) -> InlineKeyboardMarkup:
    """Build giveaway keyboard with claim URL and state action buttons."""
    url = str(game.get("open_giveaway_url", "https://www.gamerpower.com"))
    external_id = game.get("id")
    game_external_id = external_id if isinstance(external_id, int) else None
    return _build_action_keyboard(game_external_id, url, lang)


def build_game_keyboard_from_db(game: Game, lang: str | None) -> InlineKeyboardMarkup:
    """Build keyboard for reminders using a Game ORM model instance."""
    url = (
        game.open_giveaway_url
        if getattr(game, "open_giveaway_url", None)
        else f"https://www.gamerpower.com/giveaways/{game.external_id}"
    )
    return _build_action_keyboard(game.external_id, url, lang)


async def send_game_to_user(
    bot: Bot,
    tg_id: int,
    game: dict[str, Any],
    lang: str | None,
) -> bool:
    """Send a single game notification to one user.

    Returns True if message was delivered, False if user should be deactivated.
    Falls back to text message if image fails to load.
    """
    caption = build_game_caption(game, lang)
    keyboard = build_game_keyboard(game, lang)
    thumbnail = game.get("thumbnail")

    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        try:
            if thumbnail:
                try:
                    photo = URLInputFile(thumbnail)
                    await bot.send_photo(
                        chat_id=tg_id,
                        photo=photo,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard,
                    )
                except Exception as img_exc:
                    # Fallback to text message if image fails
                    logger.warning(
                        "Failed to load image for user {tg_id}, sending text instead: {exc}",
                        tg_id=tg_id,
                        exc=img_exc,
                    )
                    await bot.send_message(
                        chat_id=tg_id,
                        text=caption,
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
            if attempt >= MAX_RETRY_ATTEMPTS:
                logger.error(
                    "Rate limit persisted for user {tg_id} after {attempts} retries",
                    tg_id=tg_id,
                    attempts=MAX_RETRY_ATTEMPTS,
                )
                return True
            logger.warning(
                "Rate limited for user {tg_id}, sleeping {retry}s (attempt {attempt}/{max_attempts})",
                tg_id=tg_id,
                retry=exc.retry_after,
                attempt=attempt,
                max_attempts=MAX_RETRY_ATTEMPTS,
            )
            await asyncio.sleep(exc.retry_after)

        except Exception as exc:
            logger.opt(exception=exc).error(
                "Failed to send game to {tg_id}: {exc}",
                tg_id=tg_id,
                exc=exc,
            )
            return True  # Don't deactivate on transient errors

    return True


async def _load_active_user_page(
    last_id: int,
) -> list[tuple[int, int, str | None, bool, bool]]:
    """Load one page of active users with id > last_id (keyset pagination)."""
    async with async_session() as session:
        result = await session.execute(
            select(User.id, User.tg_id, User.language, User.pref_steam, User.pref_epic)
            .where(and_(User.is_active.is_(True), User.id > last_id))
            .order_by(User.id)
            .limit(BROADCAST_PAGE_SIZE)
        )
        return [tuple(row) for row in result.all()]


async def _deactivate_users(tg_ids: list[int]) -> None:
    """Batch-deactivate blocked users in a short-lived session."""
    async with async_session() as session:
        await session.execute(update(User).where(User.tg_id.in_(tg_ids)).values(is_active=False))
        await session.commit()


async def _record_delivered(game_external_id: int, tg_ids: list[int]) -> None:
    """Insert 'notified' UserGame rows for delivered users (idempotent)."""
    async with async_session() as session:
        await session.execute(
            sqlite_insert(UserGame)
            .values(
                [
                    {
                        "tg_id": tid,
                        "game_external_id": game_external_id,
                        "status": "notified",
                    }
                    for tid in tg_ids
                ]
            )
            .on_conflict_do_nothing(index_elements=["tg_id", "game_external_id"])
        )
        await session.commit()


async def broadcast_game(bot: Bot, game: dict[str, Any]) -> tuple[int, int]:
    """Send a game notification to every active user in their language.

    Users are paged in short-lived sessions (keyset pagination by User.id),
    so no DB transaction stays open while messages go over the network.

    Returns (success_count, fail_count).
    """
    success = 0
    failed = 0
    game_external_id = game.get("id")
    log = logger.bind(
        event="broadcast_game",
        giveaway_id=game_external_id,
        title=game.get("title"),
    )
    last_id = 0

    while True:
        rows = await _load_active_user_page(last_id)
        if not rows:
            break
        last_id = rows[-1][0]

        deactivated_ids: list[int] = []
        delivered_tg_ids: list[int] = []
        for _user_pk, tg_id, lang, pref_steam, pref_epic in rows:
            if not _game_matches_preferences(game, pref_steam, pref_epic):
                continue

            delivered = await send_game_to_user(bot, tg_id, game, lang)
            if delivered:
                success += 1
                delivered_tg_ids.append(tg_id)
            else:
                failed += 1
                deactivated_ids.append(tg_id)
            await asyncio.sleep(SEND_DELAY)

        if deactivated_ids:
            await _deactivate_users(deactivated_ids)
            log.info("Deactivated {count} blocked users", count=len(deactivated_ids))

        if delivered_tg_ids and isinstance(game_external_id, int):
            await _record_delivered(game_external_id, delivered_tg_ids)
            log.info(
                "Recorded {n} UserGame notified entries",
                n=len(delivered_tg_ids),
            )

    log.info(
        "Broadcast complete: {ok} delivered, {fail} failed",
        ok=success,
        fail=failed,
    )
    return success, failed


async def broadcast_text(
    bot: Bot,
    text: str,
    progress_cb: Callable[[int, int], Awaitable[None]] | None = None,
) -> tuple[int, int]:
    """Send a plain text message to every active user.

    The text is HTML-escaped so arbitrary admin input can never break
    Telegram's HTML parsing mid-broadcast. Users are paged in short-lived
    sessions (keyset pagination by User.id).

    Returns (success_count, fail_count).
    """
    success = 0
    failed = 0
    safe_text = html.escape(text)

    async with async_session() as session:
        total = int(
            await session.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0
        )

    last_id = 0
    while True:
        async with async_session() as session:
            result = await session.execute(
                select(User.id, User.tg_id)
                .where(and_(User.is_active.is_(True), User.id > last_id))
                .order_by(User.id)
                .limit(BROADCAST_PAGE_SIZE)
            )
            rows = [tuple(row) for row in result.all()]
        if not rows:
            break
        last_id = rows[-1][0]

        deactivated_ids: list[int] = []
        for _user_pk, tg_id in rows:
            try:
                await bot.send_message(
                    chat_id=tg_id,
                    text=safe_text,
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
                        text=safe_text,
                        parse_mode=ParseMode.HTML,
                    )
                    success += 1
                except Exception:
                    failed += 1
            except Exception as exc:
                logger.opt(exception=exc).error("broadcast_text error for {tg_id}", tg_id=tg_id)
                failed += 1

            if progress_cb and (success + failed) % 50 == 0:
                await progress_cb(success + failed, total)

            await asyncio.sleep(SEND_DELAY)

        if deactivated_ids:
            await _deactivate_users(deactivated_ids)

    return success, failed
