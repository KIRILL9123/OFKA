"""Broadcasting service — sends game notifications to all active users."""

from __future__ import annotations

import asyncio
from typing import Any
from datetime import datetime

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


def _format_platform_names(platforms_raw: str | None) -> str:
    """Format platform names with emojis and clean text.
    
    Handles duplicates and matches exact platform names only.
    """
    if not platforms_raw or not platforms_raw.strip():
        return "🎮 Unknown"
    
    platform_emoji_map = {
        "steam": "🎮 Steam",
        "epic": "🎮 Epic Games",
        "gog": "🎮 GOG",
        "amazon": "📦 Amazon",
        "itch.io": "🕹️ Itch.io",
        "ubisoft": "🎮 Ubisoft",
        "origin": "🎮 Origin",
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
    """Parse end_date and return human-readable format with days remaining.
    
    Supports localization for relative dates (today, tomorrow).
    Returns None for expired games (to signal filtering).
    Tries common date formats. Fails gracefully to raw value if parsing unsuccessful.
    """
    if not end_date_raw or end_date_raw == "N/A":
        return t("unknown_value", lang)
    
    try:
        # Try to parse common date formats (safe formats only, avoiding locale-dependent ones)
        for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"]:
            try:
                end = datetime.strptime(end_date_raw.strip(), fmt)
                now = datetime.now()
                delta = (end - now).days
                
                if delta < 0:
                    return None  # Signal to skip expired games
                elif delta == 0:
                    return t("date_today", lang)
                elif delta == 1:
                    return t("date_tomorrow", lang)
                else:
                    return f"{end_date_raw} ({delta} {t('date_days_left', lang)})"
            except ValueError:
                continue
    except Exception:
        pass
    
    # Fallback to raw value if no format matched
    return end_date_raw


def _game_matches_preferences(
    game: dict[str, Any],
    pref_steam: bool,
    pref_epic: bool,
    pref_gog: bool,
    pref_other: bool,
) -> bool:
    """Return True if giveaway platforms match at least one enabled preference.
    
    Handles empty/null platforms gracefully and normalizes duplicates.
    """
    platforms_raw = str(game.get("platforms", "")).strip().lower()
    
    # If platforms string is empty, treat as "Other"
    if not platforms_raw:
        return pref_other

    # Normalize: split, strip, deduplicate using set for performance
    seen_platforms = set()
    platform_list = []
    for p in platforms_raw.split(","):
        p_clean = p.strip()
        if p_clean and p_clean not in seen_platforms:
            seen_platforms.add(p_clean)
            platform_list.append(p_clean)
    platforms_normalized = ", ".join(platform_list)

    has_steam = any("steam" in p for p in platform_list)
    has_epic = any("epic" in p for p in platform_list)
    has_gog = any("gog" in p for p in platform_list)

    known_hit = (
        (pref_steam and has_steam)
        or (pref_epic and has_epic)
        or (pref_gog and has_gog)
    )
    if known_hit:
        return True

    # "Other" means any platform that is not Steam/Epic/GOG.
    has_other = platforms_normalized and not (has_steam or has_epic or has_gog)
    return pref_other and has_other


def build_game_caption(game: dict[str, Any], lang: str | None) -> str:
    """Format an HTML caption for a game giveaway notification.
    
    Handles N/A values gracefully, truncates long descriptions and titles,
    formats dates and platforms with emojis.
    """
    unknown = t("unknown_value", lang)
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
    end_date = _format_end_date(end_date_raw, lang) if (end_date_raw and end_date_raw != "N/A") else unknown
    
    # Build description section: truncate if too long
    description = (game.get("description") or "").strip()
    if len(description) > MAX_DESCRIPTION_LENGTH:
        description = description[:MAX_DESCRIPTION_LENGTH].rstrip() + "..."
    description_section = f"\n\n<i>{description}</i>" if description else ""
    
    return t(
        "game_caption",
        lang,
        title=title,
        worth=worth,
        platforms=platforms,
        end_date=end_date,
        description_section=description_section,
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
    Falls back to text message if image fails to load.
    """
    caption = build_game_caption(game, lang)
    keyboard = build_game_keyboard(game, lang)
    thumbnail = game.get("thumbnail")

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

    Uses streaming with yield_per() to efficiently handle large user bases
    without loading all users into memory at once.
    
    Returns (success_count, fail_count).
    """
    success = 0
    failed = 0
    deactivated_ids: list[int] = []

    # Stream users in batches of 500 to avoid memory spikes
    async with async_session() as session:
        result = await session.execute(
            select(
                User.tg_id,
                User.language,
                User.pref_steam,
                User.pref_epic,
                User.pref_gog,
                User.pref_other,
            ).where(User.is_active.is_(True))
        )
        
        # Process users as they stream from the database (batch by batch)
        async for tg_id, lang, pref_steam, pref_epic, pref_gog, pref_other in result.yield_per(500).tuples():

            if not _game_matches_preferences(
                game,
                pref_steam,
                pref_epic,
                pref_gog,
                pref_other,
            ):
                continue

            delivered = await send_game_to_user(bot, tg_id, game, lang)
            if delivered:
                success += 1
            else:
                failed += 1
                deactivated_ids.append(tg_id)
            await asyncio.sleep(SEND_DELAY)
        
        # Batch-deactivate blocked users within same session
        if deactivated_ids:
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
    
    Uses streaming with yield_per to efficiently handle large user bases.
    Returns (success_count, fail_count).
    """
    success = 0
    failed = 0
    deactivated_ids: list[int] = []

    # Stream users in batches to avoid loading all into memory
    async with async_session() as session:
        result = await session.execute(
            select(User.tg_id).where(User.is_active.is_(True))
        )
        
        async for (tg_id,) in result.yield_per(500).tuples():
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
        
        # Batch-deactivate blocked users within same session
        if deactivated_ids:
            await session.execute(
                update(User)
                .where(User.tg_id.in_(deactivated_ids))
                .values(is_active=False)
            )
            await session.commit()

    return success, failed
