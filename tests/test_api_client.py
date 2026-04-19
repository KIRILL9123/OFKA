"""Tests for GamerPower API client retries and circuit breaker behavior."""

from __future__ import annotations

from typing import Any
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from bot.services import api_client


class _Response:
    def __init__(self, status: int, payload: Any) -> None:
        self.status = status
        self._payload = payload
        self.request_info = SimpleNamespace(real_url='https://example.test/api')
        self.history: tuple[Any, ...] = ()
        self.headers: dict[str, str] = {}

    async def json(self, content_type: str | None = None) -> Any:
        return self._payload


class _ResponseContext:
    def __init__(self, response: _Response) -> None:
        self._response = response

    async def __aenter__(self) -> _Response:
        return self._response

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


class _Session:
    def __init__(self, responses: list[_Response]) -> None:
        self._responses = responses
        self.calls = 0

    def get(self, _url: str) -> _ResponseContext:
        response = self._responses[self.calls]
        self.calls += 1
        return _ResponseContext(response)


class _SessionContext:
    def __init__(self, session: _Session) -> None:
        self._session = session

    async def __aenter__(self) -> _Session:
        return self._session

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


@pytest.fixture(autouse=True)
def reset_circuit_breaker_state() -> None:
    api_client._circuit_breaker._failure_count = 0
    api_client._circuit_breaker._opened_at = None


def test_circuit_breaker_closed_initially() -> None:
    breaker = api_client._CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=300)
    assert breaker.is_open() is False


def test_circuit_breaker_opens_after_threshold() -> None:
    breaker = api_client._CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=300)

    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()

    assert breaker.is_open() is True


def test_circuit_breaker_recovers_after_timeout() -> None:
    breaker = api_client._CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=300)

    with patch('bot.services.api_client.time.monotonic', side_effect=[100.0, 401.0]):
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.is_open() is False


@pytest.mark.asyncio
async def test_fetch_free_games_returns_empty_on_circuit_open() -> None:
    with patch.object(api_client._circuit_breaker, 'is_open', return_value=True):
        with patch('bot.services.api_client.aiohttp.ClientSession') as mock_client_session:
            result = await api_client.fetch_free_games()

    assert result == []
    mock_client_session.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_free_games_returns_active_games() -> None:
    payload = [
        {'id': 1, 'title': 'A', 'status': 'active'},
        {'id': 2, 'title': 'B', 'status': 'expired'},
    ]
    session = _Session([_Response(status=200, payload=payload)])

    with patch('bot.services.api_client.aiohttp.ClientSession', return_value=_SessionContext(session)):
        result = await api_client.fetch_free_games()

    assert result == [{'id': 1, 'title': 'A', 'status': 'active'}]


@pytest.mark.asyncio
async def test_fetch_free_games_returns_empty_on_201() -> None:
    session = _Session([_Response(status=201, payload=[])])

    with patch('bot.services.api_client.aiohttp.ClientSession', return_value=_SessionContext(session)):
        result = await api_client.fetch_free_games()

    assert result == []


@pytest.mark.asyncio
async def test_fetch_free_games_retries_on_503() -> None:
    responses = [
        _Response(status=503, payload=[]),
        _Response(status=503, payload=[]),
        _Response(status=200, payload=[{'id': 99, 'title': 'Recovered', 'status': 'active'}]),
    ]
    session = _Session(responses)

    with patch('bot.services.api_client.aiohttp.ClientSession', return_value=_SessionContext(session)):
        with patch('bot.services.api_client.asyncio.sleep', new=AsyncMock()) as sleep_mock:
            result = await api_client.fetch_free_games()

    assert result == [{'id': 99, 'title': 'Recovered', 'status': 'active'}]
    assert session.calls == 3
    assert sleep_mock.await_count == 2
