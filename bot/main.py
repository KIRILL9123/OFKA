"""Entry point — bot startup, dispatcher wiring, and APScheduler job."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import URLInputFile
from aiogram.types import BotCommand, BotCommandScopeDefault
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from sqlalchemy import and_, or_, select, update

from bot.core.config import settings
from bot.core.database import async_session, engine, get_effective_database_url
from bot.core.translations import t
from bot.handlers import admin, games, user
from bot.handlers.admin import _start_cleanup_task, stop_cleanup_task
from bot.models.models import Game, User, UserGame
from bot.services.api_client import fetch_free_games
from bot.services.broadcaster import broadcast_game, build_game_keyboard_from_db
from bot.services.user_service import start_rate_limit_cleanup, stop_rate_limit_cleanup
from bot.utils.dates import format_end_date

_check_new_games_lock = asyncio.Lock()
_send_reminders_lock = asyncio.Lock()

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logger.remove()  # Remove default stderr handler
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
)
logger.add(
    "data/logs/bot.log",
    rotation="10 MB",
    retention="7 days",
    compression="zip",
    level="DEBUG",
)

# ---------------------------------------------------------------------------
# Scheduled job
# ---------------------------------------------------------------------------


async def check_new_games(bot: Bot) -> None:
    """Fetch giveaways from GamerPower and broadcast any new ones."""
    if _check_new_games_lock.locked():
        logger.warning("Skipping scheduled giveaway check: previous run still active")
        return

    async with _check_new_games_lock:
        logger.info("Running scheduled giveaway check")
        games = await fetch_free_games()

        if not games:
            logger.info("No active giveaways found")
            return

        games_by_external_id: dict[int, dict] = {}
        for game in games:
            external_id = game.get("id")
            if isinstance(external_id, int):
                games_by_external_id[external_id] = game

        if not games_by_external_id:
            logger.info("No valid giveaways with external_id found")
            return

        external_ids = list(games_by_external_id.keys())
        async with async_session() as session:
            existing_result = await session.execute(
                select(Game.external_id).where(Game.external_id.in_(external_ids))
            )
            existing_ids = set(existing_result.scalars().all())

            new_ids = [external_id for external_id in external_ids if external_id not in existing_ids]
            new_games = [games_by_external_id[external_id] for external_id in new_ids]

            if new_games:
                session.add_all(
                    [
                        Game(
                            external_id=external_id,
                            title=games_by_external_id[external_id].get("title") or "Unknown",
                            worth=games_by_external_id[external_id].get("worth"),
                            end_date=games_by_external_id[external_id].get("end_date"),
                            thumbnail=games_by_external_id[external_id].get("thumbnail"),
                            platforms=games_by_external_id[external_id].get("platforms"),
                            description=games_by_external_id[external_id].get("description"),
                            open_giveaway_url=games_by_external_id[external_id].get("open_giveaway_url"),
                        )
                        for external_id in new_ids
                    ]
                )
                await session.commit()

        new_count = 0
        for game in new_games:
            # Validate game has required fields and is not expired
            if not game.get("title") or not game.get("id"):
                logger.warning("Skipping invalid game: {game}", game=game)
                continue

            # Skip expired games
            end_date_raw = game.get("end_date", "")
            if end_date_raw and end_date_raw != "N/A":
                if format_end_date(end_date_raw) is None:  # Expired
                    logger.info("Skipping expired game: {title}", title=game.get("title"))
                    continue

            logger.info("New giveaway detected: {title}", title=game.get("title"))
            new_count += 1
            await broadcast_game(bot, game)

        logger.info("Check complete — {n} new game(s) broadcasted", n=new_count)


async def send_reminders(bot: Bot) -> None:
    """Send reminders for unclaimed games and explicit 'remind me tomorrow' requests."""
    if _send_reminders_lock.locked():
        logger.warning("Skipping reminder job: previous run still active")
        return

    async with _send_reminders_lock:
        await _send_reminders_impl(bot)


async def _send_reminders_impl(bot: Bot) -> None:
    """Internal reminder sender protected by a non-overlap lock."""
    log = logger.bind(event="reminder_job")
    log.info("Running daily reminder job")
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)

    auto_remind_filter = and_(
        UserGame.status == "notified",
        UserGame.updated_at < cutoff,
    )
    explicit_remind_filter = and_(
        UserGame.status == "remind",
        UserGame.remind_at.is_not(None),
        UserGame.remind_at <= now,
    )

    async with async_session() as session:
        result = await session.execute(
            select(UserGame, Game, User)
            .join(Game, Game.external_id == UserGame.game_external_id)
            .join(User, User.tg_id == UserGame.tg_id)
            .where(
                and_(
                    User.is_active.is_(True),
                    or_(auto_remind_filter, explicit_remind_filter),
                )
            )
        )
        rows = result.all()

    reminded_ids: list[int] = []
    for user_game, game, user_row in rows:
        # Skip if game is expired
        end_date = getattr(game, "end_date", None)
        if end_date:
            if format_end_date(end_date) is None:
                reminded_ids.append(user_game.id)
                continue

        lang = user_row.language
        text_msg = t(
            "reminder_message",
            lang,
            title=game.title,
        )
        keyboard = build_game_keyboard_from_db(game, lang)

        try:
            thumbnail = getattr(game, "thumbnail", None)
            if thumbnail:
                await bot.send_photo(
                    chat_id=user_game.tg_id,
                    photo=URLInputFile(thumbnail),
                    caption=text_msg,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
            else:
                await bot.send_message(
                    chat_id=user_game.tg_id,
                    text=text_msg,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
            reminded_ids.append(user_game.id)
            await asyncio.sleep(0.05)
        except TelegramForbiddenError:
            reminded_ids.append(user_game.id)
        except Exception as exc:
            log.warning(
                "Failed to send reminder",
                user_id=user_game.tg_id,
                giveaway_id=user_game.game_external_id,
                exc=exc,
            )

    if reminded_ids:
        async with async_session() as session:
            await session.execute(
                update(UserGame)
                .where(UserGame.id.in_(reminded_ids))
                .values(status="reminded")
            )
            await session.commit()

    log.info("Reminder job complete", sent=len(reminded_ids))


def _to_sync_db_url(database_url: str) -> str:
    """Convert async SQLAlchemy URL to sync URL for Alembic."""
    return database_url.replace("+aiosqlite", "")


def run_alembic_migrations() -> None:
    """Run Alembic migrations up to head."""
    root_dir = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(root_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(root_dir / "migrations"))
    alembic_cfg.set_main_option(
        "sqlalchemy.url",
        _to_sync_db_url(get_effective_database_url()),
    )
    command.upgrade(alembic_cfg, "head")


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------


async def on_startup(bot: Bot) -> None:
    """Run DB migrations, ensure data directories exist, and set up bot commands."""
    Path("data/logs").mkdir(parents=True, exist_ok=True)

    await asyncio.to_thread(run_alembic_migrations)
    logger.info("Database migrations applied")
    
    # Start background cleanup task for broadcast TTL
    await _start_cleanup_task()
    await start_rate_limit_cleanup()

    me = await bot.me()
    logger.info("Bot started as @{username}", username=me.username)

    # Set up bot commands for all languages (for command auto-completion)
    commands = [
        BotCommand(command="start", description="Subscribe to free games notifications"),
        BotCommand(command="settings", description="Change language and platforms"),
        BotCommand(command="help", description="How the bot works"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    logger.info("Bot commands registered")

    # Run initial check after DB is fully ready
    asyncio.create_task(check_new_games(bot))


async def on_shutdown(bot: Bot) -> None:
    """Clean up on shutdown."""
    # Stop cleanup task gracefully
    await stop_cleanup_task()
    await stop_rate_limit_cleanup()
    
    await engine.dispose()
    logger.info("Bot shut down gracefully")


async def main() -> None:
    """Wire everything together and start polling."""
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    # Register routers
    dp.include_router(user.router)
    dp.include_router(games.router)
    dp.include_router(admin.router)

    # Lifecycle hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Scheduler
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        check_new_games,
        trigger="interval",
        minutes=settings.CHECK_INTERVAL_MINUTES,
        args=[bot],
        id="check_new_games",
        replace_existing=True,
    )
    scheduler.add_job(
        send_reminders,
        trigger="cron",
        hour=12,
        minute=0,
        timezone="UTC",
        args=[bot],
        id="send_reminders",
        replace_existing=True,
    )
    logger.info("Reminder scheduler registered — fires daily at 12:00 UTC")
    scheduler.start()
    logger.info(
        "Scheduler started — checking every {m} min",
        m=settings.CHECK_INTERVAL_MINUTES,
    )

    try:
        await dp.start_polling(bot)
    finally:
        # Graceful shutdown: wait up to 30 seconds for running jobs to complete
        scheduler.shutdown(wait=True)
        logger.info("Scheduler shut down gracefully")


if __name__ == "__main__":
    asyncio.run(main())
