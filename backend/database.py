"""Token Meta: Supabase (produção/VPS) ou SQLite (dev sem Supabase)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from config import settings

logger = logging.getLogger(__name__)

SOLO_ID = "local"

SCHEMA = """
CREATE TABLE IF NOT EXISTS solo_session (
    id TEXT PRIMARY KEY CHECK (id = 'local'),
    access_token TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _db_path() -> Path:
    return Path(settings.pilotgram_sqlite_path).expanduser().resolve()


async def init_db() -> None:
    if settings.use_supabase_for_token:
        logger.info("Token store: Supabase (pg_oauth_solo)")
        return
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as db:
        await db.executescript(SCHEMA)
        await db.commit()
    logger.info("SQLite pronto em %s", path)


async def save_solo_token(access_token: str) -> None:
    if settings.use_supabase_for_token:
        from supabase_store import save_solo_token_sync

        await asyncio.to_thread(save_solo_token_sync, access_token)
        return
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            """
            INSERT INTO solo_session (id, access_token, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                access_token = excluded.access_token,
                updated_at = excluded.updated_at
            """,
            (SOLO_ID, access_token, now),
        )
        await db.commit()


async def get_solo_token() -> str | None:
    if settings.use_supabase_for_token:
        from supabase_store import get_solo_token_sync

        return await asyncio.to_thread(get_solo_token_sync)
    async with aiosqlite.connect(_db_path()) as db:
        async with db.execute(
            "SELECT access_token FROM solo_session WHERE id = ?",
            (SOLO_ID,),
        ) as cur:
            row = await cur.fetchone()
            return str(row[0]) if row else None


async def get_solo_session_meta() -> dict | None:
    if settings.use_supabase_for_token:
        from supabase_store import get_solo_session_meta_sync

        return await asyncio.to_thread(get_solo_session_meta_sync)
    async with aiosqlite.connect(_db_path()) as db:
        async with db.execute(
            "SELECT access_token, updated_at FROM solo_session WHERE id = ?",
            (SOLO_ID,),
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            tok = row[0]
            preview = f"{tok[:8]}…{tok[-4:]}" if len(tok) > 12 else "(curto)"
            return {"connected": True, "token_preview": preview, "updated_at": row[1]}


async def clear_solo_session() -> None:
    if settings.use_supabase_for_token:
        from supabase_store import clear_solo_session_sync

        await asyncio.to_thread(clear_solo_session_sync)
        return
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("DELETE FROM solo_session WHERE id = ?", (SOLO_ID,))
        await db.commit()
