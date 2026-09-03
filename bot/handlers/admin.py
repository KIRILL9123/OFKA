"""Admin-only handlers: /stats, /force_check, /broadcast."""

from __future__ import annotations


import asyncio
from contextlib import suppress
import time
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger
from sqlalchemy import func, select

from bot.core.config import settings
from bot.core.database import async_session
from bot.core.translations import t
from bot.models.models import Game, User, UserGame
from bot.services.broadcaster import broadcast_text

router = Router(name="admin")

# Pending broadcast payload per admin user id: {tg_id: (message, created_ts)}
_pending_broadcast: dict[int, tuple[str, float]] = {}
BROADCAST_TTL_SECONDS = 300

# Last expensive admin action timestamp (broadcast/force_check/backfill)
_admin_last_expensive: dict[int, float] = {}

# Flag to control cleanup task lifecycle
_cleanup_running = True
_cleanup_task: asyncio.Task | None = None


def _is_admin_throttled(tg_id: int) -> bool:
    """Return True if admin ran an expensive action within the cooldown window."""
    last = _admin_last_expensive.get(tg_id)
    if last is None:
        return False
    return (time.time() - last) < settings.ADMIN_COOLDOWN_SECONDS


def _mark_admin_action(tg_id: int) -> None:
    _admin_last_expensive[tg_id] = time.time()


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
                tg_id
                for tg_id, (_, timestamp) in _pending_broadcast.items()
                if now - timestamp > BROADCAST_TTL_SECONDS
            ]
            for tg_id in expired_ids:
                _pending_broadcast.pop(tg_id, None)
                logger.info(
                    "Auto-cleaned expired broadcast for admin {tg_id}",
                    tg_id=tg_id,
                )
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Error in _cleanup_expired_broadcasts: {exc}", exc=exc)


async def _start_cleanup_task() -> None:
    """Start the background cleanup task for expired broadcasts.

    Must be called as: await _start_cleanup_task() from async context.
    """
    global _cleanup_running, _cleanup_task
    _cleanup_running = True
    if _cleanup_task is not None and not _cleanup_task.done():
        logger.info("Broadcast TTL cleanup task already running")
        return
    _cleanup_task = asyncio.create_task(_cleanup_expired_broadcasts())
    logger.info("Started background cleanup task for broadcast TTL")


async def stop_cleanup_task() -> None:
    """Stop the cleanup task gracefully during shutdown."""
    global _cleanup_running, _cleanup_task
    _cleanup_running = False
    if _cleanup_task is not None:
        _cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await _cleanup_task
        _cleanup_task = None
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
@router.message(Command("astats"))
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

        total_user_games = 0
        total_claimed = 0
        top_lines: list[str] = []
        try:
            total_user_games = int(await session.scalar(select(func.count(UserGame.id))) or 0)
            total_claimed = int(
                await session.scalar(
                    select(func.count(UserGame.id)).where(UserGame.status == "claimed")
                )
                or 0
            )

            top_result = await session.execute(
                select(Game.title, func.count(UserGame.id).label("claimed_count"))
                .join(UserGame, UserGame.game_external_id == Game.external_id)
                .where(UserGame.status == "claimed")
                .group_by(Game.title)
                .order_by(func.count(UserGame.id).desc())
                .limit(3)
            )
            top_rows = top_result.all()
            for title, count in top_rows:
                top_lines.append(f"• {title}: <b>{count}</b>")
        except Exception as exc:
            logger.warning("Extended admin stats unavailable: {exc}", exc=exc)

    claim_rate = (total_claimed / total_user_games * 100.0) if total_user_games else 0.0
    top_section = "\n".join(top_lines) if top_lines else "• N/A"

    text = (
        "📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total users: <b>{total_users}</b>\n"
        f"✅ Active users: <b>{active_users}</b>\n"
        f"🎮 Games sent: <b>{total_games}</b>\n"
        f"🧾 UserGame records: <b>{total_user_games}</b>\n"
        f"✅ Claimed total: <b>{total_claimed}</b>\n"
        f"📈 Claim rate: <b>{claim_rate:.1f}%</b>\n\n"
        "🏆 Top claimed games:\n"
        f"{top_section}"
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

    if _is_admin_throttled(message.from_user.id):
        await message.answer(
            t("admin_action_throttled", None, seconds=settings.ADMIN_COOLDOWN_SECONDS)
        )
        return

    _mark_admin_action(message.from_user.id)
    await message.answer("🔄 Running giveaway check…")
    logger.info("Admin {tg_id} triggered force_check", tg_id=message.from_user.id)

    # Late import to avoid circular dependency
    from bot.main import check_new_games

    try:
        await check_new_games(bot)
    except Exception:
        logger.exception("force_check failed for admin {tg_id}", tg_id=message.from_user.id)
        await message.answer(t("admin_operation_failed", None))
        return
    await message.answer("✅ Force check complete.")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message) -> None:
    """Request broadcast message from admin (admin only).

    Usage: /broadcast <text>
    """
    if not _is_admin(message):
        return

    if _is_admin_throttled(message.from_user.id):
        await message.answer(
            t("admin_action_throttled", None, seconds=settings.ADMIN_COOLDOWN_SECONDS)
        )
        return

    text = message.text
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
            t(
                "admin_broadcast_too_long",
                None,
                length=len(payload),
                max_length=settings.MAX_MESSAGE_LENGTH,
            )
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

    await message.answer(
        t("admin_broadcast_confirm", None, message=payload),
        parse_mode="HTML",
        reply_markup=confirm_keyboard,
    )


@router.callback_query(F.data == "broadcast:confirm")
async def cb_broadcast_confirm(callback: CallbackQuery, bot: Bot) -> None:
    """Confirm and send the broadcast message."""
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

    status_msg = await callback.message.edit_text(t("admin_broadcasting", None))

    async def _progress(done: int, total: int) -> None:
        try:
            await status_msg.edit_text(t("admin_broadcast_progress", None, done=done, total=total))
        except Exception:
            pass

    success, failed = await broadcast_text(bot, payload, progress_cb=_progress)

    _mark_admin_action(tg_id)
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
    tg_id = callback.from_user.id
    if tg_id != settings.ADMIN_ID:
        await callback.answer(t("admin_unauthorized", None), show_alert=True)
        return

    _pending_broadcast.pop(tg_id, None)
    await callback.message.delete()
    await callback.answer(t("admin_broadcast_cancelled", None))


@router.message(Command("backfill"))
async def cmd_backfill(message: Message, bot: Bot) -> None:
    """Re-fetch recent giveaways and broadcast any not already in DB (admin only).

    Usage: /backfill [N]
    N = how many recent giveaways to check (default BACKFILL_DEFAULT_LIMIT, capped at BACKFILL_MAX_LIMIT).
    """
    from bot.services.backfill import backfill_recent_games

    if not _is_admin(message):
        return

    if _is_admin_throttled(message.from_user.id):
        await message.answer(
            t("admin_action_throttled", None, seconds=settings.ADMIN_COOLDOWN_SECONDS)
        )
        return

    text = message.text or ""
    payload = text.removeprefix("/backfill").strip()
    limit = settings.BACKFILL_DEFAULT_LIMIT
    if payload:
        try:
            limit = int(payload)
        except ValueError:
            await message.answer(
                t(
                    "admin_backfill_usage",
                    None,
                    default=settings.BACKFILL_DEFAULT_LIMIT,
                    max=settings.BACKFILL_MAX_LIMIT,
                )
            )
            return
        if limit <= 0 or limit > settings.BACKFILL_MAX_LIMIT:
            await message.answer(
                t(
                    "admin_backfill_usage",
                    None,
                    default=settings.BACKFILL_DEFAULT_LIMIT,
                    max=settings.BACKFILL_MAX_LIMIT,
                )
            )
            return

    _mark_admin_action(message.from_user.id)
    status_msg = await message.answer(f"🔄 Running backfill (limit={limit})…")
    logger.info("Admin {tg_id} triggered backfill (limit={n})", tg_id=message.from_user.id, n=limit)

    try:
        fetched, already_known, broadcasted = await backfill_recent_games(bot, limit)
    except Exception:
        logger.exception("backfill failed for admin {tg_id}", tg_id=message.from_user.id)
        await status_msg.edit_text(t("admin_operation_failed", None))
        return

    if fetched == 0 and already_known == 0 and broadcasted == 0:
        await status_msg.edit_text(t("admin_backfill_empty", None))
    else:
        await status_msg.edit_text(
            t(
                "admin_backfill_done",
                None,
                fetched=fetched,
                already_known=already_known,
                broadcasted=broadcasted,
            ),
            parse_mode="HTML",
        )
