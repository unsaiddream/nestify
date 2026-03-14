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


AVAILABLE_MODELS = [
    "gemini-2.5-pro-exp-03-25",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash-exp",
    "gemini-2.0-pro-exp",
    "gemini-2.0-pro-exp-02-05",
]


class GeminiModelRequest(BaseModel):
    model: str


@router.post("/gemini-model")
async def save_gemini_model(body: GeminiModelRequest):
    """Сохраняет выбранную модель Gemini."""
    await set_setting("gemini_model", body.model.strip())
    return {"status": "ok", "model": body.model}


@router.get("/gemini-model")
async def get_gemini_model():
    """Возвращает текущую модель Gemini."""
    model = await get_setting("gemini_model") or "gemini-2.0-flash"
    return {"model": model, "available": AVAILABLE_MODELS}


@router.post("/test-gemini")
async def test_gemini():
    """Отправляет тестовый запрос к Gemini API и возвращает результат или ошибку."""
    token = await get_setting("gemini_token")
    if not token:
        return {"status": "error", "message": "Токен не настроен"}
    model_name = await get_setting("gemini_model") or "gemini-2.0-flash"
    try:
        import asyncio
        import google.generativeai as genai
        genai.configure(api_key=token)
        model = genai.GenerativeModel(model_name)
        response = await asyncio.to_thread(
            model.generate_content,
            'Ответь одним словом: "работает"'
        )
        return {"status": "ok", "message": f"[{model_name}] {response.text.strip()[:100]}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
