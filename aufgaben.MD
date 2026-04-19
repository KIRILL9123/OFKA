Провел **максимально детальный аудит** всего кода. Вот полный список найденных проблем:

***

## 🔴 КРИТИЧЕСКИЕ БАГИ (Must Fix)

### 1. **CRASH: callback.message.answer() после delete()**
```python
# bot/handlers/user.py:356-359
await callback.message.delete()
await callback.message.answer(  # ⚠️ AttributeError!
    t("unsubscribe_confirmed", lang),
```


**Проблема**: После удаления сообщения нельзя вызывать `.answer()` на нём
**Фикс**: 
```python
await callback.message.delete()
await callback.bot.send_message(
    chat_id=callback.from_user.id,
    text=t("unsubscribe_confirmed", lang),
    parse_mode="HTML",
)
```

### 2. **Race condition в _user_rate_limit**
```python
_user_rate_limit: dict[int, list[float]] = {}
```


**Проблема**: Глобальный словарь без thread-safety для async операций
- Если 2 запроса от одного пользователя придут одновременно, race condition
- Может привести к пропуску rate-limit проверки
**Фикс**: Использовать `asyncio.Lock` или библиотеку `aiocache`

### 3. **Утечка памяти в _pending_broadcast**
```python
_pending_broadcast: dict[int, str] = {}
```


**Проблема**: Если админ не нажмёт кнопки, сообщение останется в памяти навсегда
**Фикс**: Добавить TTL или автоочистку

### 4. **Telegram caption limit overflow**
```python
title = game.get("title", unknown)  # Нет проверки длины!
```


**Проблема**: Caption ограничен 1024 символами, но:
- `title` может быть 500+ символов
- `platforms` может быть длинным
- `description` обрезан до 800, но вместе всё может превысить лимит
**Фикс**: Добавить проверку общей длины и обрезать title

### 5. **SQLite server_default конфликтует с Python default**
```python
pref_steam: Mapped[bool] = mapped_column(
    Boolean,
    default=True,
    server_default=text("1"),  # ⚠️ Дублирование
    nullable=False,
)
```


**Проблема**: При создании пользователя через Python ORM используется `default=True`, но при INSERT через SQL используется `server_default`. Это может привести к несоответствию в edge cases
**Фикс**: Оставить только `server_default` или только `default`

***

## 🟡 ВАЖНЫЕ ПРОБЛЕМЫ (Should Fix)

### 6. **Проблема #6 не исправлена: различие первого и повторного /start**
```python
async def cmd_start(message: Message) -> None:
    await _ensure_user_exists(tg_id)  # Всегда ставит is_active=True
```


**Проблема**: Если пользователь отписался (is_active=False), а потом снова сделал /start:
- Он получит то же приветствие, что и новый пользователь
- Нет сообщения "Рады видеть снова! Уведомления возобновлены"
**Фикс**: Проверять старое значение `is_active` перед обновлением

### 7. **Парсинг дат с локалями упадёт**
```python
for fmt in ["%Y-%m-%d", "%B %d, %Y", ...]:  # ⚠️ %B требует английскую локаль
    end = datetime.strptime(end_date_raw.strip(), fmt)
```


**Проблема**: Формат `"%B %d, %Y"` работает только с английскими месяцами ("March"), но API может вернуть другой язык
**Фикс**: Убрать `"%B %d, %Y"` или добавить locale handling

### 8. **Partial match платформ слишком агрессивный**
```python
if key in platform:  # "epic" найдётся в "epicenter", "steam" в "steamworks"
    formatted.append(emoji_text)
```


**Проблема**: Ложные совпадения
**Фикс**: Использовать word boundaries или точное сравнение

### 9. **Отсутствует валидация BOT_TOKEN**
```python
class Settings(BaseSettings):
    BOT_TOKEN: str  # Нет валидации формата
```


**Проблема**: Если токен невалидный (не начинается с числа, нет `:`), бот упадёт только при запуске
**Фикс**: Добавить `@field_validator` для проверки формата `\d+:[A-Za-z0-9_-]+`

### 10. **rate_limit проверка вызывается после _ensure_user_exists**
```python
if _is_rate_limited(tg_id):
    await message.answer(...)
    return
await _ensure_user_exists(tg_id)  # Идёт после rate-limit
```


**Проблема**: В некоторых местах rate-limit идёт ДО, в других ПОСЛЕ создания пользователя
- Непоследовательность
- В cmd_start rate-limit проверяется ДО, но в cb_toggle_platform ПОСЛЕ
**Фикс**: Унифицировать порядок

***

## 🟢 СРЕДНИЕ ПРОБЛЕМЫ (Could Fix)

### 11. **Неоптимальная обработка дубликатов платформ**
```python
platform_list = [p.strip() for p in platforms_raw.split(",")]
platform_list = list(dict.fromkeys(platform_list))
```


**Проблема**: `dict.fromkeys()` работает, но для этого есть более питонический способ
**Фикс**: Использовать `OrderedDict` или просто проверять перед добавлением

### 12. **Hardcoded строки в admin.py**
```python
await message.answer("❌ Message text cannot be empty.")  # Не переведено
```


**Проблема**: Админские сообщения не локализованы, хотя админ может быть не англоговорящим
**Фикс**: Добавить admin_* ключи в translations

### 13. **Отсутствует обработка очень старых дат**
```python
delta = (end - now).days
if delta < 0:
    return f"Expired"  # Но игра всё равно отправится!
```


**Проблема**: Если дата истекла, игра всё равно отправится пользователям
**Фикс**: Добавить фильтр в `check_new_games()` для пропуска истёкших

### 14. **Нет проверки на пустой title**
```python
title=games_by_external_id[external_id].get("title", "Unknown")
```


**Проблема**: Если `title=""` (пустая строка), это не то же что `None`
**Фикс**: `title=games_by_external_id[external_id].get("title") or "Unknown"`

### 15. **Circuit breaker не логирует recovery**
```python
if elapsed >= self.recovery_timeout_seconds:
    self._opened_at = None
    self._failure_count = 0
    return False  # Нет логирования
```


**Проблема**: Когда circuit breaker закрывается, это не логируется
**Фикс**: Добавить `logger.info("Circuit breaker recovered")`

### 16. **Отсутствует rate limiting для callback queries**
```python
@router.callback_query(F.data == DONE_CB)
async def cb_done_settings(callback: CallbackQuery) -> None:
    # Нет rate-limit проверки!
```


**Проблема**: Пользователь может спамить callback'ами без ограничений
**Фикс**: Добавить rate-limit для всех callback handlers

### 17. **Scheduler не graceful shutdown**
```python
finally:
    scheduler.shutdown(wait=False)  # wait=False = резкая остановка
```


**Проблема**: Если во время shutdown идёт broadcast, он оборвётся
**Фикс**: `wait=True` с timeout

### 18. **Неоптимальный SELECT в broadcast**
```python
result = await session.execute(
    select(User.tg_id, User.language, User.pref_steam, ...)
    .where(User.is_active.is_(True))
)
```


**Проблема**: Нет LIMIT, если пользователей 100k, всё загрузится в память
**Фикс**: Использовать `yield_per()` для streaming или батчинг

### 19. **Отсутствует handling для пустого end_date_raw**
```python
end_date_raw = game.get("end_date", "")
end_date = _format_end_date(end_date_raw) if end_date_raw else unknown
```


**Проблема**: Если `end_date=""` (пустая строка), `if end_date_raw` вернёт `False`, но функция всё равно может быть вызвана
**Фикс**: `if end_date_raw and end_date_raw != "N/A"`

### 20. **Отсутствует обработка invalid callback data в других handlers**
```python
@router.callback_query(F.data == DONE_CB)
async def cb_done_settings(callback: CallbackQuery) -> None:
    # Нет валидации callback.data!
```


**Проблема**: Валидация есть только в toggle/language handlers
**Фикс**: Добавить middleware для валидации всех callback'ов

***

## 🔵 МЕЛКИЕ НЕДОЧЁТЫ (Nice to Have)

### 21. **Inconsistent emoji usage**
```python
"🎮 Steam"  # В broadcaster.py
"Steam"     # В settings кнопках
```


**Проблема**: Эмодзи добавляются только в уведомлениях, но не в кнопках настроек
**Фикс**: Добавить эмодзи в `settings_btn_*` для консистентности

### 22. **Отсутствует user-agent для API запросов**
```python
async with aiohttp.ClientSession(timeout=API_TIMEOUT) as session:
```


**Проблема**: Нет User-Agent, некоторые API могут блокировать
**Фикс**: Добавить `headers={"User-Agent": "OFKA-Bot/1.0"}`

### 23. **Магические числа в коде**
```python
MAX_DESCRIPTION_LENGTH = 800  # Почему 800?
SEND_DELAY = 0.05  # Почему 0.05?
```


**Проблема**: Нет комментариев, почему выбраны эти значения
**Фикс**: Добавить комментарии с обоснованием

### 24. **Отсутствует rollback при ошибке commit**
```python
await session.commit()  # Если упадёт, session не закроется корректно
```


**Проблема**: Нет обработки ошибок при commit
**Фикс**: Обернуть в try-except с rollback

### 25. **Неинформативный logging в некоторых местах**
```python
logger.info("User {tg_id} started the bot", tg_id=tg_id)
```


**Проблема**: Не логируется, был ли это новый пользователь или возврат
**Фикс**: Добавить больше контекста

### 26. **Отсутствует проверка на пустой games список в broadcast**
```python
for game in new_games:
    await broadcast_game(bot, game)  # Нет проверки, что game валидный
```


**Проблема**: Если game не содержит обязательных полей, broadcast упадёт
**Фикс**: Валидировать game перед broadcast

### 27. **Hardcoded timezone**
```python
scheduler = AsyncIOScheduler(timezone="UTC")
```


**Проблема**: Если нужен другой timezone, придётся менять код
**Фикс**: Вынести в config

### 28. **Отсутствует health check endpoint**
**Проблема**: Нет способа проверить, жив ли бот, без отправки сообщений
**Фикс**: Добавить HTTP endpoint для мониторинга

### 29. **Нет метрик и аналитики**
**Проблема**: Невозможно отследить:
- Сколько пользователей отписалось за день
- Какие платформы популярнее
- Средний CTR на кнопку "Claim Game"
**Фикс**: Добавить Prometheus metrics или логирование в структурированном формате

### 30. **Отсутствует механизм graceful degradation**
**Проблема**: Если БД недоступна, бот полностью упадёт
**Фикс**: Добавить retry logic для DB connections

*

### Приоритетный список для фикса:

**Немедленно (crash bugs):**
1. Fix callback.message.answer() после delete
2. Fix race condition в rate_limit
3. Fix caption overflow
4. Fix утечку памяти в _pending_broadcast
5. Fix SQLite default conflicts

**Важно (logic/UX):**
6. Различать первый и повторный /start
7. Fix парсинг дат с локалями
8. Fix partial match платформ
9. Валидация BOT_TOKEN
10. Унифицировать rate-limit порядок

**Остальное** можно делать постепенно.

