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
    GAMERPOWER_API_URL: str = (
        "https://www.gamerpower.com/api/filter"
        "?platform=pc&type=game&sort-by=date"
    )


settings = Settings()
