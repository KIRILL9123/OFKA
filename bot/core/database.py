"""Async SQLAlchemy engine and session factory."""

from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bot.core.config import settings


def get_effective_database_url() -> str:
    """Resolve DB URL for local/dev runs when .env contains Docker paths."""
    database_url = settings.DATABASE_URL

    if database_url.startswith("sqlite+aiosqlite:////app/"):
        project_root = Path(__file__).resolve().parents[2]
        relative_path = database_url.removeprefix("sqlite+aiosqlite:////app/")
        local_db_path = (project_root / relative_path).resolve()
        local_db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{local_db_path.as_posix()}"

    if database_url.startswith("sqlite+aiosqlite:///") and "///:" not in database_url:
        # Relative sqlite path -> make it absolute from project root for stable startup.
        project_root = Path(__file__).resolve().parents[2]
        relative_path = database_url.removeprefix("sqlite+aiosqlite:///")
        local_db_path = (project_root / relative_path).resolve()
        local_db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{local_db_path.as_posix()}"

    return database_url


engine = create_async_engine(get_effective_database_url(), echo=False)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
