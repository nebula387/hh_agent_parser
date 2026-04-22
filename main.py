"""
HH Job Hunter Agent — main entry point
Запуск: python main.py
"""

import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot.telegram_bot import create_bot
from hh.scanner import JobScanner
from db.storage import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger(__name__)


async def main():
    db = Database()
    await db.init()

    bot, dp = await create_bot(db)
    scanner = JobScanner(bot=bot, db=db)

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    # 2 раза в день — 9:00 и 18:00
    scheduler.add_job(scanner.run_scan, "cron", hour="9,18", minute=0)
    scheduler.start()

    log.info("🤖 HH Job Agent запущен. Сканирование в 09:00 и 18:00 МСК")

    # Запуск бота
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
