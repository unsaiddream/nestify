"""
Роуты управления агентом: запуск, остановка, статус, лог действий.
"""

import asyncio
import logging

import aiosqlite
from fastapi import APIRouter

from database.db import DB_PATH

logger = logging.getLogger("nestify.agent_route")
router = APIRouter(prefix="/agent", tags=["agent"])

# Состояние агента
_stop_event: asyncio.Event | None = None
_task: asyncio.Task | None = None
_last_error: str | None = None  # последняя ошибка для отображения в UI


@router.post("/start")
async def start_agent():
    """Запускает агента — сразу открывает браузер и начинает сканирование."""
    global _stop_event, _task, _last_error

    if _task and not _task.done():
        return {"status": "already_running"}

    from agent.analyzer import run_agent

    _last_error = None
    _stop_event = asyncio.Event()
    _task = asyncio.create_task(_run_with_error_capture(_stop_event, run_agent))
    logger.info("Агент запущен")
    return {"status": "started"}


async def _run_with_error_capture(stop_event, run_fn):
    """Обёртка вокруг run_agent — сохраняет ошибку если упал."""
    global _last_error
    try:
        await run_fn(stop_event)
    except Exception as e:
        _last_error = str(e)
        logger.error(f"Агент упал с ошибкой: {e}")


@router.post("/stop")
async def stop_agent():
    """Останавливает агента и закрывает браузер."""
    global _stop_event, _task, _last_error

    if _stop_event:
        _stop_event.set()

    if _task and not _task.done():
        try:
            await asyncio.wait_for(asyncio.shield(_task), timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            _task.cancel()

    # Закрываем браузер
    try:
        from agent.browser import close_browser
        await close_browser()
    except Exception:
        pass

    _task = None
    _stop_event = None
    logger.info("Агент остановлен")
    return {"status": "stopped"}


@router.post("/install-playwright")
async def install_playwright():
    """Скачивает Chromium через playwright driver — работает на любом Mac."""
    import asyncio.subprocess as asp
    import os
    import sys
    from pathlib import Path

    env = os.environ.copy()

    # PLAYWRIGHT_BROWSERS_PATH — куда ставить браузер.
    # Берём из окружения (main.py уже устанавливает) или задаём сами.
    browsers_path = env.get("PLAYWRIGHT_BROWSERS_PATH") or str(
        Path.home() / "Library" / "Application Support" / "Nestify" / "browsers"
    )
    Path(browsers_path).mkdir(parents=True, exist_ok=True)
    env["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path

    # Ищем playwright driver: сначала через внутреннее API пакета,
    # потом через sys.executable (pip install playwright добавляет скрипт рядом),
    # потом через PATH.
    driver: str | None = None
    try:
        from playwright._impl._driver import compute_driver_executable
        driver = str(compute_driver_executable())
    except Exception:
        pass

    if not driver:
        # Путь рядом с текущим python-интерпретатором (venv / frozen)
        bin_dir = Path(sys.executable).parent
        for candidate in ["playwright", "playwright.exe"]:
            p = bin_dir / candidate
            if p.exists():
                driver = str(p)
                break

    try:
        if driver:
            # Используем playwright driver напрямую
            cmd = [driver, "install", "chromium"]
        else:
            # Fallback: запускаем как модуль Python
            cmd = [sys.executable, "-m", "playwright", "install", "chromium"]

        proc = await asp.create_subprocess_exec(
            *cmd,
            stdout=asp.PIPE,
            stderr=asp.STDOUT,
            env=env,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
        output = stdout.decode(errors="replace") if stdout else ""
        if proc.returncode == 0:
            return {"status": "ok", "message": "Chromium успешно установлен", "output": output}
        else:
            return {"status": "error", "message": "Ошибка установки", "output": output}
    except asyncio.TimeoutError:
        return {"status": "error", "message": "Таймаут — установка заняла слишком долго (>5 мин)"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/open-browser")
async def open_browser():
    """Открывает браузер с Krisha.kz без запуска сканирования."""
    try:
        from agent.browser import get_context
        ctx = await get_context()
        pages = ctx.pages
        # Если нет вкладки с Krisha — открываем
        krisha_open = any("krisha.kz" in (p.url or "") for p in pages)
        if not krisha_open:
            page = await ctx.new_page()
            await page.goto("https://krisha.kz", wait_until="domcontentloaded", timeout=20_000)
        return {"status": "ok", "message": "Браузер открыт"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/status")
async def agent_status():
    """Возвращает текущий статус агента и последнюю ошибку."""
    running = bool(_task and not _task.done())
    return {
        "running": running,
        "last_error": _last_error,
    }


@router.get("/debug-selectors")
async def debug_selectors():
    """Открывает страницу поиска Krisha.kz и возвращает найденные селекторы — для диагностики."""
    try:
        from agent.browser import new_page
        page = await new_page()
        try:
            url = "https://krisha.kz/arenda/kvartiry/almaty/"
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            import asyncio
            await asyncio.sleep(3)

            # Проверяем разные возможные селекторы карточек
            candidates = [
                ".a-card", ".a-list__item", "[data-id]", ".card",
                "article", ".flat-card", ".listing-item", "[class*='card']",
                ".search-result", ".offer", "[class*='offer']", "[class*='flat']",
                "section.a-list .a-list__item", "ul.a-list li",
            ]
            found = {}
            for sel in candidates:
                els = await page.query_selector_all(sel)
                if els:
                    found[sel] = len(els)

            # Получаем HTML первых 3000 символов для ручного анализа
            body = await page.query_selector("body")
            html_snippet = ""
            if body:
                html_snippet = (await body.inner_html())[:3000]

            # HTML первой карточки .a-card + внутренние селекторы
            first_card_html = ""
            card_inner_selectors = {}
            first_card = await page.query_selector(".a-card")
            if first_card:
                first_card_html = await first_card.inner_html()
                # Проверяем все вложенные селекторы которые используем в парсере
                inner_check = [
                    "a.a-card__title", ".a-card__header a", "a[href*='/a/show/']",
                    ".a-card__price", "[class*='price']",
                    ".a-card__header-left", ".offer__info-title", "[class*='header']",
                    ".a-card__addr", ".offer__location", "[class*='addr']", "[class*='location']",
                    ".a-card__description", "[class*='description']",
                    "a", "[href*='/a/show/']",
                ]
                for sel in inner_check:
                    els = await first_card.query_selector_all(sel)
                    if els:
                        # Для первого элемента покажем текст
                        txt = (await els[0].inner_text()).strip()[:80]
                        card_inner_selectors[sel] = {"count": len(els), "text": txt}

            title = await page.title()
            return {
                "status": "ok",
                "url": page.url,
                "title": title,
                "selectors_found": found,
                "card_inner_selectors": card_inner_selectors,
                "first_card_html": first_card_html[:4000],
            }
        finally:
            await page.close()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/log")
async def agent_log(limit: int = 50):
    """Возвращает последние действия агента из БД."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM actions_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]
