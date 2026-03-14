"""
Браузерный модуль — Playwright с постоянным профилем.
Использует уже существующую сессию пользователя в браузере,
поэтому логин в Krisha.kz не нужен — пользователь сам залогинен.
"""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright, BrowserContext, Page

# Профиль браузера хранится рядом с БД — сессия сохраняется между запусками
PROFILE_DIR = Path(__file__).parent.parent / "browser_profile"
KRISHA_BASE  = "https://krisha.kz"


_playwright  = None
_context: BrowserContext | None = None


async def get_context() -> BrowserContext:
    """
    Возвращает браузерный контекст с постоянным профилем.
    При первом вызове запускает браузер и открывает Krisha.kz.
    Пользователь логинится вручную один раз — сессия сохраняется.
    """
    global _playwright, _context
    if _context is not None:
        return _context

    PROFILE_DIR.mkdir(exist_ok=True)

    _playwright = await async_playwright().start()
    _context = await _playwright.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=False,          # браузер видимый — пользователь видит что происходит
        slow_mo=300,             # небольшая задержка между действиями — выглядит по-человечески
        viewport={"width": 1280, "height": 800},
        locale="ru-RU",
        args=["--disable-blink-features=AutomationControlled"],  # скрываем признаки автоматизации
    )

    # Если сессии нет — открываем Krisha.kz чтобы пользователь залогинился
    pages = _context.pages
    if not pages:
        page = await _context.new_page()
        await page.goto(KRISHA_BASE)

    return _context


async def new_page() -> Page:
    """Открывает новую вкладку в браузере агента."""
    ctx = await get_context()
    return await ctx.new_page()


async def close_browser():
    """Закрывает браузер и сохраняет сессию."""
    global _playwright, _context
    if _context:
        await _context.close()
        _context = None
    if _playwright:
        await _playwright.stop()
        _playwright = None


async def is_logged_in() -> bool:
    """Проверяет, залогинен ли пользователь на Krisha.kz."""
    try:
        ctx = await get_context()
        page = await ctx.new_page()
        await page.goto(f"{KRISHA_BASE}/user/", wait_until="domcontentloaded", timeout=10_000)
        # Если редиректит на /login — значит не залогинен
        logged_in = "/login" not in page.url
        await page.close()
        return logged_in
    except Exception:
        return False
