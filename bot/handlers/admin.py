"""Admin-only handlers: /stats, /force_check, /broadcast."""

from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger
from sqlalchemy import func, select

from bot.core.config import settings
from bot.core.database import async_session
from bot.models.models import Game, User
from bot.services.broadcaster import broadcast_text

router = Router(name="admin")


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
async def cmd_broadcast(message: Message, bot: Bot) -> None:
    """Broadcast a custom HTML message to all active users (admin only).

    Usage: /broadcast <text>
    """
    if not _is_admin(message):
        return

    text = message.text
    if text is None:
        await message.answer("❌ Message text cannot be empty.")
        return

    # Strip the /broadcast command prefix
    payload = text.removeprefix("/broadcast").strip()
    if not payload:
        await message.answer("❌ Usage: /broadcast &lt;text&gt;")
        return

    # Validate broadcast message length
    if len(payload) > settings.MAX_MESSAGE_LENGTH:
        await message.answer(
            f"❌ Message too long ({len(payload)} chars, max {settings.MAX_MESSAGE_LENGTH})."
        )
        return

    await message.answer("📤 Broadcasting…")
    success, failed = await broadcast_text(bot, payload)
    await message.answer(
        f"✅ Broadcast done.\n"
        f"Delivered: <b>{success}</b> | Failed: <b>{failed}</b>",
        parse_mode="HTML",
    )
    logger.info(
        "Admin {tg_id} broadcast: {ok} delivered, {fail} failed",
        tg_id=message.from_user.id,
        ok=success,
        fail=failed,
    )
