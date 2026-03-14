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
    masked = None
    if token:
        masked = token[:8] + "..." + token[-4:] if len(token) > 12 else token[:4] + "..."
    return {"has_token": token is not None, "masked": masked}


@router.post("/test-gemini")
async def test_gemini():
    """Отправляет тестовый запрос к Gemini API и возвращает результат или ошибку."""
    token = await get_setting("gemini_token")
    if not token:
        return {"status": "error", "message": "Токен не настроен"}
    try:
        import asyncio
        import google.generativeai as genai
        genai.configure(api_key=token)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = await asyncio.to_thread(
            model.generate_content,
            'Ответь одним словом: "работает"'
        )
        return {"status": "ok", "message": f"Gemini отвечает: {response.text.strip()[:100]}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
