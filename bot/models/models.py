"""SQLAlchemy ORM models for users and games."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    """Telegram user who subscribed to notifications."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    language: Mapped[str | None] = mapped_column(String(5), nullable=True, default=None)
    pref_steam: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("1"),
        nullable=False,
    )
    pref_epic: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("1"),
        nullable=False,
    )
    pref_gog: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("0"),
        nullable=False,
    )
    pref_other: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("0"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<User tg_id={self.tg_id} active={self.is_active} lang={self.language}>"


class Game(Base):
    """Game giveaway that has already been broadcasted."""

    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    worth: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Game id={self.external_id} title={self.title!r}>"


class UserGame(Base):
    """Per-user action state for a giveaway (claimed/skipped/remind)."""

    __tablename__ = "user_games"
    __table_args__ = (
        UniqueConstraint("tg_id", "game_external_id", name="uq_user_games_tg_game"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    game_external_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="claimed")
    remind_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<UserGame tg_id={self.tg_id} game_external_id={self.game_external_id} "
            f"status={self.status}>"
        )
