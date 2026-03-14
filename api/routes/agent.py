"""
Роуты управления агентом: запуск, остановка, статус.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/agent", tags=["agent"])

# Состояние агента (в памяти, для MVP достаточно)
_agent_running = False


@router.post("/start")
async def start_agent():
    """
    Запускает агента.
    TODO: реализовать полную логику в шагах 4–6 MVP.
    """
    global _agent_running
    _agent_running = True
    return {"status": "started"}


@router.post("/stop")
async def stop_agent():
    """Останавливает агента."""
    global _agent_running
    _agent_running = False
    return {"status": "stopped"}


@router.get("/status")
async def agent_status():
    """Возвращает текущий статус агента."""
    return {"running": _agent_running}
