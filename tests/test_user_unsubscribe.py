from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.handlers import user as user_handlers


def test_cb_unsubscribe_sends_message_via_bot_after_delete(monkeypatch) -> None:
    tg_id = 123456

    async def fake_not_limited(_: int) -> bool:
        return False

    async def fake_get_or_create_user(_: int) -> tuple[str | None, bool, bool, bool, bool]:
        return "en", True, True, False, False

    class FakeSession:
        async def execute(self, *_args, **_kwargs) -> None:
            return None

        async def commit(self) -> None:
            return None

    class FakeSessionContext:
        async def __aenter__(self) -> FakeSession:
            return FakeSession()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    def fake_async_session() -> FakeSessionContext:
        return FakeSessionContext()

    monkeypatch.setattr(user_handlers, "_is_rate_limited", fake_not_limited)
    monkeypatch.setattr(user_handlers, "_get_or_create_user", fake_get_or_create_user)
    monkeypatch.setattr(user_handlers, "async_session", fake_async_session)

    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=tg_id),
        message=SimpleNamespace(delete=AsyncMock()),
        bot=SimpleNamespace(send_message=AsyncMock()),
        answer=AsyncMock(),
    )

    asyncio.run(user_handlers.cb_unsubscribe(callback))

    callback.message.delete.assert_awaited_once()
    callback.bot.send_message.assert_awaited_once()
    callback.answer.assert_awaited_once()
