"""Guard tests: translations completeness and config fail-fast."""

from __future__ import annotations

import pytest

from bot.core import translations
from bot.core.config import Settings


def test_all_keys_present_in_all_languages() -> None:
    for key, texts in translations._TEXTS.items():
        missing = [lang for lang in translations.LANGUAGES if not texts.get(lang)]
        assert not missing, f"key '{key}' missing languages: {missing}"


def test_t_falls_back_to_english_for_unknown_lang() -> None:
    assert translations.t("date_today", "xx") == translations.t("date_today", "en")


def test_t_returns_key_for_unknown_key() -> None:
    assert translations.t("no_such_key", "en") == "no_such_key"


def test_placeholder_token_fails_fast() -> None:
    settings = Settings(BOT_TOKEN="1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ", _env_file=None)
    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        settings.ensure_runtime_ready()


def test_real_token_passes_fail_fast() -> None:
    settings = Settings(
        BOT_TOKEN="1111111111:" + "A" * 35,
        _env_file=None,
    )
    settings.ensure_runtime_ready()
