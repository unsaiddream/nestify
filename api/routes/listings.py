"""
Роуты для получения объявлений и клиентов из БД.
"""

import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.db import DB_PATH


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
    """Возвращает thumbnail из БД (заполняется скрапером при сканировании)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT thumbnail FROM listings WHERE id = ?", (listing_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")
    return {"image_url": row[0]}


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
