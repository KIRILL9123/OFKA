"""Backfill service — re-fetch recent giveaways and broadcast any new ones.

Used after bot downtime or to recover from missed giveaways.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy import select

from bot.core.database import async_session
from bot.models.models import Game
from bot.services.api_client import fetch_free_games
from bot.services.broadcaster import broadcast_game
from bot.utils.dates import format_end_date


async def backfill_recent_games(bot, limit: int) -> tuple[int, int, int]:
    """Re-fetch recent giveaways and broadcast any not already in the DB.

    Returns (fetched, already_known, broadcasted).
    """
    log = logger.bind(event="backfill", limit=limit)
    log.info("Starting backfill")

    games = await fetch_free_games()
    if not games:
        log.info("Backfill: API returned no games")
        return 0, 0, 0

    games_by_external_id: dict[int, dict[str, Any]] = {}
    for game in games:
        external_id = game.get("id")
        if isinstance(external_id, int):
            games_by_external_id[external_id] = game

    if not games_by_external_id:
        log.info("Backfill: no valid giveaways with external_id")
        return 0, 0, 0

    # Cap the candidates to the requested limit
    candidate_ids = list(games_by_external_id.keys())[:limit]

    async with async_session() as session:
        existing_result = await session.execute(
            select(Game.external_id).where(Game.external_id.in_(candidate_ids))
        )
        existing_ids = set(existing_result.scalars().all())

    new_ids = [eid for eid in candidate_ids if eid not in existing_ids]
    already_known = len(candidate_ids) - len(new_ids)

    new_games: list[dict[str, Any]] = []
    for eid in new_ids:
        game = games_by_external_id[eid]
        # Skip games with no title
        if not game.get("title"):
            continue
        # Skip expired games
        end_date_raw = game.get("end_date", "")
        if end_date_raw and end_date_raw != "N/A":
            if format_end_date(end_date_raw) is None:
                continue
        new_games.append(game)

    # Insert into DB
    if new_games:
        async with async_session() as session:
            session.add_all(
                [
                    Game(
                        external_id=g.get("id"),
                        title=g.get("title") or "Unknown",
                        worth=g.get("worth"),
                        end_date=g.get("end_date"),
                        thumbnail=g.get("thumbnail"),
                        platforms=g.get("platforms"),
                        description=g.get("description"),
                        open_giveaway_url=g.get("open_giveaway_url"),
                    )
                    for g in new_games
                ]
            )
            await session.commit()

    # Broadcast new games
    broadcasted = 0
    for game in new_games:
        await broadcast_game(bot, game)
        broadcasted += 1

    log.info(
        "Backfill complete",
        fetched=len(candidate_ids),
        already_known=already_known,
        broadcasted=broadcasted,
    )
    return len(candidate_ids), already_known, broadcasted
