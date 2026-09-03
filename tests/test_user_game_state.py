"""Tests for user_game state upsert guard against orphan rows."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.handlers.games import _upsert_user_game_state
from bot.models.models import Base, Game, UserGame


@pytest.fixture
async def session_maker():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


@pytest.mark.asyncio
async def test_upsert_unknown_game_creates_no_orphan(session_maker) -> None:
    with patch("bot.handlers.games.async_session", session_maker):
        changed = await _upsert_user_game_state(42, 999, "claimed")

    assert changed is False

    async with session_maker() as session:
        rows = (await session.execute(select(UserGame))).scalars().all()
        assert rows == []


@pytest.mark.asyncio
async def test_upsert_known_game_creates_state(session_maker) -> None:
    async with session_maker() as session:
        session.add(Game(external_id=7, title="Known"))
        await session.commit()

    with patch("bot.handlers.games.async_session", session_maker):
        changed = await _upsert_user_game_state(42, 7, "claimed")

    assert changed is True

    async with session_maker() as session:
        rows = (await session.execute(select(UserGame))).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == "claimed"
