"""
Роуты аутентификации: сохранение Gemini токена.
Логин в Krisha.kz не нужен — агент использует браузер с уже открытой сессией.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.db import get_setting, set_setting

router = APIRouter(prefix="/auth", tags=["auth"])


class GeminiTokenRequest(BaseModel):
    token: str


@router.post("/gemini-token")
async def save_gemini_token(body: GeminiTokenRequest):
    """Сохраняет Gemini API токен локально в SQLite."""
    if not body.token.strip():
        raise HTTPException(status_code=400, detail="Токен не может быть пустым")
    await set_setting("gemini_token", body.token.strip())
    return {"status": "ok", "message": "Токен сохранён"}


@router.get("/gemini-token/status")
async def gemini_token_status():
    """Проверяет, сохранён ли Gemini токен."""
    token = await get_setting("gemini_token")
    return {"has_token": token is not None}
