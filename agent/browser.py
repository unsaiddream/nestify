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
    thumbnail: str | None = None


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
    """Извлекает площадь из строки — ищет число перед 'м²'."""
    m = re.search(r"([\d]+[,.]?\d*)\s*м²", text)
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
    Если задан полигон — пробует map URL, при 0 результатах — fallback на list URL.
    """
    url = _build_search_url(client)
    is_map = "/map/" in url

    if is_map:
        results = await _search_map(url)
        if not results:
            # Fallback: map URL не дал результатов (редирект или 0 в полигоне)
            # Строим обычный list URL с теми же фильтрами без полигона
            fallback_client = {**client, "area_polygon": None}
            fallback_url = _build_search_url(fallback_client)
            results = await _search_list(fallback_url, max_pages)
        return results
    else:
        return await _search_list(url, max_pages)


async def _force_lazy_images(page) -> None:
    """Принудительно устанавливает src из data-src для всех lazy-load изображений."""
    await page.evaluate("""() => {
        document.querySelectorAll('img').forEach(img => {
            const lazy = img.getAttribute('data-src')
                || img.getAttribute('data-original')
                || img.getAttribute('data-lazy')
                || img.getAttribute('data-url')
                || img.getAttribute('data-image');
            if (lazy && lazy.startsWith('http')) {
                img.setAttribute('src', lazy);  // setAttribute — не трогает JS-свойство .src
            }
        });
    }""")
    await asyncio.sleep(0.4)


async def _search_map(url: str) -> list[RawListing]:
    """Поиск через map URL Krisha — скрапим список в боковой панели."""
    results: list[RawListing] = []
    page = await new_page()
    try:
        # networkidle ждёт пока карта и AJAX-запросы завершатся
        try:
            await page.goto(url, wait_until="networkidle", timeout=45_000)
        except Exception:
            pass
        await asyncio.sleep(3)  # дополнительное ожидание рендера боковой панели

        try:
            await page.wait_for_selector(".a-card", timeout=12_000)
        except Exception:
            return results

        cards = await page.query_selector_all(".a-card")

        # Принудительно подгружаем lazy-load картинки через JS
        await _force_lazy_images(page)

        for card in cards:
            try:
                listing = await _parse_card(card)
                if listing:
                    results.append(listing)
            except Exception:
                continue

        # Если нашли мало карточек — прокручиваем список вниз для подгрузки
        if 0 < len(results) < 5:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
            await _force_lazy_images(page)
            cards = await page.query_selector_all(".a-card")
            results.clear()
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
            sep = "&" if "?" in url else "?"
            page_url = url if page_num == 1 else f"{url}{sep}page={page_num}"
            await page.goto(page_url, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(1.5)

            try:
                await page.wait_for_selector(".a-card", timeout=8_000)
            except Exception:
                break

            cards = await page.query_selector_all(".a-card")
            if not cards:
                break

            await _force_lazy_images(page)

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
    Отправляет сообщение продавцу через страницу диалога Krisha.kz.
    Напрямую переходим на /my/messages/?advertId=ID — минуем кнопку "Написать".
    Возвращает True если сообщение отправлено успешно.
    """
    # Извлекаем ID объявления из URL
    id_match = re.search(r"/(\d{6,})", listing_url)
    if not id_match:
        return False
    listing_id = id_match.group(1)

    page = await new_page()
    try:
        # Переходим прямо на страницу диалога с продавцом
        messages_url = f"{KRISHA_BASE}/my/messages/?advertId={listing_id}"
        await page.goto(messages_url, wait_until="domcontentloaded", timeout=30_000)

        # SPA (React) — ждём полного рендера
        try:
            await page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass
        await asyncio.sleep(3)

        # Ищем любой редактируемый элемент через JS:
        # textarea, input[text], или contenteditable div (React-чат)
        focused = await page.evaluate("""
            () => {
                const el = (
                    document.querySelector('textarea') ||
                    document.querySelector('input[type="text"]') ||
                    document.querySelector('[contenteditable="true"]') ||
                    document.querySelector('[contenteditable]')
                );
                if (!el) return null;
                el.scrollIntoView({ behavior: 'instant', block: 'center' });
                el.focus();
                return el.tagName + '|' + (el.placeholder || el.getAttribute('contenteditable') || 'found');
            }
        """)

        if not focused:
            return False

        await asyncio.sleep(0.5)

        # keyboard.type() генерирует реальные нажатия клавиш — работает с React/Vue
        await page.keyboard.type(message_text, delay=40)
        await asyncio.sleep(0.8)

        # Ищем видимую кнопку отправки
        send_btn = None
        for sel in [
            "button[type='submit']",
            "button:has-text('Отправить')",
            "[class*='submit']",
            "[class*='send-btn']",
            "[class*='send'][class*='btn']",
        ]:
            try:
                candidate = await page.query_selector(sel)
                if candidate and await candidate.is_visible():
                    send_btn = candidate
                    break
            except Exception:
                continue

        if send_btn:
            await send_btn.click()
        else:
            # Fallback: Enter отправляет в большинстве чатов
            await page.keyboard.press("Enter")

        await asyncio.sleep(2)
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
    district_el = await card.query_selector(".a-card__subtitle, .a-card__addr, .offer__location")
    district_text = (await district_el.inner_text()).strip() if district_el else None

    # Описание (краткое)
    desc_el = await card.query_selector(".a-card__text-preview, .a-card__description")
    desc_text = (await desc_el.inner_text()).strip() if desc_el else None

    # Первое фото — data-атрибуты ПЕРВЫМИ (img.src — JS-свойство, возвращает
    # URL страницы когда атрибут пуст, поэтому используем getAttribute)
    thumbnail = await card.evaluate("""el => {
        const img = el.querySelector('img');
        if (!img) return null;
        const src = img.getAttribute('data-src')
            || img.getAttribute('data-original')
            || img.getAttribute('data-lazy')
            || img.getAttribute('data-url')
            || img.getAttribute('data-image')
            || img.currentSrc
            || img.getAttribute('src')
            || (img.srcset ? img.srcset.split(/[,\\s]+/)[0] : null);
        return (src && src.startsWith('http')) ? src : null;
    }""")

    return RawListing(
        krisha_id=krisha_id,
        url=href,
        title=title,
        price=price,
        area=area,
        rooms=rooms,
        district=district_text,
        description=desc_text,
        thumbnail=thumbnail,
    )
