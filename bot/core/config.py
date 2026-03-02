"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Bot configuration sourced from .env file or environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    BOT_TOKEN: str
    ADMIN_ID: int
    DATABASE_URL: str = "sqlite+aiosqlite:///data/bot.db"
    CHECK_INTERVAL_MINUTES: int = 15
    # Security settings
    MAX_CALLBACK_LENGTH: int = 256  # Prevent oversized callback data
    MAX_MESSAGE_LENGTH: int = 4096  # Telegram HTML message limit
    USER_RATE_LIMIT_PER_MINUTE: int = 30  # Max commands per user per minute
    SPAM_COOLDOWN_SECONDS: int = 1  # Cooldown between messages to same user
    GAMERPOWER_API_URL: str = (
        "https://www.gamerpower.com/api/filter"
        "?platform=pc&type=game&sort-by=date"
    )

    def __repr__(self) -> str:
        """Override repr to hide sensitive tokens in logs."""
        return (
            f"Settings("
            f"BOT_TOKEN={self.BOT_TOKEN[:10]}***, "
            f"ADMIN_ID={self.ADMIN_ID}, "
            f"DATABASE_URL={self.DATABASE_URL}, "
            f"...)"
        )


settings = Settings()
