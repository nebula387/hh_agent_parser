"""
bot/telegram_bot.py — aiogram 3 бот: обработка кнопок + команды
"""

import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from db.storage import Database
from hh.client import HHClient
from config import config

log = logging.getLogger(__name__)

_edit_states: dict[int, str] = {}  # chat_id -> vacancy_id


async def create_bot(db: Database) -> tuple[Bot, Dispatcher]:
    bot = Bot(token=config.TELEGRAM_TOKEN)
    dp = Dispatcher()

    # ── /start ─────────────────────────────────────────────────
    @dp.message(Command("start"))
    async def cmd_start(msg: Message):
        await msg.answer(
            "🤖 <b>HH Job Agent запущен</b>\n\n"
            "Сканирую HH в 09:00 и 18:00 МСК.\n"
            "При нахождении подходящих вакансий пришлю карточку "
            "с анализом и сопроводительным письмом.\n\n"
            "<b>Команды:</b>\n"
            "/scan — запустить сканирование прямо сейчас\n"
            "/stats — статистика откликов\n"
            "/setresume — установить ID резюме (если несколько резюме на HH)",
            parse_mode="HTML"
        )

    # ── /scan — ручной запуск ──────────────────────────────────
    @dp.message(Command("scan"))
    async def cmd_scan(msg: Message):
        if msg.chat.id != config.TELEGRAM_CHAT_ID:
            return
        await msg.answer("🔍 Запускаю сканирование...")
        from hh.scanner import JobScanner
        scanner = JobScanner(bot=bot, db=db)
        await scanner.run_scan()

    # ── /stats ─────────────────────────────────────────────────
    @dp.message(Command("stats"))
    async def cmd_stats(msg: Message):
        stats = await db.get_stats()
        await msg.answer(
            f"📊 <b>Статистика</b>\n\n"
            f"Всего найдено: {stats['total']}\n"
            f"Откликнулся: {stats['applied']}\n"
            f"Пропущено: {stats['skipped']}\n"
            f"Ожидает: {stats['total'] - stats['applied'] - stats['skipped']}",
            parse_mode="HTML"
        )

    # ── /setresume <resume_id> ─────────────────────────────────
    @dp.message(Command("setresume"))
    async def cmd_setresume(msg: Message):
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            await msg.answer(
                "Использование: /setresume <ID_РЕЗЮМЕ>\n"
                "ID найди в адресной строке резюме на hh.ru"
            )
            return
        config.HH_RESUME_ID = parts[1].strip()
        await msg.answer(f"✅ Resume ID установлен: {config.HH_RESUME_ID}")

    # ── Кнопка: Откликнуться ───────────────────────────────────
    @dp.callback_query(F.data.startswith("apply:"))
    async def handle_apply(cb: CallbackQuery):
        vacancy_id = cb.data.split(":", 1)[1]
        vacancy = await db.get_vacancy(vacancy_id)

        if not vacancy:
            await cb.answer("❌ Вакансия не найдена в базе")
            return

        if vacancy["status"] == "applied":
            await cb.answer("✅ Ты уже откликнулся на эту вакансию")
            return

        await cb.answer("⏳ Открываю браузер и отправляю отклик...")

        try:
            async with HHClient() as client:
                success = await client.apply_to_vacancy(
                    vacancy_id=vacancy_id,
                    resume_id=config.HH_RESUME_ID,
                    cover_letter=vacancy["cover_letter"],
                )
        except Exception as e:
            log.error(f"Apply error: {e}")
            success = False

        if success:
            await db.set_status(vacancy_id, "applied")
            try:
                current_text = cb.message.text or cb.message.caption or ""
                await cb.message.edit_text(
                    current_text + "\n\n✅ <b>ОТКЛИК ОТПРАВЛЕН</b>",
                    parse_mode="HTML",
                    reply_markup=None,
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
            await cb.message.answer(
                f"✅ Отклик на «{vacancy['title']}» в {vacancy['company']} отправлен!"
            )
        else:
            await cb.message.answer(
                "❌ Ошибка отправки отклика.\n"
                "Проверь HH_LOGIN и HH_PASSWORD в config.py, "
                "затем попробуй снова."
            )

    # ── Кнопка: Пропустить ────────────────────────────────────
    @dp.callback_query(F.data.startswith("skip:"))
    async def handle_skip(cb: CallbackQuery):
        vacancy_id = cb.data.split(":", 1)[1]
        await db.set_status(vacancy_id, "skipped")
        await cb.answer("Пропущено")
        try:
            current_text = cb.message.text or ""
            await cb.message.edit_text(
                current_text + "\n\n⏭ <i>Пропущено</i>",
                parse_mode="HTML",
                reply_markup=None,
                disable_web_page_preview=True,
            )
        except Exception:
            pass

    # ── Кнопка: Редактировать письмо ──────────────────────────
    @dp.callback_query(F.data.startswith("edit:"))
    async def handle_edit(cb: CallbackQuery):
        vacancy_id = cb.data.split(":", 1)[1]
        vacancy = await db.get_vacancy(vacancy_id)
        if not vacancy:
            await cb.answer("Вакансия не найдена")
            return

        _edit_states[cb.from_user.id] = vacancy_id
        await cb.answer()
        await cb.message.answer(
            f"✏️ <b>Редактирование письма для:</b> {vacancy['title']}\n\n"
            f"Текущее письмо:\n<i>{vacancy['cover_letter']}</i>\n\n"
            "Отправь новый текст письма:",
            parse_mode="HTML"
        )

    # ── Приём отредактированного письма ───────────────────────
    @dp.message(F.text & ~F.text.startswith("/"))
    async def handle_edited_letter(msg: Message):
        if msg.from_user.id not in _edit_states:
            return
        vacancy_id = _edit_states.pop(msg.from_user.id)
        async with __import__('aiosqlite').connect(db.path) as conn:
            await conn.execute(
                "UPDATE vacancies SET cover_letter=? WHERE id=?",
                (msg.text, vacancy_id)
            )
            await conn.commit()
        await msg.answer(
            "✅ Письмо обновлено!\n\n"
            "Теперь нажми <b>Откликнуться</b> на карточке вакансии.",
            parse_mode="HTML"
        )

    return bot, dp
