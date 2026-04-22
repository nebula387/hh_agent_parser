"""
hh/client.py — Playwright-based HH scraper (поиск + отклик)
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from config import config

log = logging.getLogger(__name__)

COOKIES_FILE = Path("hh_cookies.json")

_BROWSER_ARGS = ["--disable-blink-features=AutomationControlled", "--no-sandbox"]
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class HHClient:
    def __init__(self):
        self._pw = None
        self._browser = None
        self._ctx = None

    async def start(self):
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=True,
            args=_BROWSER_ARGS,
        )
        self._ctx = await self._browser.new_context(
            user_agent=_UA,
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={"Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"},
        )
        if COOKIES_FILE.exists():
            cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
            await self._ctx.add_cookies(cookies)
        await self._ensure_logged_in()

    async def close(self):
        if self._ctx:
            cookies = await self._ctx.cookies()
            COOKIES_FILE.write_text(
                json.dumps(cookies, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            await self._ctx.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.close()

    # ── Авторизация ────────────────────────────────────────────────

    async def _ensure_logged_in(self):
        page = await self._ctx.new_page()
        try:
            await page.goto("https://hh.ru", wait_until="domcontentloaded", timeout=30_000)
            if await page.query_selector("[data-qa='mainmenu_myResumes']"):
                log.info("HH: авторизован (из cookies)")
                return
            log.info("HH: cookies устарели, выполняю вход...")
            await self._login(page)
        finally:
            await page.close()

    async def _login(self, page):
        await page.goto("https://hh.ru/account/login", wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(1000)

        # Шаг 1: ввод логина
        for sel in ["input[data-qa='login-input-username']", "input[name='login']", "input[type='text']"]:
            field = await page.query_selector(sel)
            if field:
                await field.fill(config.HH_LOGIN)
                break
        else:
            log.error("HH login: поле логина не найдено")
            return

        await page.wait_for_timeout(500)

        for sel in ["button[data-qa='account-login-submit']", "button[type='submit']"]:
            btn = await page.query_selector(sel)
            if btn:
                await btn.click()
                break

        await page.wait_for_timeout(2000)

        # Шаг 2: ввод пароля (может появиться на той же или новой странице)
        for sel in ["input[data-qa='login-input-password']", "input[name='password']", "input[type='password']"]:
            pwd = await page.query_selector(sel)
            if pwd:
                await pwd.fill(config.HH_PASSWORD)
                break
        else:
            log.error("HH login: поле пароля не найдено (возможна SMS-верификация)")
            return

        await page.wait_for_timeout(500)

        for sel in ["button[data-qa='account-login-submit']", "button[type='submit']"]:
            btn = await page.query_selector(sel)
            if btn:
                await btn.click()
                break

        await page.wait_for_load_state("domcontentloaded", timeout=15_000)

        if await page.query_selector("[data-qa='mainmenu_myResumes']"):
            log.info("✅ HH: вход выполнен успешно")
        else:
            log.warning("HH: вход мог не удаться — проверьте логин/пароль или captcha")

    # ── Поиск ─────────────────────────────────────────────────────

    async def search_vacancies(
        self, text: str, area: int = 113,
        per_page: int = 50, page: int = 0,
    ) -> list[dict]:
        params = [
            ("text", text),
            ("area", str(area)),
            ("per_page", str(per_page)),
            ("page", str(page)),
            ("order_by", "publication_time"),
        ]
        if config.SEARCH_REMOTE_ONLY:
            params.append(("schedule", "remote"))
        for exp in config.EXPERIENCE_LEVELS:
            params.append(("experience", exp))

        url = f"https://hh.ru/search/vacancy?{urlencode(params)}"
        pg = await self._ctx.new_page()
        try:
            await pg.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await pg.wait_for_timeout(1500)
            return await self._parse_search_page(pg)
        except Exception as e:
            log.error(f"Ошибка поиска '{text}': {e}")
            return []
        finally:
            await pg.close()

    async def _parse_search_page(self, page) -> list[dict]:
        try:
            await page.wait_for_selector(
                "[data-qa='vacancy-serp__vacancy'], [data-qa='vacancy-serp-empty']",
                timeout=8_000,
            )
        except Exception:
            pass

        cards = await page.query_selector_all("[data-qa='vacancy-serp__vacancy']")
        vacancies = []

        for card in cards:
            try:
                link = await card.query_selector("a[data-qa='serp-item__title']")
                if not link:
                    continue
                href = await link.get_attribute("href") or ""
                m = re.search(r"/vacancy/(\d+)", href)
                if not m:
                    continue
                vid = m.group(1)
                title = (await link.inner_text()).strip()

                company = ""
                for sel in [
                    "[data-qa='vacancy-serp__vacancy-employer-company-name']",
                    "[data-qa='vacancy-serp__vacancy-employer']",
                ]:
                    co_el = await card.query_selector(sel)
                    if co_el:
                        company = (await co_el.inner_text()).strip()
                        break

                sal_el = await card.query_selector("[data-qa='vacancy-serp__vacancy-compensation']")
                sal_text = (await sal_el.inner_text()).strip() if sal_el else ""

                exp_el = await card.query_selector(
                    ".vacancy-serp-item__work-experience, "
                    "[data-qa='vacancy-serp-item-body__work-experience']"
                )
                exp_text = (await exp_el.inner_text()).strip() if exp_el else ""

                vacancies.append({
                    "id": vid,
                    "name": title,
                    "employer": {"name": company},
                    "alternate_url": f"https://hh.ru/vacancy/{vid}",
                    "_salary_text": sal_text,
                    "schedule": {"id": "remote", "name": "Удалённая работа"},
                    "experience": {"id": _exp_id(exp_text), "name": exp_text},
                })
            except Exception as e:
                log.debug(f"Ошибка парсинга карточки: {e}")

        return vacancies

    # ── Детали вакансии ────────────────────────────────────────────

    async def get_vacancy_detail(self, vacancy_id: str) -> Optional[dict]:
        pg = await self._ctx.new_page()
        try:
            await pg.goto(
                f"https://hh.ru/vacancy/{vacancy_id}",
                wait_until="domcontentloaded", timeout=30_000,
            )
            await pg.wait_for_timeout(1000)

            title_el = await pg.query_selector("h1[data-qa='vacancy-title']")
            title = (await title_el.inner_text()).strip() if title_el else ""

            company = ""
            for sel in [
                "[data-qa='vacancy-company-name']",
                "a[data-qa='vacancy-company']",
                ".vacancy-company__name",
            ]:
                co_el = await pg.query_selector(sel)
                if co_el:
                    company = (await co_el.inner_text()).strip()
                    break

            desc_el = await pg.query_selector("[data-qa='vacancy-description']")
            description = await desc_el.inner_html() if desc_el else ""

            sal_text = ""
            for sel in [
                "[data-qa='vacancy-salary-compensation-title-fallback']",
                "[data-qa='vacancy-salary']",
                ".vacancy-salary",
            ]:
                sal_el = await pg.query_selector(sel)
                if sal_el:
                    sal_text = (await sal_el.inner_text()).strip()
                    break

            exp_text = ""
            for el in await pg.query_selector_all("[data-qa='vacancy-view-employment-mode']"):
                t = (await el.inner_text()).strip()
                if any(w in t.lower() for w in ["опыт", "год", "лет"]):
                    exp_text = t
                    break

            salary = _parse_salary_text(sal_text)

            return {
                "id": vacancy_id,
                "name": title,
                "employer": {"name": company},
                "description": description,
                "alternate_url": f"https://hh.ru/vacancy/{vacancy_id}",
                "experience": {"name": exp_text},
                "schedule": {"name": "Удалённая работа"},
                "salary": {
                    "from": salary["salary_from"],
                    "to": salary["salary_to"],
                    "currency": salary["salary_currency"],
                },
            }
        except Exception as e:
            log.error(f"Ошибка деталей вакансии {vacancy_id}: {e}")
            return None
        finally:
            await pg.close()

    # ── Отклик ────────────────────────────────────────────────────

    async def apply_to_vacancy(
        self, vacancy_id: str, resume_id: str, cover_letter: str
    ) -> bool:
        pg = await self._ctx.new_page()
        try:
            await pg.goto(
                f"https://hh.ru/vacancy/{vacancy_id}",
                wait_until="domcontentloaded", timeout=30_000,
            )
            await pg.wait_for_timeout(1500)

            # Уже откликались?
            if await pg.query_selector("[data-qa='vacancy-response-letter-already-sent']"):
                log.info(f"Вакансия {vacancy_id}: отклик уже был отправлен")
                return True

            apply_btn = None
            for sel in [
                "a[data-qa='vacancy-response-link-top']",
                "button[data-qa='vacancy-response-link-top']",
            ]:
                apply_btn = await pg.query_selector(sel)
                if apply_btn:
                    break

            if not apply_btn:
                log.error(f"Кнопка отклика не найдена: {vacancy_id}")
                return False

            await apply_btn.click()
            await pg.wait_for_timeout(2000)

            # Выбор резюме (если несколько)
            if resume_id:
                radio = await pg.query_selector(f"input[value='{resume_id}']")
                if radio:
                    await radio.click()
                    await pg.wait_for_timeout(500)

            # Сопроводительное письмо
            for sel in [
                "textarea[data-qa='vacancy-response-letter-body']",
                "textarea[name='message']",
            ]:
                letter_el = await pg.query_selector(sel)
                if letter_el and cover_letter:
                    await letter_el.fill(cover_letter)
                    break

            await pg.wait_for_timeout(500)

            # Кнопка отправки
            for sel in [
                "button[data-qa='vacancy-response-submit-button']",
                "button[data-qa='vacancy-response-letter-submit']",
            ]:
                submit_el = await pg.query_selector(sel)
                if submit_el:
                    await submit_el.click()
                    await pg.wait_for_timeout(2000)
                    log.info(f"✅ Отклик отправлен: {vacancy_id}")
                    return True

            log.error(f"Кнопка отправки не найдена: {vacancy_id}")
            return False

        except Exception as e:
            log.error(f"Ошибка отклика {vacancy_id}: {e}")
            return False
        finally:
            await pg.close()


# ── Утилиты ────────────────────────────────────────────────────────

def _exp_id(text: str) -> str:
    t = text.lower()
    if "без опыта" in t or "нет опыта" in t:
        return "noExperience"
    if "от 1" in t or "1–3" in t or "1-3" in t:
        return "between1And3"
    if "от 3" in t or "3–6" in t or "3-6" in t:
        return "between3And6"
    return ""


def _parse_salary_text(text: str) -> dict:
    text = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    cur = "RUR"
    for sym, code in [("₽", "RUR"), ("$", "USD"), ("€", "EUR"), ("₸", "KZT")]:
        if sym in text:
            cur = code
            break
    nums = [int(n.replace(" ", "")) for n in re.findall(r"\d[\d ]*\d|\d", text) if n.strip().isdigit() or re.match(r"[\d ]+", n)]
    # убираем случайно захваченные маленькие числа (часы, дни)
    nums = [n for n in nums if n >= 1000]
    sal_from = sal_to = None
    if len(nums) >= 2:
        sal_from, sal_to = nums[0], nums[1]
    elif len(nums) == 1:
        if any(w in text.lower() for w in ["от", "from"]):
            sal_from = nums[0]
        elif any(w in text.lower() for w in ["до", "up to"]):
            sal_to = nums[0]
        else:
            sal_from = nums[0]
    return {"salary_from": sal_from, "salary_to": sal_to, "salary_currency": cur}


def parse_salary(vacancy: dict) -> dict:
    """Извлекает salary из структуры вакансии (совместимость со scanner.py)"""
    s = vacancy.get("salary") or {}
    return {
        "salary_from": s.get("from"),
        "salary_to": s.get("to"),
        "salary_currency": s.get("currency", "RUR"),
    }


def format_salary(salary_from, salary_to, currency) -> str:
    if not salary_from and not salary_to:
        return "не указана"
    cur_sym = {"RUR": "₽", "USD": "$", "EUR": "€", "KZT": "₸"}.get(currency, currency)
    if salary_from and salary_to:
        return f"{salary_from:,} – {salary_to:,} {cur_sym}"
    elif salary_from:
        return f"от {salary_from:,} {cur_sym}"
    else:
        return f"до {salary_to:,} {cur_sym}"
