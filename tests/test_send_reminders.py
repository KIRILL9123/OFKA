"""Integration tests for send_reminders using a real in-memory SQLite DB."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from bot.main import send_reminders
from bot.models.models import Base, Game, User, UserGame


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


async def _seed_user_with_game(
    session_factory,
    *,
    user_status: str,
    user_updated_at: datetime,
    remind_at: datetime | None,
    user_active: bool = True,
) -> int:
    """Insert one user, one game, one user_game. Returns the UserGame.id."""
    async with session_factory() as session:
        async with session.begin():
            user = User(tg_id=999001, is_active=user_active, language="en")
            session.add(user)
            await session.flush()
            game = Game(
                external_id=42,
                title="Sample Game",
                worth="$9.99",
                end_date="2099-12-31",
                thumbnail=None,
                platforms="Steam",
                description="",
                open_giveaway_url="https://example.test/giveaway/42",
            )
            session.add(game)
            await session.flush()
            ug = UserGame(
                tg_id=user.tg_id,
                game_external_id=game.external_id,
                status=user_status,
                remind_at=remind_at,
                updated_at=user_updated_at,
            )
            session.add(ug)
            await session.flush()
            return ug.id


@pytest.mark.asyncio
async def test_send_reminders_skips_explicit_remind_with_future_time(
    session_factory, monkeypatch
) -> None:
    """A 'remind' row with remind_at in the future must NOT trigger a reminder."""
    now = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
    future = now + timedelta(hours=12)
    fresh = now - timedelta(hours=1)
    await _seed_user_with_game(
        session_factory,
        user_status="remind",
        user_updated_at=fresh,
        remind_at=future,
    )

    bot_sends = []
    bot = type("B", (), {})()

    async def _send(*args, **kwargs):
        bot_sends.append((args, kwargs))

    bot.send_message = _send
    bot.send_photo = _send

    class _FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr("bot.main.datetime", _FixedDateTime)
    monkeypatch.setattr("bot.main.async_session", session_factory)

    await send_reminders(bot)
    assert bot_sends == []


@pytest.mark.asyncio
async def test_send_reminders_sends_explicit_remind_with_past_time(
    session_factory, monkeypatch
) -> None:
    """A 'remind' row with remind_at in the past MUST trigger a reminder."""
    now = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
    past = now - timedelta(hours=1)
    fresh = now - timedelta(hours=1)
    await _seed_user_with_game(
        session_factory,
        user_status="remind",
        user_updated_at=fresh,
        remind_at=past,
    )

    bot_sends = []
    bot = type("B", (), {})()

    async def _send(*args, **kwargs):
        bot_sends.append((args, kwargs))

    bot.send_message = _send
    bot.send_photo = _send

    class _FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr("bot.main.datetime", _FixedDateTime)
    monkeypatch.setattr("bot.main.async_session", session_factory)

    await send_reminders(bot)
    assert len(bot_sends) == 1


@pytest.mark.asyncio
async def test_send_reminders_skips_fresh_notified(session_factory, monkeypatch) -> None:
    """A 'notified' row updated <24h ago must NOT trigger a reminder."""
    now = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
    fresh = now - timedelta(hours=1)
    await _seed_user_with_game(
        session_factory,
        user_status="notified",
        user_updated_at=fresh,
        remind_at=None,
    )

    bot_sends = []
    bot = type("B", (), {})()

    async def _send(*args, **kwargs):
        bot_sends.append((args, kwargs))

    bot.send_message = _send
    bot.send_photo = _send

    class _FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr("bot.main.datetime", _FixedDateTime)
    monkeypatch.setattr("bot.main.async_session", session_factory)

    await send_reminders(bot)
    assert bot_sends == []


@pytest.mark.asyncio
async def test_send_reminders_sends_auto_for_old_notified(session_factory, monkeypatch) -> None:
    """A 'notified' row updated >24h ago MUST trigger a reminder."""
    now = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=25)
    await _seed_user_with_game(
        session_factory,
        user_status="notified",
        user_updated_at=old,
        remind_at=None,
    )

    bot_sends = []
    bot = type("B", (), {})()

    async def _send(*args, **kwargs):
        bot_sends.append((args, kwargs))

    bot.send_message = _send
    bot.send_photo = _send

    class _FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr("bot.main.datetime", _FixedDateTime)
    monkeypatch.setattr("bot.main.async_session", session_factory)

    await send_reminders(bot)
    assert len(bot_sends) == 1


@pytest.mark.asyncio
async def test_send_reminders_skips_inactive_user(session_factory, monkeypatch) -> None:
    """Inactive users should never receive reminders."""
    now = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=25)
    await _seed_user_with_game(
        session_factory,
        user_status="notified",
        user_updated_at=old,
        remind_at=None,
        user_active=False,
    )

    bot_sends = []
    bot = type("B", (), {})()

    async def _send(*args, **kwargs):
        bot_sends.append((args, kwargs))

    bot.send_message = _send
    bot.send_photo = _send

    class _FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr("bot.main.datetime", _FixedDateTime)
    monkeypatch.setattr("bot.main.async_session", session_factory)

    await send_reminders(bot)
    assert bot_sends == []
