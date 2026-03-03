"""HTTP client for the GamerPower free-games API."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import aiohttp
from loguru import logger

from bot.core.config import settings

API_TIMEOUT = aiohttp.ClientTimeout(total=20)
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1.0
BACKOFF_MAX_SECONDS = 8.0


class _CircuitBreaker:
    """Small in-memory circuit breaker for API calls."""

    def __init__(self, failure_threshold: int, recovery_timeout_seconds: int) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self._failure_count = 0
        self._opened_at: float | None = None

    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        elapsed = time.monotonic() - self._opened_at
        if elapsed >= self.recovery_timeout_seconds:
            self._opened_at = None
            self._failure_count = 0
            return False
        return True

    def record_success(self) -> None:
        self._failure_count = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold:
            self._opened_at = time.monotonic()


_circuit_breaker = _CircuitBreaker(
    failure_threshold=3,
    recovery_timeout_seconds=300,
)


async def fetch_free_games() -> list[dict[str, Any]]:
    """Fetch current PC/Steam/Epic/GOG game giveaways from GamerPower.

    Uses the /api/filter endpoint which handles platform and type filtering
    server-side.  Returns a list of giveaway dicts.  On any network/parsing
    error an empty list is returned so the scheduler loop never crashes.
    """
    if _circuit_breaker.is_open():
        logger.warning(
            "Skipping GamerPower request: circuit breaker is open"
        )
        return []

    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with aiohttp.ClientSession(timeout=API_TIMEOUT) as session:
                async with session.get(settings.GAMERPOWER_API_URL) as resp:
                    # 201 means "no active giveaways" per API docs
                    if resp.status == 201:
                        _circuit_breaker.record_success()
                        logger.info("GamerPower: no active giveaways right now")
                        return []

                    # Retry transient HTTP statuses
                    if resp.status in {408, 425, 429, 500, 502, 503, 504}:
                        raise aiohttp.ClientResponseError(
                            request_info=resp.request_info,
                            history=resp.history,
                            status=resp.status,
                            message=f"Transient HTTP status {resp.status}",
                            headers=resp.headers,
                        )

                    if resp.status != 200:
                        _circuit_breaker.record_success()
                        logger.warning(
                            "GamerPower API returned non-retryable HTTP {status}",
                            status=resp.status,
                        )
                        return []

                    data = await resp.json(content_type=None)

                    # API may also return a dict with status key when empty
                    if isinstance(data, dict):
                        _circuit_breaker.record_success()
                        logger.info("GamerPower returned no active giveaways")
                        return []

                    games: list[dict[str, Any]] = [
                        g for g in data
                        if g.get("status", "").lower() == "active"
                    ]
                    _circuit_breaker.record_success()
                    logger.info(
                        "Fetched {count} active game giveaways",
                        count=len(games),
                    )
                    return games

        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                sleep_seconds = min(
                    BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)),
                    BACKOFF_MAX_SECONDS,
                )
                logger.warning(
                    "GamerPower request failed on attempt {attempt}/{max_attempts}: {exc}. Retrying in {delay:.1f}s",
                    attempt=attempt,
                    max_attempts=MAX_RETRIES,
                    exc=exc,
                    delay=sleep_seconds,
                )
                await asyncio.sleep(sleep_seconds)
                continue

            _circuit_breaker.record_failure()
            logger.error(
                "GamerPower request failed after {max_attempts} attempts: {exc}",
                max_attempts=MAX_RETRIES,
                exc=exc,
            )
            return []
        except Exception as exc:
            _circuit_breaker.record_failure()
            logger.error("Unexpected error in fetch_free_games: {exc}", exc=exc)
            return []

    _circuit_breaker.record_failure()
    logger.error(
        "GamerPower request exhausted retries without success: {exc}",
        exc=last_exc,
    )
    return []
