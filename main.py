"""
Nestify — точка входа.
Запускает FastAPI сервер и автоматически открывает браузер.
"""

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Для PyInstaller: указываем Playwright где искать bundled браузеры
if getattr(sys, 'frozen', False):
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(Path(sys._MEIPASS) / 'playwright-browsers')

import uvicorn  # noqa: E402 — импорт после установки env vars

HOST = "127.0.0.1"
PORT = 8000
URL  = f"http://{HOST}:{PORT}"


def open_browser():
    """Открывает браузер после небольшой задержки, чтобы сервер успел стартовать."""
    time.sleep(1.2)
    webbrowser.open(URL)


def main():
    print(f"""
  ╔══════════════════════════════╗
  ║   🏠  Nestify  v0.1.0        ║
  ║   Запуск на {URL}   ║
  ╚══════════════════════════════╝
""")

    # Открываем браузер в отдельном потоке, не блокируя сервер
    threading.Thread(target=open_browser, daemon=True).start()

    # Запускаем FastAPI/uvicorn
    uvicorn.run(
        "api.server:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
