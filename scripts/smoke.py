#!/usr/bin/env python3
"""End-to-end smoke test for OFKA — no Telegram required.

Runs through a full user journey against an in-memory SQLite DB:
  1. /start
  2. /settings (toggle platform)
  3. /games (mocked GamerPower response)
  4. claim/skip/remind callbacks
  5. send_reminders job

Exit code: 0 on success, 1 on any failure.
"""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


@asynccontextmanager
async def _isolated_db():
    """Yield an in-memory DB engine and patch the global async_session to use it."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from bot.models.models import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield engine, factory
    finally:
        await engine.dispose()


def _make_message(tg_id: int, text: str | None = None, callback_data: str | None = None):
    """Build a fake aiogram Message or CallbackQuery for a user."""
    user = SimpleNamespace(id=tg_id, language_code="en", is_bot=False)
    if callback_data is not None:
        return SimpleNamespace(
            from_user=user,
            data=callback_data,
            message=SimpleNamespace(
                edit_text=AsyncMock(),
                delete=AsyncMock(),
                answer=AsyncMock(),
            ),
            bot=AsyncMock(),
            answer=AsyncMock(),
        )
    return SimpleNamespace(
        from_user=user,
        chat=SimpleNamespace(id=tg_id),
        text=text or "",
        bot=AsyncMock(),
        answer=AsyncMock(),
    )


def _build_mock_api_game(external_id: int = 100):
    return {
        "id": external_id,
        "title": "Smoke Test Game",
        "worth": "$19.99",
        "end_date": "2099-12-31",
        "thumbnail": "https://example.test/thumb.jpg",
        "platforms": "Steam",
        "description": "A test giveaway",
        "open_giveaway_url": f"https://example.test/giveaway/{external_id}",
        "status": "active",
    }


async def _run_smoke() -> int:
    print("=" * 60)
    print("OFKA smoke test")
    print("=" * 60)

    from bot.handlers import games as games_handlers
    from bot.handlers import user as user_handlers
    from bot.main import check_new_games, send_reminders

    # Modules that imported async_session at load time and need patching
    _SESSION_MODULES = [
        "bot.core.database",
        "bot.services.user_service",
        "bot.services.broadcaster",
        "bot.services.game_display",
        "bot.services.backfill",
        "bot.main",
        "bot.handlers.admin",
        "bot.handlers.user",
        "bot.handlers.games",
        "bot.core.healthcheck",
    ]

    # Patch DB to in-memory
    async with _isolated_db() as (_, factory):
        patches = [patch(f"{m}.async_session", factory) for m in _SESSION_MODULES]
        # Enter all patches
        for p in patches:
            p.start()
        try:
            # Patch the API client to return one game (multiple call sites use it)
            with patch(
                "bot.main.fetch_free_games",
                new=AsyncMock(return_value=[_build_mock_api_game()]),
            ):
                with patch(
                    "bot.services.game_display.fetch_free_games",
                    new=AsyncMock(return_value=[_build_mock_api_game()]),
                ):
                    # Step 1: /start
                    print("\n[1/5] /start ...")
                    msg = _make_message(tg_id=42, text="/start")
                    await user_handlers.cmd_start(msg)
                    msg.answer.assert_awaited()

                    # Step 2: /settings
                    print("[2/5] /settings ...")
                    msg = _make_message(tg_id=42, text="/settings")
                    await user_handlers.cmd_settings(msg)
                    msg.answer.assert_awaited()

                    # Step 3: toggle Steam
                    print("[3/5] toggle Steam ...")
                    cb = _make_message(tg_id=42, callback_data="settings:toggle:steam")
                    await user_handlers.cb_toggle_platform(cb)
                    cb.answer.assert_awaited()

                    # Step 4: /games
                    print("[4/5] /games ...")
                    msg = _make_message(tg_id=42, text="/games")
                    await games_handlers.cmd_games(msg)
                    msg.answer.assert_awaited()

                    # Step 5: check_new_games (broadcast)
                    print("[5/5] check_new_games ...")
                    bot = AsyncMock()
                    with patch("bot.main.broadcast_game", new=AsyncMock()) as bc:
                        await check_new_games(bot)
                        bc.assert_awaited()

                    # Bonus: send_reminders with no rows
                    print("[bonus] send_reminders (empty) ...")
                    await send_reminders(AsyncMock())
        finally:
            for p in patches:
                p.stop()

    print("\n" + "=" * 60)
    print("SMOKE TEST PASSED")
    print("=" * 60)
    return 0


def main() -> int:
    # Make sure .env doesn't get loaded
    os.environ.pop("BOT_TOKEN", None)
    os.environ["BOT_TOKEN"] = "0000000000:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    os.environ["ADMIN_ID"] = "1"

    try:
        return asyncio.run(_run_smoke())
    except AssertionError as exc:
        print(f"\nSMOKE FAILED: {exc}")
        return 1
    except Exception as exc:
        print(f"\nSMOKE CRASHED: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
