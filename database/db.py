"""
Модуль для работы с локальной SQLite базой данных.
Инициализирует таблицы и предоставляет базовые операции.
"""

import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "nestify.db"


async def init_db():
    """Создаёт все таблицы если их ещё нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS clients (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                district   TEXT,
                budget_min INTEGER,
                budget_max INTEGER,
                area_min   INTEGER,
                area_max   INTEGER,
                rooms      TEXT,
                deal_type  TEXT DEFAULT 'buy',
                active     INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS listings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id   INTEGER REFERENCES clients(id),
                krisha_id   TEXT UNIQUE,
                url         TEXT,
                title       TEXT,
                price       INTEGER,
                area        REAL,
                rooms       INTEGER,
                district    TEXT,
                description TEXT,
                status      TEXT DEFAULT 'new',
                ai_score    INTEGER,
                ai_comment  TEXT,
                found_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER REFERENCES listings(id),
                text       TEXT,
                sent_at    TEXT DEFAULT (datetime('now')),
                status     TEXT DEFAULT 'sent'
            );

            CREATE TABLE IF NOT EXISTS actions_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                action     TEXT NOT NULL,
                details    TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        await db.commit()

        # Миграции: добавляем новые колонки если их нет (для существующих БД)
        migrations = [
            "ALTER TABLE clients ADD COLUMN area_polygon TEXT",
            "ALTER TABLE clients ADD COLUMN message_template TEXT",
            "ALTER TABLE clients ADD COLUMN emoji TEXT DEFAULT '🏠'",
            "ALTER TABLE listings ADD COLUMN thumbnail TEXT",
        ]
        for sql in migrations:
            try:
                await db.execute(sql)
                await db.commit()
            except Exception:
                pass  # колонка уже существует


async def get_setting(key: str) -> str | None:
    """Читает значение настройки из БД."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def set_setting(key: str, value: str):
    """Сохраняет или обновляет настройку в БД."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await db.commit()
