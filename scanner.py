"""
hh/scanner.py — оркестратор: сканирует HH, скорит, генерирует письмо, шлёт в TG
"""

import asyncio
import logging
from aiogram import Bot
from hh.client import HHClient, parse_salary
from ai.scorer import score_vacancy
from ai.cover_letter import generate_cover_letter
from db.storage import Database
from config import config

log = logging.getLogger(__name__)

_SKIP_EXPERIENCE = {"between3And6", "moreThan6"}


class JobScanner:
    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db

    async def run_scan(self):
        log.info("🔍 Начинаю сканирование HH...")
        found = 0
        sent = 0

        async with HHClient() as client:
            all_vacancies: dict[str, dict] = {}
            for query in config.SEARCH_QUERIES:
                items = await client.search_vacancies(
                    text=query,
                    area=config.SEARCH_AREA,
                    per_page=config.VACANCIES_PER_QUERY,
                )
                for item in items:
                    all_vacancies[item["id"]] = item
                await asyncio.sleep(1.0)

            log.info(f"Найдено уникальных вакансий: {len(all_vacancies)}")

            for vacancy_id, item in all_vacancies.items():
                if await self.db.is_seen(vacancy_id):
                    continue

                exp_id = (item.get("experience") or {}).get("id", "")
                if exp_id in _SKIP_EXPERIENCE:
                    continue

                schedule_id = (item.get("schedule") or {}).get("id", "")
                if config.SEARCH_REMOTE_ONLY and schedule_id not in ("remote", ""):
                    continue

                found += 1

                detail = await client.get_vacancy_detail(vacancy_id)
                if not detail:
                    continue

                score, analysis = await score_vacancy(detail)
                log.info(f"  [{score}/100] {detail.get('name')} — {detail.get('employer', {}).get('name')}")

                salary = parse_salary(detail)
                cover_letter = ""
                if score >= config.MIN_MATCH_SCORE:
                    cover_letter = await generate_cover_letter(detail, analysis)

                await self.db.save_vacancy({
                    "id": vacancy_id,
                    "title": detail.get("name", ""),
                    "company": detail.get("employer", {}).get("name", ""),
                    "url": detail.get("alternate_url", ""),
                    "score": score,
                    "cover_letter": cover_letter,
                    **salary,
                })

                if score >= config.MIN_MATCH_SCORE:
                    await self._send_to_telegram(detail, score, analysis, cover_letter, salary)
                    sent += 1
                    await asyncio.sleep(1)

        log.info(f"✅ Сканирование завершено. Новых: {found}, отправлено: {sent}")
        if found == 0:
            await self.bot.send_message(
                config.TELEGRAM_CHAT_ID,
                "🔍 Сканирование завершено — новых подходящих вакансий нет."
            )

    async def _send_to_telegram(
        self, detail: dict, score: int, analysis: str,
        cover_letter: str, salary: dict
    ):
        from bot.notifications import send_vacancy_card
        await send_vacancy_card(
            bot=self.bot,
            chat_id=config.TELEGRAM_CHAT_ID,
            detail=detail,
            score=score,
            analysis=analysis,
            cover_letter=cover_letter,
            salary=salary,
        )
