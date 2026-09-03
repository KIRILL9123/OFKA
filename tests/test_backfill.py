"""Tests for the backfill service and admin command."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from bot.handlers.admin import cmd_backfill
from bot.models.models import Base, Game, User
from bot.services.backfill import backfill_recent_games


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_active_user(session_factory, tg_id: int = 1001) -> None:
    async with session_factory() as session:
        async with session.begin():
            user = User(tg_id=tg_id, is_active=True, language="en", pref_steam=True)
            session.add(user)


@pytest.mark.asyncio
async def test_backfill_with_no_api_data_returns_zeros(session_factory, monkeypatch) -> None:
    monkeypatch.setattr("bot.services.backfill.async_session", session_factory)
    with patch("bot.services.backfill.fetch_free_games", new=AsyncMock(return_value=[])):
        fetched, already_known, broadcasted = await backfill_recent_games(AsyncMock(), limit=20)
    assert (fetched, already_known, broadcasted) == (0, 0, 0)


@pytest.mark.asyncio
async def test_backfill_inserts_new_games_and_skips_existing(session_factory, monkeypatch) -> None:
    await _seed_active_user(session_factory)
    monkeypatch.setattr("bot.services.backfill.async_session", session_factory)

    # Seed one existing game
    async with session_factory() as session:
        async with session.begin():
            session.add(Game(external_id=1, title="Existing", end_date="2099-12-31"))

    api_games = [
        {"id": 1, "title": "Existing", "end_date": "2099-12-31", "platforms": "Steam"},
        {"id": 2, "title": "Brand New", "end_date": "2099-12-31", "platforms": "Steam"},
    ]

    with patch("bot.services.backfill.fetch_free_games", new=AsyncMock(return_value=api_games)):
        bc = AsyncMock()
        with patch("bot.services.backfill.broadcast_game", new=bc):
            fetched, already_known, broadcasted = await backfill_recent_games(AsyncMock(), limit=20)

    assert fetched == 2
    assert already_known == 1
    assert broadcasted == 1
    bc.assert_awaited_once()


@pytest.mark.asyncio
async def test_backfill_skips_expired_games(session_factory, monkeypatch) -> None:
    await _seed_active_user(session_factory)
    monkeypatch.setattr("bot.services.backfill.async_session", session_factory)

    api_games = [
        {"id": 1, "title": "Expired", "end_date": "2020-01-01", "platforms": "Steam"},
        {"id": 2, "title": "Active", "end_date": "2099-12-31", "platforms": "Steam"},
    ]

    with patch("bot.services.backfill.fetch_free_games", new=AsyncMock(return_value=api_games)):
        bc = AsyncMock()
        with patch("bot.services.backfill.broadcast_game", new=bc):
            fetched, already_known, broadcasted = await backfill_recent_games(AsyncMock(), limit=20)

    assert fetched == 2
    assert already_known == 0
    assert broadcasted == 1  # only the active one


@pytest.mark.asyncio
async def test_backfill_respects_limit(session_factory, monkeypatch) -> None:
    await _seed_active_user(session_factory)
    monkeypatch.setattr("bot.services.backfill.async_session", session_factory)

    api_games = [
        {"id": i, "title": f"Game {i}", "end_date": "2099-12-31", "platforms": "Steam"}
        for i in range(1, 6)
    ]

    with patch("bot.services.backfill.fetch_free_games", new=AsyncMock(return_value=api_games)):
        with patch("bot.services.backfill.broadcast_game", new=AsyncMock()):
            fetched, already_known, broadcasted = await backfill_recent_games(AsyncMock(), limit=2)

    assert fetched == 2
    assert broadcasted == 2


def test_cmd_backfill_rejects_non_admin(monkeypatch) -> None:
    """Non-admin /backfill must do nothing."""
    from bot.core import config as cfg
    from bot.handlers import admin as admin_handlers

    called = []
    monkeypatch.setattr(admin_handlers, "_is_admin", lambda m: False)
    monkeypatch.setattr(admin_handlers, "_is_admin_throttled", lambda _: False)
    monkeypatch.setattr(
        "bot.services.backfill.backfill_recent_games",
        AsyncMock(side_effect=lambda *a, **k: called.append(True)),
    )
    monkeypatch.setattr(cfg.settings, "ADMIN_ID", 999999)

    msg = SimpleNamespace(
        from_user=SimpleNamespace(id=1),
        text="/backfill",
        answer=AsyncMock(),
    )
    import asyncio

    asyncio.run(cmd_backfill(msg, bot=AsyncMock()))

    assert called == []
    msg.answer.assert_not_awaited()


def test_cmd_backfill_rejects_invalid_n(monkeypatch) -> None:
    from bot.core import config as cfg
    from bot.handlers import admin as admin_handlers

    monkeypatch.setattr(admin_handlers, "_is_admin", lambda m: True)
    monkeypatch.setattr(admin_handlers, "_is_admin_throttled", lambda _: False)
    monkeypatch.setattr(cfg.settings, "ADMIN_ID", 999999)

    msg = SimpleNamespace(
        from_user=SimpleNamespace(id=999999),
        text="/backfill abc",
        answer=AsyncMock(),
    )
    import asyncio

    asyncio.run(cmd_backfill(msg, bot=AsyncMock()))

    msg.answer.assert_awaited_once()
    text = msg.answer.await_args.args[0]
    assert "Usage" in text or "Использование" in text
