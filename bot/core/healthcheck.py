"""Health check for Docker — verifies DB connectivity.

Run with: `python -m bot.core.healthcheck`
Exits 0 on success, 1 on failure.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger
from sqlalchemy import text

from bot.core.database import async_session


async def _check_db() -> bool:
    try:
        async with async_session() as session:
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as exc:
        logger.error("Healthcheck DB error: {exc}", exc=exc)
        return False


async def main() -> int:
    if not await _check_db():
        logger.error("Healthcheck FAILED")
        return 1
    logger.info("Healthcheck OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
