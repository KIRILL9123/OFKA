"""Shared user-related helpers used by multiple handlers.

Lives in bot.services (not bot.handlers) so that handlers can import it
without creating circular dependencies.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
import time

from sqlalchemy import select

from bot.core.config import settings
from bot.core.database import async_session
from bot.models.models import User


_user_rate_limit: dict[int, list[float]] = {}
_user_rate_limit_lock = asyncio.Lock()
_rate_limit_cleanup_running = True
_rate_limit_cleanup_task: asyncio.Task | None = None


async def is_rate_limited(tg_id: int) -> bool:
    """Check if user has exceeded rate limit (prevent spam/DoS)."""
    now = time.time()
    cutoff = now - 60

    async with _user_rate_limit_lock:
        if tg_id not in _user_rate_limit:
            _user_rate_limit[tg_id] = [now]
            return False

        _user_rate_limit[tg_id] = [ts for ts in _user_rate_limit[tg_id] if ts > cutoff]
        if not _user_rate_limit[tg_id]:
            del _user_rate_limit[tg_id]
            _user_rate_limit[tg_id] = [now]
            return False

        if len(_user_rate_limit[tg_id]) >= settings.USER_RATE_LIMIT_PER_MINUTE:
            return True

        _user_rate_limit[tg_id].append(now)
        return False


async def _cleanup_rate_limit_cache() -> None:
    """Background task to evict stale user rate-limit entries."""
    while _rate_limit_cleanup_running:
        try:
            await asyncio.sleep(300)
            if not _rate_limit_cleanup_running:
                break

            now = time.time()
            cutoff = now - 60
            async with _user_rate_limit_lock:
                stale_ids = [
                    tg_id
                    for tg_id, timestamps in _user_rate_limit.items()
                    if timestamps and all(ts <= cutoff for ts in timestamps)
                ]
                for tg_id in stale_ids:
                    _user_rate_limit.pop(tg_id, None)
        except asyncio.CancelledError:
            break
        except Exception:
            pass


async def start_rate_limit_cleanup() -> None:
    """Start background cleanup task for in-memory rate-limit cache."""
    global _rate_limit_cleanup_running, _rate_limit_cleanup_task
    _rate_limit_cleanup_running = True
    if _rate_limit_cleanup_task is not None and not _rate_limit_cleanup_task.done():
        return
    _rate_limit_cleanup_task = asyncio.create_task(_cleanup_rate_limit_cache())


async def stop_rate_limit_cleanup() -> None:
    """Signal background cleanup task to stop gracefully."""
    global _rate_limit_cleanup_running, _rate_limit_cleanup_task
    _rate_limit_cleanup_running = False
    if _rate_limit_cleanup_task is not None:
        _rate_limit_cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await _rate_limit_cleanup_task
        _rate_limit_cleanup_task = None


async def get_or_create_user(
    tg_id: int,
) -> tuple[str | None, bool, bool, bool, bool, bool, bool]:
    """Fetch user settings in one query, creating/reactivating the user when needed."""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalars().first()

        created = False
        reactivated = False
        if user is None:
            created = True
            user = User(tg_id=tg_id, is_active=True)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        elif not user.is_active:
            reactivated = True
            user.is_active = True
            await session.commit()

        return (
            user.language,
            user.pref_steam,
            user.pref_epic,
            user.pref_gog,
            user.pref_other,
            created,
            reactivated,
        )
