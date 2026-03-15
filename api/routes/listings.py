"""
Роуты для получения объявлений и клиентов из БД.
"""

import asyncio

import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.db import DB_PATH

_preview_cache: dict[int, str | None] = {}  # listing_id → image_url | None
# Семафор: не более 2 одновременных Playwright-навигаций для thumbnail
_fetch_sem = asyncio.Semaphore(2)

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

    # Запускаем фоновый фетч через Playwright (реальный браузер с куками krisha.kz).
    # Отвечаем клиенту сразу null — картинка появится при следующем ховере из кэша.
    asyncio.create_task(_fetch_thumbnail_bg(listing_id, listing_url))
    return {"image_url": None}


async def _fetch_thumbnail_bg(listing_id: int, listing_url: str) -> None:
    """Фоновая задача: открывает страницу объявления через Playwright,
    извлекает первое фото, сохраняет в кэш и в БД."""
    # Если уже в кэше — не делаем ничего
    if listing_id in _preview_cache and _preview_cache[listing_id] is not None:
        return

    image_url = None
    async with _fetch_sem:
        try:
            from agent.browser import get_context
            ctx = await get_context()
            page = await ctx.new_page()
            try:
                await page.goto(listing_url, wait_until="domcontentloaded", timeout=12_000)
                image_url = await page.evaluate("""() => {
                    // og:image — самый надёжный вариант (SEO-тег, всегда в HTML)
                    const og = document.querySelector('meta[property="og:image"]');
                    if (og?.content?.startsWith('http')) return og.content;
                    // Фото в галерее объявления
                    for (const sel of [
                        '.gallery__photo img', '.offer-gallery img',
                        '.a-card__photo-img', 'img[src*="img.krisha.kz"]',
                        'img[data-src*="img.krisha.kz"]'
                    ]) {
                        const el = document.querySelector(sel);
                        const src = el?.src || el?.dataset?.src;
                        if (src?.startsWith('http')) return src;
                    }
                    return null;
                }""")
            finally:
                await page.close()
        except Exception:
            pass

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
