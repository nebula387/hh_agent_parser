"""
db/storage.py — хранилище: seen вакансии, статусы откликов
"""

import aiosqlite
import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)
DB_PATH = "job_agent.db"


class Database:
    def __init__(self):
        self.path = DB_PATH

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS vacancies (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    company TEXT,
                    url TEXT,
                    salary_from INTEGER,
                    salary_to INTEGER,
                    salary_currency TEXT,
                    score INTEGER,
                    cover_letter TEXT,
                    status TEXT DEFAULT 'pending',
                    seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    applied_at TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS hh_tokens (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    access_token TEXT,
                    refresh_token TEXT,
                    expires_at TIMESTAMP
                )
            """)
            await db.commit()
        log.info("✅ База данных инициализирована")

    async def is_seen(self, vacancy_id: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT id FROM vacancies WHERE id = ?", (vacancy_id,)
            )
            return await cur.fetchone() is not None

    async def save_vacancy(self, vacancy: dict):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                INSERT OR IGNORE INTO vacancies
                (id, title, company, url, salary_from, salary_to,
                 salary_currency, score, cover_letter, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                vacancy["id"], vacancy["title"], vacancy["company"],
                vacancy["url"], vacancy.get("salary_from"),
                vacancy.get("salary_to"), vacancy.get("salary_currency"),
                vacancy["score"], vacancy["cover_letter"]
            ))
            await db.commit()

    async def set_status(self, vacancy_id: str, status: str):
        async with aiosqlite.connect(self.path) as db:
            applied_at = datetime.now() if status == "applied" else None
            await db.execute(
                "UPDATE vacancies SET status=?, applied_at=? WHERE id=?",
                (status, applied_at, vacancy_id)
            )
            await db.commit()

    async def get_vacancy(self, vacancy_id: str) -> Optional[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM vacancies WHERE id=?", (vacancy_id,)
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def save_tokens(self, access: str, refresh: str, expires_at: datetime):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO hh_tokens (id, access_token, refresh_token, expires_at)
                VALUES (1, ?, ?, ?)
            """, (access, refresh, expires_at))
            await db.commit()

    async def get_tokens(self) -> Optional[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM hh_tokens WHERE id=1")
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_stats(self) -> dict:
        async with aiosqlite.connect(self.path) as db:
            total = (await (await db.execute("SELECT COUNT(*) FROM vacancies")).fetchone())[0]
            applied = (await (await db.execute(
                "SELECT COUNT(*) FROM vacancies WHERE status='applied'")).fetchone())[0]
            skipped = (await (await db.execute(
                "SELECT COUNT(*) FROM vacancies WHERE status='skipped'")).fetchone())[0]
            return {"total": total, "applied": applied, "skipped": skipped}
