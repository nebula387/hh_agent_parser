"""
bot/notifications.py — форматирование и отправка карточки вакансии в Telegram
"""

import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from hh.client import format_salary

log = logging.getLogger(__name__)

SCORE_EMOJI = {
    range(90, 101): "🔥",
    range(80, 90): "⭐",
    range(65, 80): "✅",
}


def get_score_emoji(score: int) -> str:
    for r, emoji in SCORE_EMOJI.items():
        if score in r:
            return emoji
    return "🟡"


async def send_vacancy_card(
    bot: Bot, chat_id: int, detail: dict,
    score: int, analysis: str, cover_letter: str, salary: dict
):
    vacancy_id = detail["id"]
    title = detail.get("name", "")
    company = detail.get("employer", {}).get("name", "")
    url = detail.get("alternate_url", "")
    experience = detail.get("experience", {}).get("name", "")
    schedule = detail.get("schedule", {}).get("name", "")
    salary_str = format_salary(
        salary.get("salary_from"),
        salary.get("salary_to"),
        salary.get("salary_currency", "RUR"),
    )

    emoji = get_score_emoji(score)

    # ── Карточка вакансии ──────────────────────────────────────
    card = (
        f"{emoji} <b>Совпадение: {score}/100</b>\n\n"
        f"💼 <b>{title}</b>\n"
        f"🏢 {company}\n"
        f"💰 {salary_str}\n"
        f"📋 {experience} • {schedule}\n"
        f"🔗 <a href='{url}'>Открыть на HH</a>\n\n"
        f"<b>Анализ:</b>\n{analysis}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>📝 Сопроводительное письмо:</b>\n\n"
        f"{cover_letter}"
    )

    # Telegram лимит 4096 символов
    if len(card) > 4090:
        card = card[:4087] + "..."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✅ Откликнуться",
            callback_data=f"apply:{vacancy_id}"
        ),
        InlineKeyboardButton(
            text="❌ Пропустить",
            callback_data=f"skip:{vacancy_id}"
        ),
    ], [
        InlineKeyboardButton(
            text="✏️ Редактировать письмо",
            callback_data=f"edit:{vacancy_id}"
        ),
    ]])

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=card,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
    except Exception as e:
        log.error(f"Failed to send vacancy card {vacancy_id}: {e}")
