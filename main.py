"""
Nestify — точка входа.
Запускает FastAPI сервер и автоматически открывает браузер.
"""

import os
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

# ──────────────────────────────────────────────────────────────
# 0. PLAYWRIGHT_BROWSERS_PATH — ДОЛЖНО быть установлено ДО
#    любых импортов playwright, иначе замороженный .app ищет
#    браузеры внутри себя (read-only bundle) и крашится.
# ──────────────────────────────────────────────────────────────
_browsers_path = Path.home() / "Library" / "Application Support" / "Nestify" / "browsers"
_browsers_path.mkdir(parents=True, exist_ok=True)
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_browsers_path)

# ──────────────────────────────────────────────────────────────
# 1. Логирование в файл — чтобы видеть краши при запуске из .app
# ──────────────────────────────────────────────────────────────
LOG_DIR = Path.home() / "Library" / "Logs" / "Nestify"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "nestify.log"

import logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("nestify")

# ──────────────────────────────────────────────────────────────
# 2. CWD — при запуске из .app нужно переключиться в правильную папку
# ──────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    # В frozen-режиме ресурсы лежат в sys._MEIPASS
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

os.chdir(BASE_DIR)
log.debug(f"BASE_DIR = {BASE_DIR}")
log.debug(f"CWD = {os.getcwd()}")

# ──────────────────────────────────────────────────────────────
# 3. PATH — Finder запускает с урезанным PATH (нет brew, node, etc.)
# ──────────────────────────────────────────────────────────────
extra_paths = [
    "/opt/homebrew/bin",       # Apple Silicon Homebrew
    "/usr/local/bin",          # Intel Homebrew
    "/usr/bin",
    "/bin",
]
current_path = os.environ.get("PATH", "")
os.environ["PATH"] = ":".join(extra_paths) + (":" + current_path if current_path else "")

HOST = "127.0.0.1"
PORT = 8000
URL  = f"http://{HOST}:{PORT}"


def ensure_playwright_browsers():
    """Устанавливает Chromium при первом запуске (no-op если уже установлен)."""
    log.info(f"PLAYWRIGHT_BROWSERS_PATH = {os.environ.get('PLAYWRIGHT_BROWSERS_PATH')}")
    try:
        from playwright._impl._driver import compute_driver_executable
        driver = compute_driver_executable()
        log.info(f"Playwright driver: {driver}")
        log.info("Запускаем playwright install chromium...")
        result = subprocess.run(
            [str(driver), "install", "chromium"],
            capture_output=True, text=True, timeout=300,
            env=os.environ,  # передаём PLAYWRIGHT_BROWSERS_PATH в subprocess
        )
        log.debug(f"stdout: {result.stdout}")
        if result.returncode != 0:
            log.warning(f"playwright install stderr:\n{result.stderr}")
        else:
            log.info("Chromium готов.")
    except Exception as e:
        log.warning(f"Не удалось установить Chromium: {e}")


def open_browser():
    """Открывает браузер после небольшой задержки, чтобы сервер успел стартовать."""
    time.sleep(1.5)
    webbrowser.open(URL)


def main():
    log.info("Nestify v0.1.0 запускается...")

    # Проверяем/устанавливаем Chromium
    ensure_playwright_browsers()

    # Открываем браузер в отдельном потоке, не блокируя сервер
    threading.Thread(target=open_browser, daemon=True).start()

    # Импортируем app напрямую — строковый импорт не работает в frozen-режиме
    try:
        from api.server import app as fastapi_app
    except Exception:
        log.error("Не удалось импортировать api.server:\n" + traceback.format_exc())
        sys.exit(1)

    log.info(f"Сервер запускается на {URL}")

    import uvicorn
    uvicorn.run(
        fastapi_app,
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.error("Неожиданный краш:\n" + traceback.format_exc())
        sys.exit(1)
