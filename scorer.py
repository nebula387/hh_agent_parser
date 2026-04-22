"""
ai/scorer.py — LLM оценивает совпадение вакансии с профилем кандидата
"""

import httpx
import json
import logging
import re
from config import config

log = logging.getLogger(__name__)

SCORER_SYSTEM = """Ты — рекрутинговый аналитик. Оцени совпадение вакансии с профилем кандидата.

Верни ТОЛЬКО JSON, без markdown, без пояснений:
{
  "score": <0-100>,
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill3"],
  "highlights": "2-3 предложения почему эта вакансия подходит или не подходит",
  "remote_ok": true/false,
  "seniority_match": "junior/mid/senior/lead — совпадает ли уровень"
}"""


def _extract_text_from_html(html: str) -> str:
    """Грубое извлечение текста из HTML описания"""
    clean = re.sub(r'<[^>]+>', ' ', html or '')
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean[:3000]  # лимит токенов


async def score_vacancy(detail: dict) -> tuple[int, str]:
    """
    Возвращает (score: int, analysis: str)
    """
    description_html = detail.get("description", "")
    description = _extract_text_from_html(description_html)

    vacancy_summary = f"""
ВАКАНСИЯ: {detail.get('name', '')}
КОМПАНИЯ: {detail.get('employer', {}).get('name', '')}
ТРЕБОВАНИЯ/ОПИСАНИЕ: {description}
ГРАФИК: {detail.get('schedule', {}).get('name', '')}
ОПЫТ: {detail.get('experience', {}).get('name', '')}
"""

    prompt = f"""ПРОФИЛЬ КАНДИДАТА:
{config.CANDIDATE_PROFILE}

{vacancy_summary}

Оцени совпадение от 0 до 100."""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.SCORER_MODEL,
                    "max_tokens": 500,
                    "messages": [
                        {"role": "system", "content": SCORER_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                }
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()

            # Чистим возможные ```json фенсы
            content = re.sub(r'^```json\s*', '', content)
            content = re.sub(r'\s*```$', '', content)

            data = json.loads(content)
            score = max(0, min(100, int(data.get("score", 0))))
            analysis = data.get("highlights", "")
            return score, analysis

    except Exception as e:
        log.error(f"Scorer error: {e}")
        return 0, "Ошибка оценки"
