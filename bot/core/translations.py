"""All bot text localised into 4 languages."""

from __future__ import annotations

from typing import Any

# Supported language codes
LANGUAGES = ("ru", "uk", "en", "de")
DEFAULT_LANG = "en"

# Map code → display label (used in the picker)
LANG_LABELS: dict[str, str] = {
    "ru": "🇷🇺 Русский",
    "uk": "🇺🇦 Українська",
    "en": "🇬🇧 English",
    "de": "🇩🇪 Deutsch",
}

# ── All translatable strings keyed by (key, lang) ────────────────────────

_TEXTS: dict[str, dict[str, str]] = {
    "pick_language": {
        "ru": "🌍 Выберите язык:",
        "uk": "🌍 Оберіть мову:",
        "en": "🌍 Choose your language:",
        "de": "🌍 Wähle deine Sprache:",
    },
    "language_set": {
        "ru": "✅ Язык установлен: <b>Русский</b>",
        "uk": "✅ Мову встановлено: <b>Українська</b>",
        "en": "✅ Language set: <b>English</b>",
        "de": "✅ Sprache eingestellt: <b>Deutsch</b>",
    },
    "resubscribed": {
        "ru": "👋 Рады видеть вас снова!\n\n🔔 <i>Уведомления о раздачах успешно возобновлены.</i>",
        "uk": "👋 Раді бачити вас знову!\n\n🔔 <i>Сповіщення про роздачі успішно відновлено.</i>",
        "en": "👋 Glad to see you again!\n\n🔔 <i>Giveaway notifications have been successfully resumed.</i>",
        "de": "👋 Schön, dich wiederzusehen!\n\n🔔 <i>Die Giveaway-Benachrichtigungen wurden erfolgreich fortgesetzt.</i>",
    },
    "start": {
        "ru": (
            "👋 <b>Добро пожаловать!</b>\n\n"
            "Я буду уведомлять тебя, когда появляется новая "
            "<b>100% бесплатная игра</b> (навсегда) в <b>Steam</b>, "
            "<b>Epic Games Store</b> или <b>GOG</b>.\n\n"
            "Ничего делать не нужно — просто жди сообщений.\n\n"
            "Команды: /help, /settings"
        ),
        "uk": (
            "👋 <b>Ласкаво просимо!</b>\n\n"
            "Я повідомлятиму тебе, коли з'являється нова "
            "<b>100% безкоштовна гра</b> (назавжди) у <b>Steam</b>, "
            "<b>Epic Games Store</b> або <b>GOG</b>.\n\n"
            "Нічого робити не потрібно — просто чекай повідомлень.\n\n"
            "Команди: /help, /settings"
        ),
        "en": (
            "👋 <b>Welcome!</b>\n\n"
            "I will notify you whenever a new <b>100% free game</b> "
            "(free to keep forever) appears on <b>Steam</b>, "
            "<b>Epic Games Store</b>, or <b>GOG</b>.\n\n"
            "You don't need to do anything — just keep this chat "
            "and I'll message you when a new giveaway drops.\n\n"
            "Commands: /help, /settings"
        ),
        "de": (
            "👋 <b>Willkommen!</b>\n\n"
            "Ich benachrichtige dich, sobald ein neues "
            "<b>100% kostenloses Spiel</b> (dauerhaft) auf <b>Steam</b>, "
            "<b>Epic Games Store</b> oder <b>GOG</b> verfügbar ist.\n\n"
            "Du musst nichts tun — warte einfach auf Nachrichten.\n\n"
            "Befehle: /help, /settings"
        ),
    },
    "help": {
        "ru": (
            "ℹ️ <b>Как это работает</b>\n\n"
            "Каждые 15 минут я проверяю GamerPower API на наличие "
            "бесплатных PC-игр в Steam, Epic Games Store и GOG.\n\n"
            "Когда появляется новая <b>бесплатная навсегда</b> игра — "
            "ты получишь уведомление со ссылкой.\n\n"
            "<b>Команды:</b>\n"
            "/start — Подписаться\n"
            "/settings — Язык и платформы\n"
            "/help — Это сообщение"
        ),
        "uk": (
            "ℹ️ <b>Як це працює</b>\n\n"
            "Кожні 15 хвилин я перевіряю GamerPower API на наявність "
            "безкоштовних PC-ігор у Steam, Epic Games Store та GOG.\n\n"
            "Коли з'являється нова <b>безкоштовна назавжди</b> гра — "
            "ти отримаєш повідомлення з посиланням.\n\n"
            "<b>Команди:</b>\n"
            "/start — Підписатися\n"
            "/settings — Мова та платформи\n"
            "/help — Це повідомлення"
        ),
        "en": (
            "ℹ️ <b>How it works</b>\n\n"
            "Every 15 minutes I check the GamerPower API for new "
            "PC game giveaways on Steam, Epic Games Store, and GOG.\n\n"
            "When a new <b>free-to-keep</b> game appears, I send you "
            "a notification with a direct link to claim it.\n\n"
            "<b>Commands:</b>\n"
            "/start — Subscribe\n"
            "/settings — Language and platforms\n"
            "/help — This message"
        ),
        "de": (
            "ℹ️ <b>So funktioniert's</b>\n\n"
            "Alle 15 Minuten prüfe ich die GamerPower API auf neue "
            "kostenlose PC-Spiele bei Steam, Epic Games Store und GOG.\n\n"
            "Wenn ein neues <b>dauerhaft kostenloses</b> Spiel erscheint, "
            "sende ich dir eine Benachrichtigung mit Link.\n\n"
            "<b>Befehle:</b>\n"
            "/start — Abonnieren\n"
            "/settings — Sprache und Plattformen\n"
            "/help — Diese Nachricht"
        ),
    },
    "subscription_confirmed": {
        "ru": "✅ <b>Вы подписаны!</b>\n\nТеперь вы будете получать уведомления о новых бесплатных играх.",
        "uk": "✅ <b>Ви підписані!</b>\n\nТепер ви будете отримувати сповіщення про нові безкоштовні ігри.",
        "en": "✅ <b>You're subscribed!</b>\n\nYou will now receive notifications about new free games.",
        "de": "✅ <b>Du bist abonniert!</b>\n\nDu erhältst jetzt Benachrichtigungen über neue kostenlose Spiele.",
    },
    "unsubscribe_confirmed": {
        "ru": "👋 Уведомления отключены. Вы можете подписаться снова командой /start",
        "uk": "👋 Сповіщення вимкнено. Ви можете підписатися знову командою /start",
        "en": "👋 Notifications disabled. You can subscribe again with /start",
        "de": "👋 Benachrichtigungen deaktiviert. Du kannst dich jederzeit mit /start erneut abonnieren.",
    },
    "settings_hint": {
        "ru": "⚙️ Открой /settings, чтобы выбрать язык и платформы уведомлений.",
        "uk": "⚙️ Відкрий /settings, щоб обрати мову та платформи сповіщень.",
        "en": "⚙️ Open /settings to choose language and notification platforms.",
        "de": "⚙️ Öffne /settings, um Sprache und Benachrichtigungs-Plattformen zu wählen.",
    },
    "settings_title": {
        "ru": "⚙️ <b>Настройки</b>\nВыбери, о каких платформах присылать уведомления:\n\n💡 <i>«Другие» = Amazon, Itch.io, Ubisoft, Origin, GOG+ и прочее</i>",
        "uk": "⚙️ <b>Налаштування</b>\nОбери, про які платформи надсилати сповіщення:\n\n💡 <i>«Інші» = Amazon, Itch.io, Ubisoft, Origin, GOG+ та інше</i>",
        "en": "⚙️ <b>Settings</b>\nChoose which platforms to notify you about:\n\n💡 <i>«Other» = Amazon, Itch.io, Ubisoft, Origin, GOG+, and more</i>",
        "de": "⚙️ <b>Einstellungen</b>\nWähle, über welche Plattformen du Benachrichtigungen erhalten willst:\n\n💡 <i>«Andere» = Amazon, Itch.io, Ubisoft, Origin, GOG+ und mehr</i>",
    },
    "settings_language_title": {
        "ru": "🌍 <b>Выбор языка</b>",
        "uk": "🌍 <b>Вибір мови</b>",
        "en": "🌍 <b>Choose language</b>",
        "de": "🌍 <b>Sprache wählen</b>",
    },
    "settings_btn_steam": {
        "ru": "Steam",
        "uk": "Steam",
        "en": "Steam",
        "de": "Steam",
    },
    "settings_btn_epic": {
        "ru": "Epic",
        "uk": "Epic",
        "en": "Epic",
        "de": "Epic",
    },
    "settings_btn_gog": {
        "ru": "GOG",
        "uk": "GOG",
        "en": "GOG",
        "de": "GOG",
    },
    "settings_btn_other": {
        "ru": "Другие",
        "uk": "Інші",
        "en": "Other",
        "de": "Andere",
    },
    "settings_btn_language": {
        "ru": "Язык",
        "uk": "Мова",
        "en": "Language",
        "de": "Sprache",
    },
    "settings_saved": {
        "ru": "Сохранено",
        "uk": "Збережено",
        "en": "Saved",
        "de": "Gespeichert",
    },
    "game_caption": {
        "ru": (
            "🎮 <b>{title}</b>\n"
            "💰 Цена: <s>{worth}</s> → <b>БЕСПЛАТНО</b>\n"
            "🏪 Платформа: {platforms}\n"
            "⏳ До: {end_date}{description_section}"
        ),
        "uk": (
            "🎮 <b>{title}</b>\n"
            "💰 Ціна: <s>{worth}</s> → <b>БЕЗКОШТОВНО</b>\n"
            "🏪 Платформа: {platforms}\n"
            "⏳ До: {end_date}{description_section}"
        ),
        "en": (
            "🎮 <b>{title}</b>\n"
            "💰 Price: <s>{worth}</s> → <b>FREE</b>\n"
            "🏪 Platform: {platforms}\n"
            "⏳ Ends: {end_date}{description_section}"
        ),
        "de": (
            "🎮 <b>{title}</b>\n"
            "💰 Preis: <s>{worth}</s> → <b>KOSTENLOS</b>\n"
            "🏪 Plattform: {platforms}\n"
            "⏳ Bis: {end_date}{description_section}"
        ),
    },
    "rate_limit_message": {
        "ru": "⏳ Подождите немного перед следующим действием.",
        "uk": "⏳ Почекайте трохи перед наступною дією.",
        "en": "⏳ Please wait a moment before the next action.",
        "de": "⏳ Bitte warten Sie einen Moment vor der nächsten Aktion.",
    },
    "unknown_value": {
        "ru": "Неизвестно",
        "uk": "Невідомо",
        "en": "Unknown",
        "de": "Unbekannt",
    },
    "date_today": {
        "ru": "Сегодня",
        "uk": "Сьогодні",
        "en": "Today",
        "de": "Heute",
    },
    "date_last_day": {
        "ru": "🔥 Сегодня последний день!",
        "uk": "🔥 Сьогодні останній день!",
        "en": "🔥 Today is the last day!",
        "de": "🔥 Heute ist der letzte Tag!",
    },
    "date_tomorrow": {
        "ru": "Завтра",
        "uk": "Завтра",
        "en": "Tomorrow",
        "de": "Morgen",
    },
    "date_days_left": {
        "ru": "дней осталось",
        "uk": "днів залишилось",
        "en": "days left",
        "de": "Tage verbleibend",
    },
    "btn_games": {
        "ru": "🎮 Игры",
        "uk": "🎮 Ігри",
        "en": "🎮 Games",
        "de": "🎮 Spiele",
    },
    "btn_stats": {
        "ru": "📊 Статистика",
        "uk": "📊 Статистика",
        "en": "📊 Stats",
        "de": "📊 Statistik",
    },
    "btn_settings": {
        "ru": "⚙️ Настройки",
        "uk": "⚙️ Налаштування",
        "en": "⚙️ Settings",
        "de": "⚙️ Einstellungen",
    },
    "btn_help": {
        "ru": "ℹ️ Помощь",
        "uk": "ℹ️ Довідка",
        "en": "ℹ️ Help",
        "de": "ℹ️ Hilfe",
    },
    "btn_claimed": {
        "ru": "✅ Получил",
        "uk": "✅ Отримав",
        "en": "✅ Claimed",
        "de": "✅ Erhalten",
    },
    "btn_skip": {
        "ru": "⏭ Пропустить",
        "uk": "⏭ Пропустити",
        "en": "⏭ Skip",
        "de": "⏭ Überspringen",
    },
    "btn_remind": {
        "ru": "⏰ Напомнить завтра",
        "uk": "⏰ Нагадати завтра",
        "en": "⏰ Remind tomorrow",
        "de": "⏰ Morgen erinnern",
    },
    "btn_claim_game": {
        "ru": "🎁 Забрать игру",
        "uk": "🎁 Забрати гру",
        "en": "🎁 Claim Game",
        "de": "🎁 Spiel holen",
    },
    "toast_claimed": {
        "ru": "✅ Отмечено как полученное!",
        "uk": "✅ Позначено як отримане!",
        "en": "✅ Marked as claimed!",
        "de": "✅ Als erhalten markiert!",
    },
    "toast_skipped": {
        "ru": "⏭ Пропущено",
        "uk": "⏭ Пропущено",
        "en": "⏭ Skipped",
        "de": "⏭ Übersprungen",
    },
    "toast_remind_set": {
        "ru": "⏰ Напомним завтра!",
        "uk": "⏰ Нагадаємо завтра!",
        "en": "⏰ We'll remind you tomorrow!",
        "de": "⏰ Wir erinnern dich morgen!",
    },
    "toast_already_marked": {
        "ru": "Уже отмечено ✅",
        "uk": "Вже позначено ✅",
        "en": "Already marked ✅",
        "de": "Bereits markiert ✅",
    },
    "no_active_games": {
        "ru": "😴 Сейчас активных раздач нет. Мы уведомим тебя, когда появятся!",
        "uk": "😴 Зараз активних роздач немає. Ми повідомимо тебе, коли з'являться!",
        "en": "😴 No active giveaways right now. We'll notify you when new ones appear!",
        "de": "😴 Derzeit gibt es keine aktiven Giveaways. Wir benachrichtigen dich, sobald neue erscheinen!",
    },
    "all_games_claimed": {
        "ru": "🎉 Ты уже получил все текущие раздачи!",
        "uk": "🎉 Ти вже отримав усі поточні роздачі!",
        "en": "🎉 You've already claimed all current giveaways!",
        "de": "🎉 Du hast bereits alle aktuellen Giveaways erhalten!",
    },
    "loading_games": {
        "ru": "⏳ Ищем активные раздачи...",
        "uk": "⏳ Шукаємо активні роздачі...",
        "en": "⏳ Looking for active giveaways...",
        "de": "⏳ Suche nach aktiven Giveaways...",
    },
    "games_showing_n": {
        "ru": "Показываю {shown} из {total} раздач",
        "uk": "Показую {shown} із {total} роздач",
        "en": "Showing {shown} of {total} giveaways",
        "de": "Zeige {shown} von {total} Giveaways",
    },
    "reminder_message": {
        "ru": "⏰ <b>Напоминание!</b>\n\nТы ещё не забрал бесплатную игру:\n🎮 <b>{title}</b>\n\nНе упусти её!",
        "uk": "⏰ <b>Нагадування!</b>\n\nТи ще не забрав безкоштовну гру:\n🎮 <b>{title}</b>\n\nНе проґав її!",
        "en": "⏰ <b>Reminder!</b>\n\nYou haven't claimed this free game yet:\n🎮 <b>{title}</b>\n\nDon't miss it!",
        "de": "⏰ <b>Erinnerung!</b>\n\nDu hast dieses kostenlose Spiel noch nicht geholt:\n🎮 <b>{title}</b>\n\nVerpass es nicht!",
    },
    "user_stats": {
        "ru": "📊 <b>Твоя статистика</b>\n\n✅ Получено игр: <b>{claimed}</b>\n⏭ Пропущено: <b>{skipped}</b>\n💰 Сэкономлено: <b>{saved}</b>",
        "uk": "📊 <b>Твоя статистика</b>\n\n✅ Отримано ігор: <b>{claimed}</b>\n⏭ Пропущено: <b>{skipped}</b>\n💰 Заощаджено: <b>{saved}</b>",
        "en": "📊 <b>Your Stats</b>\n\n✅ Games claimed: <b>{claimed}</b>\n⏭ Skipped: <b>{skipped}</b>\n💰 Saved: <b>{saved}</b>",
        "de": "📊 <b>Deine Statistik</b>\n\n✅ Erhaltene Spiele: <b>{claimed}</b>\n⏭ Übersprungen: <b>{skipped}</b>\n💰 Gespart: <b>{saved}</b>",
    },
    "claim_button": {
        "ru": "🎁 Забрать игру",
        "uk": "🎁 Забрати гру",
        "en": "🎁 Claim Game",
        "de": "🎁 Spiel holen",
    },
    "btn_back": {
        "ru": "⬅️ Назад",
        "uk": "⬅️ Назад",
        "en": "⬅️ Back",
        "de": "⬅️ Zurück",
    },
    "btn_done": {
        "ru": "✅ Готово",
        "uk": "✅ Готово",
        "en": "✅ Done",
        "de": "✅ Fertig",
    },
    "btn_unsubscribe": {
        "ru": "🔕 Отключить уведомления",
        "uk": "🔕 Вимкнути сповіщення",
        "en": "🔕 Disable notifications",
        "de": "🔕 Benachrichtigungen deaktivieren",
    },
    "platform_all_disabled": {
        "ru": "⚠️ Включите хотя бы одну платформу!",
        "uk": "⚠️ Увімкніть принаймні одну платформу!",
        "en": "⚠️ Enable at least one platform!",
        "de": "⚠️ Aktivieren Sie mindestens eine Plattform!",
    },
    "invalid_request": {
        "ru": "⚠️ Некорректный запрос. Попробуйте ещё раз.",
        "uk": "⚠️ Некоректний запит. Спробуйте ще раз.",
        "en": "⚠️ Invalid request. Please try again.",
        "de": "⚠️ Ungültige Anfrage. Bitte versuche es erneut.",
    },
    "admin_broadcast_empty": {
        "ru": "❌ Текст сообщения не может быть пустым.",
        "uk": "❌ Текст повідомлення не може бути порожнім.",
        "en": "❌ Message text cannot be empty.",
        "de": "❌ Nachrichtentext darf nicht leer sein.",
    },
    "admin_broadcast_usage": {
        "ru": "❌ Использование: /broadcast <текст>",
        "uk": "❌ Використання: /broadcast <текст>",
        "en": "❌ Usage: /broadcast <text>",
        "de": "❌ Verwendung: /broadcast <Text>",
    },
    "admin_broadcast_too_long": {
        "ru": "❌ Сообщение слишком длинное ({length} символов, макс. {max_length}).",
        "uk": "❌ Повідомлення занадто довге ({length} символів, макс. {max_length}).",
        "en": "❌ Message too long ({length} chars, max {max_length}).",
        "de": "❌ Nachricht zu lang ({length} Zeichen, max. {max_length}).",
    },
    "admin_broadcast_confirm": {
        "ru": "📢 <b>Подтвердите рассылку всем активным пользователям:</b>\n\n{message}",
        "uk": "📢 <b>Підтвердіть розсилку всім активним користувачам:</b>\n\n{message}",
        "en": "📢 <b>Confirm broadcast to all active users:</b>\n\n{message}",
        "de": "📢 <b>Broadcast an alle aktiven Benutzer bestätigen:</b>\n\n{message}",
    },
    "admin_unauthorized": {
        "ru": "❌ Неавторизовано",
        "uk": "❌ Неавторизовано",
        "en": "❌ Unauthorized",
        "de": "❌ Nicht autorisiert",
    },
    "admin_no_pending": {
        "ru": "❌ Нет ожидающей рассылки",
        "uk": "❌ Немає очікуваної розсилки",
        "en": "❌ No pending broadcast",
        "de": "❌ Kein ausstehender Broadcast",
    },
    "admin_broadcast_expired": {
        "ru": "❌ Запрос рассылки истек. Попробуйте снова.",
        "uk": "❌ Запит розсилки минув. Спробуйте знову.",
        "en": "❌ Broadcast request expired. Please try again.",
        "de": "❌ Broadcast-Anfrage abgelaufen. Bitte erneut versuchen.",
    },
    "admin_broadcasting": {
        "ru": "📤 Отправка рассылки…",
        "uk": "📤 Відправка розсилки…",
        "en": "📤 Broadcasting…",
        "de": "📤 Wird gesendet…",
    },
    "admin_broadcast_progress": {
        "ru": "📤 Отправляю… {done}/{total}",
        "uk": "📤 Відправляю… {done}/{total}",
        "en": "📤 Sending… {done}/{total}",
        "de": "📤 Sende… {done}/{total}",
    },
    "admin_broadcast_done": {
        "ru": "✅ Рассылка завершена.\nДоставлено: <b>{success}</b> | Не удалось: <b>{failed}</b>",
        "uk": "✅ Розсилка завершена.\nДоставлено: <b>{success}</b> | Не вдалось: <b>{failed}</b>",
        "en": "✅ Broadcast done.\nDelivered: <b>{success}</b> | Failed: <b>{failed}</b>",
        "de": "✅ Broadcast abgeschlossen.\nZugestellt: <b>{success}</b> | Fehlgeschlagen: <b>{failed}</b>",
    },
    "admin_broadcast_cancelled": {
        "ru": "Рассылка отменена.",
        "uk": "Розсилку скасовано.",
        "en": "Broadcast cancelled.",
        "de": "Broadcast abgebrochen.",
    },
    "admin_backfill_usage": {
        "ru": "❌ Использование: /backfill [N]\nN — сколько последних раздач проверить (по умолчанию {default}, макс. {max}).",
        "uk": "❌ Використання: /backfill [N]\nN — скільки останніх роздач перевірити (за замовчуванням {default}, макс. {max}).",
        "en": "❌ Usage: /backfill [N]\nN — how many recent giveaways to check (default {default}, max {max}).",
        "de": "❌ Verwendung: /backfill [N]\nN — wie viele aktuelle Giveaways geprüft werden (Standard {default}, max {max}).",
    },
    "admin_backfill_done": {
        "ru": "🔄 Backfill завершён.\nПроверено: <b>{fetched}</b>\nУже в БД: <b>{already_known}</b>\nРазослано: <b>{broadcasted}</b>",
        "uk": "🔄 Backfill завершено.\nПеревірено: <b>{fetched}</b>\nВже в БД: <b>{already_known}</b>\nРозіслано: <b>{broadcasted}</b>",
        "en": "🔄 Backfill done.\nChecked: <b>{fetched}</b>\nAlready in DB: <b>{already_known}</b>\nBroadcasted: <b>{broadcasted}</b>",
        "de": "🔄 Backfill abgeschlossen.\nGeprüft: <b>{fetched}</b>\nBereits in DB: <b>{already_known}</b>\nGesendet: <b>{broadcasted}</b>",
    },
    "admin_backfill_empty": {
        "ru": "😴 GamerPower сейчас не возвращает раздач.",
        "uk": "😴 GamerPower зараз не повертає роздач.",
        "en": "😴 GamerPower returned no giveaways right now.",
        "de": "😴 GamerPower liefert aktuell keine Giveaways.",
    },
    "admin_backfill_throttled": {
        "ru": "⏳ Подождите {seconds}s между действиями.",
        "uk": "⏳ Зачекайте {seconds}s між діями.",
        "en": "⏳ Wait {seconds}s between actions.",
        "de": "⏳ Bitte {seconds}s zwischen Aktionen warten.",
    },
    "admin_action_throttled": {
        "ru": "⏳ Подождите {seconds}s между действиями.",
        "uk": "⏳ Зачекайте {seconds}s між діями.",
        "en": "⏳ Wait {seconds}s between actions.",
        "de": "⏳ Bitte {seconds}s zwischen Aktionen warten.",
    },
    "admin_operation_failed": {
        "ru": "❌ Операция завершилась с ошибкой. Проверьте логи и попробуйте снова.",
        "uk": "❌ Операція завершилась з помилкою. Перевірте логи та спробуйте ще раз.",
        "en": "❌ Operation failed. Check logs and try again.",
        "de": "❌ Vorgang fehlgeschlagen. Prüfe die Logs und versuche es erneut.",
    },
}


def t(key: str, lang: str | None = None, **kwargs: Any) -> str:
    """Get a translated string by key and language code.

    Falls back to English if the key or language is missing.
    Supports str.format() kwargs for templates like game_caption.
    """
    lang = lang if lang in LANGUAGES else DEFAULT_LANG
    texts = _TEXTS.get(key, {})
    text = texts.get(lang, texts.get(DEFAULT_LANG, key))
    if kwargs:
        return text.format(**kwargs)
    return text
