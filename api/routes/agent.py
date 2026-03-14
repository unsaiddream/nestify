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


@router.post("/start")
async def start_agent():
    """Запускает агента в фоновой asyncio-задаче."""
    global _stop_event, _task

    if _task and not _task.done():
        return {"status": "already_running"}

    # Импортируем здесь чтобы избежать циклических импортов
    from agent.analyzer import run_agent

    _stop_event = asyncio.Event()
    _task = asyncio.create_task(run_agent(_stop_event))
    logger.info("Агент запущен")
    return {"status": "started"}


@router.post("/stop")
async def stop_agent():
    """Останавливает агента."""
    global _stop_event, _task

    if _stop_event:
        _stop_event.set()

    if _task and not _task.done():
        try:
            await asyncio.wait_for(_task, timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            _task.cancel()

    _task = None
    _stop_event = None
    logger.info("Агент остановлен")
    return {"status": "stopped"}


@router.get("/status")
async def agent_status():
    """Возвращает текущий статус агента."""
    running = bool(_task and not _task.done())
    return {"running": running}


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
