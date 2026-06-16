"""Tests for scheduled giveaway filtering and broadcasting in check_new_games."""

from __future__ import annotations

from typing import Any
from unittest.mock import ANY, AsyncMock, patch

import pytest

import bot.main as main_module
from bot.main import check_new_games


class _ScalarResult:
    def __init__(self, values: list[int]) -> None:
        self._values = values

    def all(self) -> list[int]:
        return self._values


class _ExecuteResult:
    def __init__(self, values: list[int]) -> None:
        self._values = values

    def scalars(self) -> _ScalarResult:
        return _ScalarResult(self._values)


class _Session:
    def __init__(self, existing_ids: set[int]) -> None:
        self._existing_ids = existing_ids
        self.added_objects: list[Any] = []

    async def execute(self, *_args: Any, **_kwargs: Any) -> _ExecuteResult:
        return _ExecuteResult(list(self._existing_ids))

    def add_all(self, objects: list[Any]) -> None:
        self.added_objects.extend(objects)

    async def commit(self) -> None:
        return None


class _SessionContext:
    def __init__(self, session: _Session) -> None:
        self._session = session

    async def __aenter__(self) -> _Session:
        return self._session

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


def _make_async_session(existing_ids: set[int]) -> Any:
    def _factory() -> _SessionContext:
        return _SessionContext(_Session(existing_ids))

    return _factory


@pytest.mark.asyncio
async def test_no_games_returned() -> None:
    with patch('bot.main.fetch_free_games', new=AsyncMock(return_value=[])):
        with patch('bot.main.broadcast_game', new=AsyncMock()) as broadcast_mock:
            await check_new_games(AsyncMock())

    broadcast_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_game_is_broadcasted() -> None:
    game = {'id': 1, 'title': 'Test Game', 'status': 'active'}

    with patch('bot.main.fetch_free_games', new=AsyncMock(return_value=[game])):
        with patch('bot.main.async_session', _make_async_session(set())):
            with patch('bot.main.broadcast_game', new=AsyncMock()) as broadcast_mock:
                bot = AsyncMock()
                await check_new_games(bot)

    broadcast_mock.assert_awaited_once_with(ANY, game)


@pytest.mark.asyncio
async def test_already_known_game_not_broadcasted() -> None:
    game = {'id': 1, 'title': 'Test Game', 'status': 'active'}

    with patch('bot.main.fetch_free_games', new=AsyncMock(return_value=[game])):
        with patch('bot.main.async_session', _make_async_session({1})):
            with patch('bot.main.broadcast_game', new=AsyncMock()) as broadcast_mock:
                await check_new_games(AsyncMock())

    broadcast_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_expired_game_not_broadcasted() -> None:
    game = {'id': 1, 'title': 'Expired Game', 'status': 'active', 'end_date': '2020-01-01'}

    with patch('bot.main.fetch_free_games', new=AsyncMock(return_value=[game])):
        with patch('bot.main.async_session', _make_async_session(set())):
            with patch('bot.main.format_end_date', return_value=None):
                with patch('bot.main.broadcast_game', new=AsyncMock()) as broadcast_mock:
                    await check_new_games(AsyncMock())

    broadcast_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_new_games_skips_overlapping_run() -> None:
    await main_module._check_new_games_lock.acquire()
    try:
        with patch("bot.main.fetch_free_games", new=AsyncMock(return_value=[{"id": 1, "title": "A"}])) as fetch_mock:
            await check_new_games(AsyncMock())
    finally:
        main_module._check_new_games_lock.release()

    fetch_mock.assert_not_awaited()
