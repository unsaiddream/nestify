"""
Роуты аутентификации: сохранение Gemini токена, логин в Krisha.kz.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.db import get_setting, set_setting

router = APIRouter(prefix="/auth", tags=["auth"])


class GeminiTokenRequest(BaseModel):
    token: str


class KrishaLoginRequest(BaseModel):
    phone: str
    password: str


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


@router.post("/krisha-login")
async def krisha_login(body: KrishaLoginRequest):
    """
    Логин в Krisha.kz через Playwright.
    TODO: реализовать в шаге 3 MVP.
    """
    return {"status": "pending", "message": "Логин через Playwright будет реализован в шаге 3"}


@router.get("/krisha-status")
async def krisha_status():
    """Проверяет статус сессии Krisha.kz."""
    logged_in = await get_setting("krisha_logged_in")
    return {"logged_in": logged_in == "true"}
