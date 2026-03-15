"""
Роуты для получения объявлений и клиентов из БД.
"""

import asyncio
import re
import urllib.request

import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.db import DB_PATH

_preview_cache: dict[int, str | None] = {}  # listing_id → image_url | None
_fetch_pending: set[int] = set()            # listing_ids с активным фетчем (без дублей)
_fetch_sem = asyncio.Semaphore(1)           # 1 — последовательный доступ к _thumb_page
_thumb_page = None                          # единственная вкладка для thumbnail-фетча

# Заголовки как у обычного браузера — обходят базовую защиту от ботов
_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Referer": "https://krisha.kz/",
}
# og:image — атрибуты могут идти в любом порядке
_OG_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](https?://[^"\'>\s]+)["\']'
    r'|<meta[^>]+content=["\'](https?://[^"\'>\s]+)["\'][^>]+property=["\']og:image["\']',
    re.I,
)


def _fetch_og_sync(url: str) -> str | None:
    """Синхронный HTTP-запрос за og:image. Запускается в thread pool."""
    try:
        req = urllib.request.Request(url, headers=_HTTP_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read(60_000).decode("utf-8", errors="ignore")
        m = _OG_RE.search(html)
        if m:
            return m.group(1) or m.group(2)
    except Exception:
        pass
    return None


async def _ensure_thumb_page():
    """Возвращает или создаёт единственную вкладку для thumbnail-фетча.
    Не открывает новую вкладку если уже есть живая."""
    global _thumb_page
    try:
        from agent import browser as _br
        if _br._context is None:
            return None
        if _thumb_page is not None and not _thumb_page.is_closed():
            return _thumb_page
        _thumb_page = await _br._context.new_page()
        return _thumb_page
    except Exception:
        return None


router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("/")
async def get_listings(client_id: int | None = None, limit: int = 50):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        base = """
            SELECT l.*, c.name as client_name, c.emoji as client_emoji
            FROM listings l
            LEFT JOIN clients c ON c.id = l.client_id
        """
        if client_id:
            async with db.execute(base + " WHERE l.client_id = ? ORDER BY l.found_at DESC LIMIT ?", (client_id, limit)) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(base + " ORDER BY l.found_at DESC LIMIT ?", (limit,)) as cur:
                rows = await cur.fetchall()
    return [dict(r) for r in rows]


class ClientRequest(BaseModel):
    name: str
    district: str | None = None
    budget_min: int | None = None
    budget_max: int | None = None
    area_min: int | None = None
    area_max: int | None = None
    rooms: str | None = None
    deal_type: str = "buy"
    area_polygon: str | None = None       # "lat1,lon1,lat2,lon2,..." координаты полигона
    message_template: str | None = None   # шаблон сообщения продавцу
    emoji: str = '🏠'


@router.get("/clients")
async def get_clients():
    """Возвращает список активных клиентов."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM clients WHERE active = 1 ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/clients")
async def create_client(body: ClientRequest):
    """Создаёт нового клиента с параметрами поиска."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO clients
               (name, district, budget_min, budget_max, area_min, area_max, rooms, deal_type, area_polygon, message_template, emoji)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (body.name, body.district, body.budget_min, body.budget_max,
             body.area_min, body.area_max, body.rooms, body.deal_type,
             body.area_polygon, body.message_template, body.emoji),
        )
        await db.commit()
        return {"id": cur.lastrowid, "name": body.name}


class PolygonUpdate(BaseModel):
    area_polygon: str  # "lat1,lon1,lat2,lon2,..."


@router.patch("/clients/{client_id}/polygon")
async def update_client_polygon(client_id: int, body: PolygonUpdate):
    """Сохраняет нарисованный на карте полигон для клиента."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE clients SET area_polygon = ? WHERE id = ?",
            (body.area_polygon, client_id),
        )
        await db.commit()
    return {"status": "ok"}


@router.delete("/clients/{client_id}")
async def delete_client(client_id: int):
    """Деактивирует клиента (soft delete)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE clients SET active = 0 WHERE id = ?", (client_id,))
        await db.commit()
    return {"status": "ok"}


@router.get("/messages")
async def get_messages(limit: int = 50):
    """Возвращает историю отправленных сообщений с данными объявлений."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT m.id, m.text, m.sent_at, m.status,
                      l.title, l.url, l.price, l.district, l.krisha_id,
                      c.name as client_name
               FROM messages m
               JOIN listings l ON l.id = m.listing_id
               JOIN clients  c ON c.id = l.client_id
               ORDER BY m.sent_at DESC
               LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/{listing_id}/preview")
async def get_listing_preview(listing_id: int):
    """Возвращает превью-изображение объявления.
    Сначала смотрит thumbnail из БД, иначе — загружает через Playwright-контекст
    (тот же браузер что и агент → cookies krisha.kz → никаких блокировок).
    """
    if listing_id in _preview_cache:
        return {"image_url": _preview_cache[listing_id]}

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT url, thumbnail FROM listings WHERE id = ?", (listing_id,)
        ) as cur:
            row = await cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing_url, thumbnail = row

    if thumbnail:
        _preview_cache[listing_id] = thumbnail
        return {"image_url": thumbnail}

    if not listing_url:
        _preview_cache[listing_id] = None
        return {"image_url": None}

    # Запускаем фоновый HTTP-фетч (без Playwright — og:image есть в HTML сразу).
    # Дедупликация: если уже идёт фетч для этого listing_id — не создаём ещё один.
    if listing_id not in _fetch_pending:
        _fetch_pending.add(listing_id)
        asyncio.create_task(_fetch_thumbnail_bg(listing_id, listing_url))
    return {"image_url": None}


async def _fetch_thumbnail_bg(listing_id: int, listing_url: str) -> None:
    """Фоновая задача: HTTP-запрос за og:image страницы объявления.
    Приоритет: urllib (быстро, без браузера) → Playwright single-page (fallback)."""
    image_url = None
    async with _fetch_sem:  # Semaphore(1) — последовательный доступ к _thumb_page
        try:
            # Сначала пробуем plain HTTP (og:image часто есть в server-rendered HTML)
            image_url = await asyncio.to_thread(_fetch_og_sync, listing_url)
        except Exception:
            pass

        if not image_url:
            # Fallback: единственная переиспользуемая вкладка — не создаём новую
            page = await _ensure_thumb_page()
            if page:
                try:
                    await page.goto(listing_url, wait_until="domcontentloaded", timeout=10_000)
                    image_url = await page.evaluate(
                        "() => { const m = document.querySelector('meta[property=\"og:image\"]');"
                        " return m?.content?.startsWith('http') ? m.content : null; }"
                    )
                except Exception:
                    pass

    _fetch_pending.discard(listing_id)
    _preview_cache[listing_id] = image_url
    if image_url:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE listings SET thumbnail = ? WHERE id = ?",
                    (image_url, listing_id),
                )
                await db.commit()
        except Exception:
            pass


@router.get("/stats")
async def get_stats():
    """Возвращает общую статистику для дашборда."""
    async with aiosqlite.connect(DB_PATH) as db:
        async def count(query, params=()):
            async with db.execute(query, params) as cur:
                row = await cur.fetchone()
                return row[0] if row else 0

        clients   = await count("SELECT COUNT(*) FROM clients WHERE active = 1")
        listings  = await count("SELECT COUNT(*) FROM listings")
        approved  = await count("SELECT COUNT(*) FROM listings WHERE status = 'approved'")
        messaged  = await count("SELECT COUNT(*) FROM listings WHERE status = 'messaged'")
        messages  = await count("SELECT COUNT(*) FROM messages")
        actions_today = await count(
            "SELECT COUNT(*) FROM actions_log WHERE date(created_at) = date('now')"
        )

    return {
        "clients": clients,
        "listings": listings,
        "approved": approved,
        "messaged": messaged,
        "messages": messages,
        "actions_today": actions_today,
    }
