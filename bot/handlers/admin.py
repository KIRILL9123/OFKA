"""Admin-only handlers: /stats, /force_check, /broadcast."""

from __future__ import annotations


import asyncio
import time
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger
from sqlalchemy import func, select

from bot.core.config import settings
from bot.core.database import async_session
from bot.models.models import Game, User
from bot.services.broadcaster import broadcast_text

router = Router(name="admin")

# Flag to control cleanup task lifecycle
_cleanup_running = True


async def _cleanup_expired_broadcasts() -> None:
    """Background task to clean up expired broadcast requests.
    
    Runs periodically to remove stale entries from _pending_broadcast dict.
    Prevents memory leaks if admin doesn't confirm/cancel requests.
    Stops gracefully when _cleanup_running is set to False.
    """
    while _cleanup_running:
        try:
            await asyncio.sleep(60)  # Check every minute
            if not _cleanup_running:
                break
            
            now = time.time()
            expired_ids = [
                tg_id for tg_id, (_, timestamp) in _pending_broadcast.items()
                if now - timestamp > BROADCAST_TTL_SECONDS
            ]
            for tg_id in expired_ids:
                _pending_broadcast.pop(tg_id, None)
                logger.info(
                    "Auto-cleaned expired broadcast for admin {tg_id}",
                    tg_id=tg_id,
                )
        except Exception as exc:
            logger.error("Error in _cleanup_expired_broadcasts: {exc}", exc=exc)


async def _start_cleanup_task() -> None:
    """Start the background cleanup task for expired broadcasts.
    
    Must be called as: await _start_cleanup_task() from async context.
    """
    asyncio.create_task(_cleanup_expired_broadcasts())
    logger.info("Started background cleanup task for broadcast TTL")


async def stop_cleanup_task() -> None:
    """Stop the cleanup task gracefully during shutdown."""
    global _cleanup_running
    _cleanup_running = False
    logger.info("Stopped background cleanup task")


def _is_admin(message: Message) -> bool:
    """Verify admin access and log unauthorized attempts."""
    is_authorized = message.from_user.id == settings.ADMIN_ID
    if not is_authorized:
        logger.warning(
            "Unauthorized admin command attempt from user {tg_id}: {cmd}",
            tg_id=message.from_user.id,
            cmd=message.text[:50] if message.text else "unknown",
        )
    return is_authorized


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    """Show bot statistics (admin only)."""
    if not _is_admin(message):
        return

    async with async_session() as session:
        total_users = await session.scalar(select(func.count(User.id)))
        active_users = await session.scalar(
            select(func.count(User.id)).where(User.is_active.is_(True))
        )
        total_games = await session.scalar(select(func.count(Game.id)))

    text = (
        "📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total users: <b>{total_users}</b>\n"
        f"✅ Active users: <b>{active_users}</b>\n"
        f"🎮 Games sent: <b>{total_games}</b>"
    )
    await message.answer(text, parse_mode="HTML")
    logger.info("Admin {tg_id} requested stats", tg_id=message.from_user.id)


@router.message(Command("force_check"))
async def cmd_force_check(message: Message, bot: Bot) -> None:
    """Manually trigger a giveaway check (admin only).

    The actual check logic lives in main.py (check_new_games).
    We import and call it here to avoid circular imports via a late import.
    """
    if not _is_admin(message):
        return

    await message.answer("🔄 Running giveaway check…")
    logger.info("Admin {tg_id} triggered force_check", tg_id=message.from_user.id)

    # Late import to avoid circular dependency
    from bot.main import check_new_games

    await check_new_games(bot)
    await message.answer("✅ Force check complete.")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message) -> None:
    """Request broadcast message from admin (admin only).

    Usage: /broadcast <text>
    """
    if not _is_admin(message):
        return

    text = message.text
    from bot.core.translations import t
    
    if text is None:
        await message.answer(t("admin_broadcast_empty", None))
        return

    # Strip the /broadcast command prefix
    payload = text.removeprefix("/broadcast").strip()
    if not payload:
        await message.answer(t("admin_broadcast_usage", None))
        return

    # Validate broadcast message length
    if len(payload) > settings.MAX_MESSAGE_LENGTH:
        await message.answer(
            t("admin_broadcast_too_long", None, length=len(payload), max_length=settings.MAX_MESSAGE_LENGTH)
        )
        return

    # Store pending broadcast with TTL and ask for confirmation
    tg_id = message.from_user.id
    _pending_broadcast[tg_id] = (payload, time.time())
    
    confirm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Send", callback_data="broadcast:confirm"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="broadcast:cancel"),
            ]
        ]
    )
    
    from bot.core.translations import t
    
    await message.answer(
        t("admin_broadcast_confirm", None, message=payload),
        parse_mode="HTML",
        reply_markup=confirm_keyboard,
    )


@router.callback_query(F.data == "broadcast:confirm")
async def cb_broadcast_confirm(callback: CallbackQuery, bot: Bot) -> None:
    """Confirm and send the broadcast message."""
    from bot.core.translations import t
    
    tg_id = callback.from_user.id
    if tg_id != settings.ADMIN_ID:
        await callback.answer(t("admin_unauthorized", None), show_alert=True)
        return
    
    pending_data = _pending_broadcast.pop(tg_id, None)
    if not pending_data:
        await callback.answer(t("admin_no_pending", None), show_alert=True)
        return
    
    payload, timestamp = pending_data
    
    # Check if TTL expired (5 minutes)
    if time.time() - timestamp > BROADCAST_TTL_SECONDS:
        await callback.answer(t("admin_broadcast_expired", None), show_alert=True)
        return
    
    await callback.message.edit_text(t("admin_broadcasting", None))
    success, failed = await broadcast_text(bot, payload)
    
    await callback.message.edit_text(
        t("admin_broadcast_done", None, success=success, failed=failed),
        parse_mode="HTML",
    )
    logger.info(
        "Admin {tg_id} broadcast: {ok} delivered, {fail} failed",
        tg_id=tg_id,
        ok=success,
        fail=failed,
    )


@router.callback_query(F.data == "broadcast:cancel")
async def cb_broadcast_cancel(callback: CallbackQuery) -> None:
    """Cancel pending broadcast."""
    from bot.core.translations import t
    
    tg_id = callback.from_user.id
    if tg_id != settings.ADMIN_ID:
        await callback.answer(t("admin_unauthorized", None), show_alert=True)
        return
    
    _pending_broadcast.pop(tg_id, None)
    await callback.message.delete()
    await callback.answer(t("admin_broadcast_cancelled", None))
