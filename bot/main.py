"""Entry point — bot startup, dispatcher wiring, and APScheduler job."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from sqlalchemy import select, text

from bot.core.config import settings
from bot.core.database import async_session, engine
from bot.handlers import admin, user
from bot.models.models import Base, Game
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

    new_count = 0
    for game in games:
        external_id = game.get("id")
        if external_id is None:
            continue

        async with async_session() as session:
            exists = await session.scalar(
                select(Game.id).where(Game.external_id == external_id)
            )
            if exists:
                continue

            # Save new game to DB
            db_game = Game(
                external_id=external_id,
                title=game.get("title", "Unknown"),
            )
            session.add(db_game)
            await session.commit()

        logger.info("New giveaway detected: {title}", title=game.get("title"))
        new_count += 1
        await broadcast_game(bot, game)

    logger.info("Check complete — {n} new game(s) broadcasted", n=new_count)


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------


async def on_startup(bot: Bot) -> None:
    """Create DB tables, apply migrations, and ensure data directories exist."""
    Path("data/logs").mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Migrations: add missing users columns for old DBs
    async with engine.begin() as conn:
        columns = await conn.execute(text("PRAGMA table_info(users)"))
        col_names = {row[1] for row in columns}

        if "language" not in col_names:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN language VARCHAR(5)")
            )
            logger.info("Migrated: added 'language' column to users table")

        if "pref_steam" not in col_names:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN pref_steam BOOLEAN NOT NULL DEFAULT 1")
            )
            logger.info("Migrated: added 'pref_steam' column to users table")

        if "pref_epic" not in col_names:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN pref_epic BOOLEAN NOT NULL DEFAULT 1")
            )
            logger.info("Migrated: added 'pref_epic' column to users table")

        if "pref_gog" not in col_names:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN pref_gog BOOLEAN NOT NULL DEFAULT 0")
            )
            logger.info("Migrated: added 'pref_gog' column to users table")

        if "pref_other" not in col_names:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN pref_other BOOLEAN NOT NULL DEFAULT 0")
            )
            logger.info("Migrated: added 'pref_other' column to users table")

        # Safety for old DB values that may contain NULLs
        await conn.execute(text("UPDATE users SET pref_steam = 1 WHERE pref_steam IS NULL"))
        await conn.execute(text("UPDATE users SET pref_epic = 1 WHERE pref_epic IS NULL"))
        await conn.execute(text("UPDATE users SET pref_gog = 0 WHERE pref_gog IS NULL"))
        await conn.execute(text("UPDATE users SET pref_other = 0 WHERE pref_other IS NULL"))

    logger.info("Database tables ready")

    me = await bot.me()
    logger.info("Bot started as @{username}", username=me.username)

    # Run initial check after DB is fully ready
    asyncio.create_task(check_new_games(bot))


async def on_shutdown(bot: Bot) -> None:
    """Clean up on shutdown."""
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
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
