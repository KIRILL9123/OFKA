"""Application configuration loaded from environment variables."""

import re
from typing import ClassVar

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Bot configuration sourced from .env file or environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    BOT_TOKEN: str = "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ"
    ADMIN_ID: int = 123456789
    DATABASE_URL: str = "sqlite+aiosqlite:///data/bot.db"
    CHECK_INTERVAL_MINUTES: int = 15
    MAX_CALLBACK_LENGTH: int = 256
    MAX_MESSAGE_LENGTH: int = 4096
    USER_RATE_LIMIT_PER_MINUTE: int = 30
    SPAM_COOLDOWN_SECONDS: int = 1
    ADMIN_COOLDOWN_SECONDS: int = 30
    BACKFILL_DEFAULT_LIMIT: int = 20
    BACKFILL_MAX_LIMIT: int = 100
    GAMERPOWER_API_URL: str = (
        "https://www.gamerpower.com/api/filter?platform=pc&type=game&sort-by=date"
    )
    BLOCKED_GIVEAWAY_DOMAINS: str = "freebies.indiegala.com,itch.io"

    @property
    def blocked_giveaway_domains(self) -> tuple[str, ...]:
        """Return tuple of blocked domains parsed from comma-separated string."""
        if not self.BLOCKED_GIVEAWAY_DOMAINS:
            return ()
        return tuple(
            d.strip().lower() for d in self.BLOCKED_GIVEAWAY_DOMAINS.split(",") if d.strip()
        )

    DEFAULT_PLACEHOLDER_TOKEN: ClassVar[str] = "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ"

    def ensure_runtime_ready(self) -> None:
        """Fail fast if the bot would start with a non-functional placeholder token."""
        if self.BOT_TOKEN == self.DEFAULT_PLACEHOLDER_TOKEN:
            raise RuntimeError(
                "BOT_TOKEN is still the placeholder value — set a real token in .env"
            )

    @field_validator("BOT_TOKEN")
    @classmethod
    def validate_bot_token(cls, value: str) -> str:
        if not re.match(r"^\d+:[A-Za-z0-9_-]+$", value):
            raise ValueError("Invalid bot token format")
        return value

    def __repr__(self) -> str:
        return (
            f"Settings("
            f"BOT_TOKEN={self.BOT_TOKEN[:10]}***, "
            f"ADMIN_ID={self.ADMIN_ID}, "
            f"DATABASE_URL={self.DATABASE_URL}, "
            f"...)"
        )


settings = Settings()
