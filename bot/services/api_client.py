"""HTTP client for the GamerPower free-games API."""

from __future__ import annotations

from typing import Any

import aiohttp
from loguru import logger

from bot.core.config import settings

API_TIMEOUT = aiohttp.ClientTimeout(total=30)


async def fetch_free_games() -> list[dict[str, Any]]:
    """Fetch current PC/Steam/Epic/GOG game giveaways from GamerPower.

    Uses the /api/filter endpoint which handles platform and type filtering
    server-side.  Returns a list of giveaway dicts.  On any network/parsing
    error an empty list is returned so the scheduler loop never crashes.
    """
    try:
        async with aiohttp.ClientSession(timeout=API_TIMEOUT) as session:
            async with session.get(settings.GAMERPOWER_API_URL) as resp:
                # 201 means "no active giveaways" per API docs
                if resp.status == 201:
                    logger.info("GamerPower: no active giveaways right now")
                    return []

                if resp.status != 200:
                    logger.warning(
                        "GamerPower API returned HTTP {status}",
                        status=resp.status,
                    )
                    return []

                data = await resp.json(content_type=None)

                # API may also return a dict with status key when empty
                if isinstance(data, dict):
                    logger.info("GamerPower returned no active giveaways")
                    return []

                games: list[dict[str, Any]] = [
                    g for g in data
                    if g.get("status", "").lower() == "active"
                ]
                logger.info("Fetched {count} active game giveaways", count=len(games))
                return games

    except aiohttp.ClientError as exc:
        logger.error("Network error while fetching giveaways: {exc}", exc=exc)
        return []
    except Exception as exc:
        logger.error("Unexpected error in fetch_free_games: {exc}", exc=exc)
        return []
