"""
ai/cover_letter.py — генерация сопроводительного письма под конкретную вакансию
"""

import httpx
import logging
import re
from config import config

log = logging.getLogger(__name__)

COVER_SYSTEM = """Ты — карьерный коуч. Пишешь сопроводительные письма на русском языке.

Требования к письму:
- Длина: 150-200 слов
- Тон: профессиональный, конкретный, без воды
- Структура: 1) зацепка релевантным опытом под ЭТУ вакансию, 2) 2-3 конкретных достижения из проектов, 3) почему эта компания, 4) краткий call-to-action
- НЕ начинай с "Здравствуйте" или "Уважаемые"
- Упоминай конкретные технологии из вакансии которые есть у кандидата
- Пиши от первого лица"""


def _extract_text_from_html(html: str) -> str:
    clean = re.sub(r'<[^>]+>', ' ', html or '')
    return re.sub(r'\s+', ' ', clean).strip()[:2000]


async def generate_cover_letter(detail: dict, score_analysis: str = "") -> str:
    """Генерирует персонализированное сопроводительное письмо"""

    description = _extract_text_from_html(detail.get("description", ""))

    prompt = f"""ПРОФИЛЬ КАНДИДАТА:
{config.CANDIDATE_PROFILE}

ВАКАНСИЯ: {detail.get('name', '')}
КОМПАНИЯ: {detail.get('employer', {}).get('name', '')}
ОПИСАНИЕ: {description}

АНАЛИЗ СОВПАДЕНИЯ: {score_analysis}

Напиши сопроводительное письмо."""

    try:
        async with httpx.AsyncClient(timeout=40) as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.COVER_LETTER_MODEL,
                    "max_tokens": 600,
                    "messages": [
                        {"role": "system", "content": COVER_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                }
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()

    except Exception as e:
        log.error(f"Cover letter generation error: {e}")
        return _fallback_cover_letter(detail)


def _fallback_cover_letter(detail: dict) -> str:
    """Шаблонное письмо если LLM недоступен"""
    position = detail.get("name", "эту позицию")
    company = detail.get("employer", {}).get("name", "вашу компанию")
    return f"""Меня заинтересовала позиция {position} в {company}.

За последний год я построил несколько production AI-систем: мультимодельный Telegram-агент с роутингом запросов между Qwen3 235B и Gemini 2.5 Pro, голосовой агент для фильтрации звонков на базе Vapi + ElevenLabs, и агента для анализа юридических документов с поддержкой PDF/DOCX.

Стек: Python, aiogram 3, OpenRouter, FastAPI, LightGBM, PyTorch, Linux/VPS.

Готов обсудить задачи подробнее. Портфолио: nebula387.github.io/portfolio"""
