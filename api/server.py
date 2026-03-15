"""
FastAPI приложение — главный сервер Nestify.
Регистрирует роуты и отдаёт статические файлы UI.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from database.db import init_db
from api.routes import auth, agent, listings

UI_DIR = Path(__file__).parent.parent / "ui"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация БД при старте сервера."""
    await init_db()
    yield


app = FastAPI(title="Nestify", version="0.1.0", lifespan=lifespan)

# Регистрируем роуты API
app.include_router(auth.router, prefix="/api")
app.include_router(agent.router, prefix="/api")
app.include_router(listings.router, prefix="/api")

# Статические файлы UI (CSS, JS)
app.mount("/static", StaticFiles(directory=UI_DIR), name="static")


@app.get("/")
async def root():
    """Отдаёт главную страницу — без кеша, чтобы браузер всегда брал свежий JS/CSS."""
    return FileResponse(
        UI_DIR / "index.html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/static/app.js")
async def serve_js():
    """JS без кеша."""
    return FileResponse(
        UI_DIR / "app.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/static/styles.css")
async def serve_css():
    """CSS без кеша."""
    return FileResponse(
        UI_DIR / "styles.css",
        media_type="text/css",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
