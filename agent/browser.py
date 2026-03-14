"""
Браузерный модуль — Playwright с постоянным профилем.
Использует уже существующую сессию пользователя в браузере,
поэтому логин в Krisha.kz не нужен — пользователь сам залогинен.
"""

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator

from playwright.async_api import async_playwright, BrowserContext, Page

PROFILE_DIR = Path(__file__).parent.parent / "browser_profile"
KRISHA_BASE = "https://krisha.kz"

_playwright = None
_context: BrowserContext | None = None


@dataclass
class RawListing:
    krisha_id: str
    url: str
    title: str
    price: int | None
    area: float | None
    rooms: int | None
    district: str | None
    description: str | None


async def get_context() -> BrowserContext:
    """
    Возвращает браузерный контекст с постоянным профилем.
    При первом запуске открывает браузер — пользователь уже залогинен.
    """
    global _playwright, _context
    if _context is not None:
        return _context

    PROFILE_DIR.mkdir(exist_ok=True)

    _playwright = await async_playwright().start()
    _context = await _playwright.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
        slow_mo=200,
        viewport={"width": 1280, "height": 800},
        locale="ru-RU",
        args=["--disable-blink-features=AutomationControlled"],
    )

    # Открываем Krisha.kz если вкладок ещё нет
    if not _context.pages:
        page = await _context.new_page()
        await page.goto(KRISHA_BASE)

    return _context


async def new_page() -> Page:
    ctx = await get_context()
    return await ctx.new_page()


async def close_browser():
    global _playwright, _context
    if _context:
        await _context.close()
        _context = None
    if _playwright:
        await _playwright.stop()
        _playwright = None


def _build_search_url(client: dict) -> str:
    """Строит URL поиска на Krisha.kz по параметрам клиента."""
    deal = "arenda" if client.get("deal_type") == "rent" else "prodazha"

    # Если задан полигон — используем map URL Krisha
    if client.get("area_polygon"):
        return _build_map_url(client, deal)

    base = f"{KRISHA_BASE}/{deal}/kvartiry/"

    district: str = client.get("district") or ""
    city_slug = _city_slug(district)
    if city_slug:
        base += f"{city_slug}/"

    params = _filter_params(client)
    query = "&".join(params)
    return f"{base}?{query}" if query else base


def _build_map_url(client: dict, deal: str) -> str:
    """
    Строит URL карты Krisha.kz с полигоном области.
    Формат: /map/{deal}/kvartiry/?areas=p{lat},{lon},{lat},{lon},...
    """
    polygon = client["area_polygon"]  # "lat1,lon1,lat2,lon2,..."
    coords = [c.strip() for c in polygon.split(",")]

    # Закрываем полигон (первая точка = последняя)
    if len(coords) >= 4 and coords[:2] != coords[-2:]:
        coords = coords + coords[:2]

    areas_param = "p" + ",".join(coords)

    # Центр полигона для zoom/lat/lon параметров
    lats = [float(coords[i]) for i in range(0, len(coords), 2)]
    lons = [float(coords[i]) for i in range(1, len(coords), 2)]
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    params = [f"zoom=13&lat={center_lat:.5f}&lon={center_lon:.5f}&areas={areas_param}"]
    params += _filter_params(client)

    return f"{KRISHA_BASE}/map/{deal}/kvartiry/?{'&'.join(params)}"


def _filter_params(client: dict) -> list[str]:
    """Общие фильтры (цена, площадь, комнаты) для любого URL."""
    params = []
    if client.get("budget_min"):
        params.append(f"das[price][from]={client['budget_min']}")
    if client.get("budget_max"):
        params.append(f"das[price][to]={client['budget_max']}")
    if client.get("area_min"):
        params.append(f"das[live.square][from]={client['area_min']}")
    if client.get("area_max"):
        params.append(f"das[live.square][to]={client['area_max']}")
    rooms_raw = client.get("rooms")
    if rooms_raw and rooms_raw != "4+":
        params.append(f"das[live.rooms]={rooms_raw}")
    elif rooms_raw == "4+":
        params.append("das[live.rooms][from]=4")
    return params


def _city_slug(district: str) -> str:
    """Простое определение города по введённому тексту района."""
    d = district.lower()
    if "алмат" in d or "almaty" in d:
        return "almaty"
    if "астан" in d or "astana" in d or "нур-султан" in d:
        return "astana"
    if "шымкент" in d or "shymkent" in d:
        return "shymkent"
    if "актобе" in d or "aktobe" in d:
        return "aktobe"
    if "атырау" in d or "atyrau" in d:
        return "atyrau"
    if "павлодар" in d or "pavlodar" in d:
        return "pavlodar"
    return ""


def _parse_price(text: str) -> int | None:
    """Извлекает числовую цену из строки вида '45 000 000 ₸'."""
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


def _parse_area(text: str) -> float | None:
    """Извлекает площадь из строки вида '65 м²'."""
    m = re.search(r"(\d+[\.,]?\d*)", text)
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def _parse_rooms(text: str) -> int | None:
    """Извлекает количество комнат из строки."""
    m = re.search(r"(\d+)-комн", text)
    if m:
        return int(m.group(1))
    return None


async def search_listings(client: dict, max_pages: int = 3) -> list[RawListing]:
    """
    Ищет объявления на Krisha.kz по параметрам клиента.
    Если задан полигон — использует map URL и скрапит правый сайдбар.
    """
    url = _build_search_url(client)
    is_map = "/map/" in url

    if is_map:
        return await _search_map(url)
    else:
        return await _search_list(url, max_pages)


async def _search_map(url: str) -> list[RawListing]:
    """Поиск через map URL Krisha — скрапим список в правом сайдбаре."""
    results: list[RawListing] = []
    page = await new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(2.5)  # ждём загрузки карты и сайдбара

        # Ждём карточки в сайдбаре
        try:
            await page.wait_for_selector(".a-card", timeout=10_000)
        except Exception:
            return results

        cards = await page.query_selector_all(".a-card")
        for card in cards:
            try:
                listing = await _parse_card(card)
                if listing:
                    results.append(listing)
            except Exception:
                continue

    finally:
        await page.close()
    return results


async def _search_list(url: str, max_pages: int) -> list[RawListing]:
    """Поиск через обычный список объявлений."""
    results: list[RawListing] = []
    page = await new_page()
    try:
        for page_num in range(1, max_pages + 1):
            page_url = url if page_num == 1 else f"{url}&page={page_num}"
            await page.goto(page_url, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(1.5)

            try:
                await page.wait_for_selector(".a-card", timeout=8_000)
            except Exception:
                break

            cards = await page.query_selector_all(".a-card")
            if not cards:
                break

            for card in cards:
                try:
                    listing = await _parse_card(card)
                    if listing:
                        results.append(listing)
                except Exception:
                    continue

            if len(cards) < 20:
                break

            await asyncio.sleep(2)
    finally:
        await page.close()
    return results


async def send_message(listing_url: str, message_text: str) -> bool:
    """
    Отправляет сообщение продавцу на странице объявления Krisha.kz.
    Возвращает True если сообщение отправлено успешно.
    """
    page = await new_page()
    try:
        await page.goto(listing_url, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(1.5)

        # Пробуем найти кнопку "Написать" / чат
        btn_selectors = [
            "button.send-message",
            "[data-name='sendMessage']",
            ".offer-chat__button",
            "button:has-text('Написать')",
            "a:has-text('Написать')",
            ".contacts__btn-message",
            "[class*='message'][class*='btn']",
            "[class*='chat'][class*='btn']",
        ]

        btn = None
        for sel in btn_selectors:
            try:
                btn = await page.wait_for_selector(sel, timeout=3_000)
                if btn:
                    break
            except Exception:
                continue

        if not btn:
            return False

        await btn.click()
        await asyncio.sleep(1)

        # Ищем поле ввода сообщения
        input_selectors = [
            "textarea.send-message__textarea",
            ".offer-chat__input textarea",
            "[class*='chat'] textarea",
            "[class*='message'] textarea",
            "textarea[placeholder*='сообщен']",
            "textarea[placeholder*='Сообщен']",
        ]

        textarea = None
        for sel in input_selectors:
            try:
                textarea = await page.wait_for_selector(sel, timeout=3_000)
                if textarea:
                    break
            except Exception:
                continue

        if not textarea:
            return False

        await textarea.click()
        await textarea.fill(message_text)
        await asyncio.sleep(0.8)

        # Кнопка отправки
        send_selectors = [
            "button[type='submit']",
            "button:has-text('Отправить')",
            ".send-message__submit",
            "[class*='submit']",
            "[class*='send'][class*='button']",
        ]

        send_btn = None
        for sel in send_selectors:
            try:
                send_btn = await page.query_selector(sel)
                if send_btn:
                    break
            except Exception:
                continue

        if not send_btn:
            return False

        await send_btn.click()
        await asyncio.sleep(1.5)

        return True

    except Exception:
        return False
    finally:
        await page.close()


async def _parse_card(card) -> RawListing | None:
    """Извлекает данные из одной карточки объявления."""
    # Ссылка и ID
    link_el = await card.query_selector("a.a-card__title, .a-card__header a")
    if not link_el:
        return None

    href = await link_el.get_attribute("href") or ""
    if not href.startswith("http"):
        href = KRISHA_BASE + href

    # ID из URL (например /a/show/12345678)
    id_match = re.search(r"/(\d{6,})", href)
    krisha_id = id_match.group(1) if id_match else href

    title = (await link_el.inner_text()).strip()

    # Цена
    price_el = await card.query_selector(".a-card__price")
    price_text = (await price_el.inner_text()).strip() if price_el else ""
    price = _parse_price(price_text)

    # Параметры: комнаты, площадь
    params_el = await card.query_selector(".a-card__header-left, .offer__info-title")
    params_text = (await params_el.inner_text()).strip() if params_el else ""
    rooms = _parse_rooms(params_text)
    area  = _parse_area(params_text)

    # Район / адрес
    district_el = await card.query_selector(".a-card__addr, .offer__location")
    district_text = (await district_el.inner_text()).strip() if district_el else None

    # Описание (краткое)
    desc_el = await card.query_selector(".a-card__description")
    desc_text = (await desc_el.inner_text()).strip() if desc_el else None

    return RawListing(
        krisha_id=krisha_id,
        url=href,
        title=title,
        price=price,
        area=area,
        rooms=rooms,
        district=district_text,
        description=desc_text,
    )
