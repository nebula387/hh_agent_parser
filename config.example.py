"""
Конфиг агента — редактируй под себя
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    # ── Telegram ──────────────────────────────────────────────
    TELEGRAM_TOKEN: str = ""
    TELEGRAM_CHAT_ID: int =  # твой личный chat_id

    # ── HH авторизация ────────────────────────────────────────
    HH_LOGIN: str = ""           # email или телефон на HH
    HH_PASSWORD: str = ""        # пароль
    HH_RESUME_ID: str = ""       # ID резюме (опционально, если несколько резюме)

    # ── OpenRouter ────────────────────────────────────────────
    OPENROUTER_API_KEY: str = "YOUR_OPENROUTER_KEY"
    SCORER_MODEL: str = "qwen/qwen3-235b-a22b"        # для scoring
    COVER_LETTER_MODEL: str = "google/gemini-2.5-pro"  # для письма

    # ── Поиск вакансий ────────────────────────────────────────
    SEARCH_QUERIES: List[str] = field(default_factory=lambda: [
        # AI / LLM
        "AI Engineer",
        "LLM разработчик",
        "AI агент Python",
        "AI разработчик",
        # ML / Data
        "ML Engineer",
        "Machine Learning инженер",
        "Data Engineer Python",
        "Data Analyst Python",
        "Data Scientist",
        # Python / боты
        "Python разработчик aiogram",
        "Telegram bot разработчик",
        "Python backend разработчик",
        # Junior-friendly
        "Junior Python разработчик",
        "Junior AI",
        "Junior Data Analyst",
    ])
    SEARCH_AREA: int = 113       # 113 = Россия, 0 = весь мир
    SEARCH_REMOTE_ONLY: bool = True
    # noExperience = нет опыта, between1And3 = от 1 до 3 лет
    EXPERIENCE_LEVELS: List[str] = field(default_factory=lambda: [
        "noExperience",
        "between1And3",
    ])
    MIN_MATCH_SCORE: int = 72    # минимальный % совпадения для отправки
    VACANCIES_PER_QUERY: int = 50

    # ── Профиль для matching и cover letter ───────────────────
    CANDIDATE_PROFILE: str = """
Иван Снигирев — AI & Data Engineer (UTC+3, remote only, English B2)

НАВЫКИ:
- AI/Agents: LLM routing, OpenRouter, Groq Whisper, aiogram 3, Tavily, Vapi, Voice AI
- ML/Data: LightGBM, scikit-learn, PyTorch, pandas, NumPy, EDA, SQL
- Engineering: Python OOP, Node.js, FastAPI, Linux/VPS, systemd, Git
- Domain: Network security, telecom/ISP, industrial automation

ПРОЕКТЫ:
1. Pro Assistant Bot — мультимодельный Telegram-агент с роутингом (Qwen3 235B / Gemini 2.5 Pro),
   голосовой ввод Groq Whisper, поиск Tavily, деплой VPS+systemd
2. Doc Agent — агент для анализа юридических документов (PDF/DOCX/TXT),
   cross-reference с веб-поиском, auto-fallback по 5 моделям
3. ScamGuard — голосовой AI-агент фильтрации звонков (Vapi + Claude Sonnet + ElevenLabs)
4. Network Intrusion Detection — бинарная классификация трафика KDD Cup 99 (ROC-AUC ~1.00)
5. Diabetes Risk Prediction — LightGBM pipeline, ROC-AUC 0.91, оптимизация recall
6. GBC Analytics Dashboard — real-time CRM дашборд (Next.js + Supabase + RetailCRM API)

ОПЫТ:
- Сетевой инженер, ЭР-Телеком (2024–н.в.)
- Инженер АСУ ТП, Росфлотсервис (2020–2023)

ОБРАЗОВАНИЕ: Диплом аналитика данных, ТГУ, 2024

УСЛОВИЯ: только remote, фриланс или full-time
"""


config = Config()
