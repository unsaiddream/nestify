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
    """Запускает 'playwright install chromium' — скачивает браузер."""
    import asyncio.subprocess as asp
    try:
        proc = await asp.create_subprocess_exec(
            "playwright", "install", "chromium",
            stdout=asp.PIPE,
            stderr=asp.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=180)
        output = stdout.decode(errors="replace") if stdout else ""
        if proc.returncode == 0:
            return {"status": "ok", "message": "Chromium успешно установлен", "output": output}
        else:
            return {"status": "error", "message": "Ошибка установки", "output": output}
    except asyncio.TimeoutError:
        return {"status": "error", "message": "Таймаут — установка заняла слишком долго"}
    except FileNotFoundError:
        return {"status": "error", "message": "Команда 'playwright' не найдена. Запустите: pip install playwright"}
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

            title = await page.title()
            return {
                "status": "ok",
                "url": page.url,
                "title": title,
                "selectors_found": found,
                "html_snippet": html_snippet,
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
