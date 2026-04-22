# HH Job Hunter Agent

Автономный агент для поиска работы: сканирует hh.ru, оценивает каждую вакансию через LLM, генерирует персонализированное сопроводительное письмо и отправляет карточку в Telegram. Отклик — одной кнопкой.

> **Примечание:** HH.ru закрыл API для частных соискателей. Агент работает через браузерную автоматизацию (Playwright) — логинится под вашим аккаунтом и выполняет отклики так же, как это делает обычный пользователь.

## Как работает

```
hh.ru (парсинг, 2×/день)
    → фильтрация (удалёнка, опыт ≤ 1–3 года)
    → LLM scoring (0–100)
    → генерация сопроводительного письма
    → Telegram-карточка
    → [✅ Откликнуться] → Playwright отправляет отклик
```

## Стек

| Слой | Технология |
|---|---|
| Парсинг и автоматизация | Playwright (Chromium) |
| Telegram-бот | aiogram 3 |
| LLM scoring | Qwen3 235B via OpenRouter |
| Генерация письма | Gemini 2.5 Pro via OpenRouter |
| Хранилище | SQLite (aiosqlite) |
| Планировщик | APScheduler (09:00 и 18:00 МСК) |

## Быстрый старт

### 1. Установка

```bash
git clone <repo>
cd hh-job-agent

py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\playwright install chromium
```

### 2. Конфиг (`config.py`)

```python
TELEGRAM_TOKEN   = "токен от @BotFather"
TELEGRAM_CHAT_ID = твой_chat_id          # узнай через @userinfobot
HH_LOGIN         = "твой@email.ru"       # логин на hh.ru
HH_PASSWORD      = "твой_пароль"
OPENROUTER_API_KEY = "sk-or-..."
```

### 3. Запуск

```bash
.venv\Scripts\python main.py
```

При первом запуске агент авторизуется на hh.ru и сохранит сессию в `hh_cookies.json` — повторный вход не потребуется до истечения сессии.

## Команды бота

| Команда | Описание |
|---|---|
| `/scan` | Запустить сканирование прямо сейчас |
| `/stats` | Статистика: найдено / откликнулся / пропустил |
| `/setresume <id>` | Установить ID резюме (если несколько резюме на HH) |

## Фильтры поиска

- **Формат:** только удалённая работа (`schedule=remote`)
- **Опыт:** без опыта и до 3 лет (`noExperience`, `between1And3`)
- **Ключевые слова:** AI Engineer, ML Engineer, Data Analyst, Python разработчик, aiogram, Telegram bot и другие (настраивается в `config.py`)
- **Порог отклика:** score ≥ 72/100 по оценке LLM

## Формат уведомления в Telegram

```
🔥 Совпадение: 91/100

💼 Python AI Developer — TechCorp
🏢 ТехКорп
💰 от 150 000 ₽
📋 от 1 года • Удалённая работа
🔗 Открыть на HH

Анализ: Вакансия хорошо совпадает со стеком — требуют Python,
aiogram, OpenRouter. Опыт с LLM-роутингом и Telegram-агентами
напрямую релевантен задачам позиции.

━━━━━━━━━━━━━━━━━━━
📝 Сопроводительное письмо:

[персонализированный текст под эту вакансию...]

[✅ Откликнуться]  [❌ Пропустить]
[✏️ Редактировать письмо]
```

## Структура проекта

```
hh-job-agent/
├── main.py              # точка входа, планировщик
├── config.py            # все настройки
├── requirements.txt
├── hh_cookies.json      # сессия HH (создаётся автоматически)
├── bot/
│   ├── telegram_bot.py  # aiogram 3: команды и кнопки
│   └── notifications.py # форматирование карточки вакансии
├── hh/
│   ├── client.py        # Playwright: парсинг + отклик
│   └── scanner.py       # оркестратор сканирования
├── ai/
│   ├── scorer.py        # LLM оценка совпадения (0–100)
│   └── cover_letter.py  # генерация сопроводительного письма
└── db/
    └── storage.py       # SQLite: вакансии, статусы
```

## Деплой на VPS

```bash
sudo nano /etc/systemd/system/job-agent.service
```

```ini
[Unit]
Description=HH Job Hunter Agent
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/hh-job-agent
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable job-agent
sudo systemctl start job-agent
sudo journalctl -u job-agent -f
```

> На VPS нужен Chromium: `playwright install chromium --with-deps`
