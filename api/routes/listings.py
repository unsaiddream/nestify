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
    """Возвращает список объявлений из БД."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if client_id:
            async with db.execute(
                "SELECT * FROM listings WHERE client_id = ? ORDER BY found_at DESC LIMIT ?",
                (client_id, limit),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM listings ORDER BY found_at DESC LIMIT ?", (limit,)
            ) as cur:
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
            """INSERT INTO clients (name, district, budget_min, budget_max, area_min, area_max, rooms, deal_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (body.name, body.district, body.budget_min, body.budget_max,
             body.area_min, body.area_max, body.rooms, body.deal_type),
        )
        await db.commit()
        return {"id": cur.lastrowid, "name": body.name}


@router.delete("/clients/{client_id}")
async def delete_client(client_id: int):
    """Деактивирует клиента (soft delete)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE clients SET active = 0 WHERE id = ?", (client_id,))
        await db.commit()
    return {"status": "ok"}
