# OFKA — Telegram-бот раздач бесплатных игр

Бот, который каждые 15 минут опрашивает [GamerPower API](https://www.gamerpower.com/) на бесплатные PC-раздачи **только для Steam и Epic Games Store** и рассылает их подписчикам на 4 языках (ru, uk, en, de).

## Возможности

- Подписка по `/start` с настройкой языка и платформ (Steam / Epic)
- Рассылка новых раздач с картинкой, кнопками `Забрать / Пропустить / Напомнить завтра`
- Ежедневные напоминания о неполученных играх (12:00 UTC)
- Админ-команды: `/stats`, `/astats`, `/force_check`, `/broadcast`, `/backfill`
- Rate-limit, circuit-breaker на API, миграции Alembic

## Стек

- Python 3.12+
- [aiogram 3](https://docs.aiogram.dev/) — Telegram-фреймворк
- SQLAlchemy 2 (async) + aiosqlite + Alembic
- APScheduler для фоновых задач
- aiohttp + loguru

## Структура

```
bot/
  main.py              # точка входа, dispatcher, scheduler
  core/                # config, database, translations
  handlers/            # user, games, admin
  models/              # ORM (User, Game, UserGame)
  services/            # api_client, broadcaster, game_display, backfill
  utils/               # date helpers
migrations/            # Alembic
tests/                 # pytest
scripts/               # smoke.py — E2E smoke test без Telegram
```

## Запуск локально

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # Linux/macOS
pip install -r requirements.txt -r requirements-dev.txt

cp .env.example .env
# заполнить BOT_TOKEN и ADMIN_ID

alembic upgrade head               # применить миграции
pytest                             # тесты
python -m bot.main                 # запустить бота
```

## Запуск в Docker

```bash
docker compose up --build -d
docker compose logs -f bot
```

`docker-compose.override.yml` — опциональный dev-override (монтирует исходники read-only, не коммитится).

## Миграции

```bash
alembic upgrade head            # применить
alembic downgrade -1            # откатить одну
alembic current                 # текущая ревизия
alembic history                 # список ревизий
```

В `bot/main.py` миграции применяются автоматически при старте (`run_alembic_migrations`).

## Конфигурация (`.env`)

| Переменная | По умолчанию | Назначение |
|------------|--------------|-----------|
| `BOT_TOKEN` | — (обязательно) | токен Telegram-бота |
| `ADMIN_ID` | — (обязательно) | Telegram user id админа |
| `DATABASE_URL` | `sqlite+aiosqlite:///data/bot.db` | URL БД |
| `CHECK_INTERVAL_MINUTES` | `15` | как часто опрашивать GamerPower |
| `GAMERPOWER_API_URL` | `https://www.gamerpower.com/api/filter?platform=pc&type=game&sort-by=date` | URL API |
| `BLOCKED_GIVEAWAY_DOMAINS` | `freebies.indiegala.com,itch.io` | домены-исключения для раздач |

Полный список — в `bot/core/config.py`.

## Тесты

```bash
pytest            # тесты + отчёт покрытия
python scripts\smoke.py    # E2E smoke test (in-memory SQLite)
```

Покрывают: circuit-breaker и ретраи API, фильтрацию платформ в broadcaster, форматирование дат, логику `check_new_games`, отписку, напоминания. CI (`.github/workflows/ci.yml`) гоняет ruff + pytest на каждый push/PR.

## Деплой

Бот упакован в multi-stage `Dockerfile` (python:3.12-alpine, сборка gcc только в builder-стадии), `restart: always`, healthcheck через `python -c "import bot.core.healthcheck"`. На VPS:

```bash
git pull
docker compose build --no-cache bot
docker compose up -d bot
docker compose logs -f bot
```
