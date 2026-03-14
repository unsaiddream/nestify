"""
Главный цикл агента.
Для каждого активного клиента: ищет объявления → анализирует Gemini → сохраняет в БД.
"""

import asyncio
import logging

import aiosqlite

from agent.browser import search_listings, send_message
from agent.gemini import analyze_listing
from database.db import DB_PATH

logger = logging.getLogger("nestify.analyzer")

# Интервал между полными проходами (в секундах)
SCAN_INTERVAL = 10 * 60  # 10 минут


async def run_agent(stop_event: asyncio.Event):
    """
    Основной цикл агента. Работает пока stop_event не установлен.
    Каждые SCAN_INTERVAL секунд проходит по всем клиентам.
    """
    logger.info("Агент запущен")
    while not stop_event.is_set():
        try:
            await _scan_all_clients()
        except Exception as e:
            logger.error(f"Ошибка в цикле агента: {e}")

        # Ждём следующего прохода с возможностью прерваться
        try:
            await asyncio.wait_for(
                asyncio.shield(stop_event.wait()),
                timeout=SCAN_INTERVAL,
            )
        except asyncio.TimeoutError:
            pass  # Таймаут вышел — делаем следующий проход

    logger.info("Агент остановлен")


async def _scan_all_clients():
    """Проходит по всем активным клиентам и обрабатывает объявления."""
    clients = await _get_active_clients()
    if not clients:
        logger.info("Нет активных клиентов, пропускаем проход")
        return

    for client in clients:
        if not client.get("active"):
            continue
        logger.info(f"Сканируем объявления для клиента: {client['name']}")
        await _process_client(client)
        await asyncio.sleep(3)  # пауза между клиентами


async def _process_client(client: dict):
    """Ищет и анализирует объявления для одного клиента."""
    # Поиск объявлений через Playwright
    try:
        raw_listings = await search_listings(client, max_pages=2)
    except Exception as e:
        logger.error(f"Ошибка поиска для клиента {client['name']}: {e}")
        await _log_action("search_error", f"Клиент {client['name']}: {e}")
        return

    logger.info(f"Найдено {len(raw_listings)} объявлений для {client['name']}")
    await _log_action("search", f"Клиент {client['name']}: найдено {len(raw_listings)} объявлений")

    new_count = 0
    for raw in raw_listings:
        # Пропускаем уже известные объявления
        if await _listing_exists(raw.krisha_id):
            continue

        # Сохраняем как новое
        listing_id = await _save_listing(raw, client["id"])
        new_count += 1

        # Анализ через Gemini
        listing_dict = {
            "title": raw.title,
            "price": raw.price,
            "area": raw.area,
            "rooms": raw.rooms,
            "district": raw.district,
            "description": raw.description,
            "url": raw.url,
        }
        try:
            analysis = await analyze_listing(listing_dict, client)
            status = "approved" if analysis.approved else "rejected"
            await _update_listing_analysis(listing_id, analysis.score, analysis.comment, status)

            logger.info(
                f"  [{status.upper()}] {raw.title[:50]} | score={analysis.score} | {analysis.comment[:60]}"
            )
            await _log_action(
                "analyze",
                f"Объявление {raw.krisha_id}: score={analysis.score}, {status}",
            )

            # Отправляем сообщение продавцу если объявление одобрено
            if analysis.approved and analysis.message:
                await asyncio.sleep(2)  # пауза перед отправкой
                ok = await send_message(raw.url, analysis.message)
                if ok:
                    await _save_message(listing_id, analysis.message)
                    await _update_listing_status(listing_id, "messaged")
                    await _log_action(
                        "send_message",
                        f"Объявление {raw.krisha_id}: сообщение отправлено",
                    )
                    logger.info(f"  💬 Сообщение отправлено: {raw.krisha_id}")
                else:
                    await _log_action(
                        "message_error",
                        f"Объявление {raw.krisha_id}: не удалось отправить сообщение",
                    )
                    logger.warning(f"  ⚠️ Не удалось отправить: {raw.krisha_id}")

        except Exception as e:
            logger.error(f"Ошибка Gemini для {raw.krisha_id}: {e}")

        # Задержка между запросами к Gemini — не спамим API
        await asyncio.sleep(1.5)

    logger.info(f"Новых объявлений для {client['name']}: {new_count}")


# ── Работа с БД ────────────────────────────────────────────────────────────────

async def _get_active_clients() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM clients WHERE active = 1") as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def _listing_exists(krisha_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM listings WHERE krisha_id = ?", (krisha_id,)
        ) as cur:
            return await cur.fetchone() is not None


async def _save_listing(raw, client_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT OR IGNORE INTO listings
               (client_id, krisha_id, url, title, price, area, rooms, district, description, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')""",
            (client_id, raw.krisha_id, raw.url, raw.title,
             raw.price, raw.area, raw.rooms, raw.district, raw.description),
        )
        await db.commit()
        return cur.lastrowid


async def _update_listing_analysis(listing_id: int, score: int, comment: str, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE listings SET ai_score = ?, ai_comment = ?, status = ? WHERE id = ?",
            (score, comment, status, listing_id),
        )
        await db.commit()


async def _save_message(listing_id: int, text: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (listing_id, text, status) VALUES (?, ?, 'sent')",
            (listing_id, text),
        )
        await db.commit()


async def _update_listing_status(listing_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE listings SET status = ? WHERE id = ?",
            (status, listing_id),
        )
        await db.commit()


async def _log_action(action: str, details: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO actions_log (action, details) VALUES (?, ?)",
            (action, details),
        )
        await db.commit()
