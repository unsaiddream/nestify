"""
Nestify — точка входа.
Запускает FastAPI сервер и автоматически открывает браузер.
"""

import subprocess
import sys
import threading
import time
import webbrowser

import uvicorn

HOST = "127.0.0.1"
PORT = 8000
URL  = f"http://{HOST}:{PORT}"


def ensure_playwright_browsers():
    """Устанавливает Chromium при первом запуске (no-op если уже установлен)."""
    try:
        from playwright._impl._driver import compute_driver_executable
        driver = compute_driver_executable()
        result = subprocess.run(
            [str(driver), 'install', 'chromium'],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            print(f"  Предупреждение: playwright install вернул ошибку:\n{result.stderr}")
    except Exception as e:
        print(f"  Предупреждение: не удалось установить Chromium: {e}")


def open_browser():
    """Открывает браузер после небольшой задержки, чтобы сервер успел стартовать."""
    time.sleep(1.2)
    webbrowser.open(URL)


def main():
    print("""
  ╔══════════════════════════════╗
  ║   Nestify  v0.1.0            ║
  ║   Запуск на localhost:8000   ║
  ╚══════════════════════════════╝
""")

    # Проверяем/устанавливаем Chromium (при повторных запусках — мгновенно)
    print("  Проверка Chromium...")
    ensure_playwright_browsers()
    print("  Chromium готов.")

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
