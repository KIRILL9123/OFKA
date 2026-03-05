"""Entry point — bot startup, dispatcher wiring, and APScheduler job."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from sqlalchemy import select

from bot.core.config import settings
from bot.core.database import async_session, engine, get_effective_database_url
from bot.handlers import admin, user
from bot.models.models import Game
from bot.services.api_client import fetch_free_games
from bot.services.broadcaster import broadcast_game

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
                        title=games_by_external_id[external_id].get("title", "Unknown"),
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
            from bot.services.broadcaster import _format_end_date
            formatted_date = _format_end_date(end_date_raw)
            if formatted_date is None:  # Expired
                logger.info("Skipping expired game: {title}", title=game.get("title"))
                continue
        
        logger.info("New giveaway detected: {title}", title=game.get("title"))
        new_count += 1
        await broadcast_game(bot, game)

    logger.info("Check complete — {n} new game(s) broadcasted", n=new_count)


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
    from bot.handlers.admin import _start_cleanup_task
    await _start_cleanup_task()

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
    from bot.handlers.admin import stop_cleanup_task
    await stop_cleanup_task()
    
    await engine.dispose()
    logger.info("Bot shut down gracefully")


async def main() -> None:
    """Wire everything together and start polling."""
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    # Register routers
    dp.include_router(user.router)
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
