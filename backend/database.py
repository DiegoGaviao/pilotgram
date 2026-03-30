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

CREATE TABLE IF NOT EXISTS content_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ig_user_id TEXT NOT NULL,
    source_media_id TEXT,
    suggestion_text TEXT NOT NULL,
    rationale TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    approved_at TEXT
);

CREATE TABLE IF NOT EXISTS profile_dna (
    ig_user_id TEXT PRIMARY KEY,
    themes TEXT NOT NULL,
    tone_hint TEXT NOT NULL,
    cta_hint TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _db_path() -> Path:
    return Path(settings.pilotgram_sqlite_path).expanduser().resolve()


async def init_db() -> None:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as db:
        await db.executescript(SCHEMA)
        await db.commit()
    if settings.use_supabase_for_token:
        logger.info("Token store: Supabase (pg_oauth_solo) + SQLite para robôs em %s", path)
    else:
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


async def save_content_suggestions(
    ig_user_id: str,
    suggestions: list[dict[str, str | None]],
) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []
    async with aiosqlite.connect(_db_path()) as db:
        for s in suggestions:
            cur = await db.execute(
                """
                INSERT INTO content_suggestions (
                    ig_user_id, source_media_id, suggestion_text, rationale, status, created_at
                ) VALUES (?, ?, ?, ?, 'pending', ?)
                """,
                (
                    ig_user_id,
                    s.get("source_media_id"),
                    s.get("suggestion_text") or "",
                    s.get("rationale"),
                    now,
                ),
            )
            rows.append(
                {
                    "id": int(cur.lastrowid),
                    "ig_user_id": ig_user_id,
                    "source_media_id": s.get("source_media_id"),
                    "suggestion_text": s.get("suggestion_text") or "",
                    "rationale": s.get("rationale"),
                    "status": "pending",
                    "created_at": now,
                    "approved_at": None,
                }
            )
        await db.commit()
    return rows


async def list_content_suggestions(ig_user_id: str) -> list[dict]:
    async with aiosqlite.connect(_db_path()) as db:
        async with db.execute(
            """
            SELECT id, ig_user_id, source_media_id, suggestion_text, rationale, status, created_at, approved_at
            FROM content_suggestions
            WHERE ig_user_id = ?
            ORDER BY id DESC
            LIMIT 50
            """,
            (ig_user_id,),
        ) as cur:
            items = []
            async for row in cur:
                items.append(
                    {
                        "id": int(row[0]),
                        "ig_user_id": row[1],
                        "source_media_id": row[2],
                        "suggestion_text": row[3],
                        "rationale": row[4],
                        "status": row[5],
                        "created_at": row[6],
                        "approved_at": row[7],
                    }
                )
            return items


async def approve_content_suggestion(suggestion_id: int) -> dict | None:
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            """
            UPDATE content_suggestions
            SET status = 'approved', approved_at = ?
            WHERE id = ?
            """,
            (now, suggestion_id),
        )
        await db.commit()
        async with db.execute(
            """
            SELECT id, ig_user_id, source_media_id, suggestion_text, rationale, status, created_at, approved_at
            FROM content_suggestions
            WHERE id = ?
            """,
            (suggestion_id,),
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return {
                "id": int(row[0]),
                "ig_user_id": row[1],
                "source_media_id": row[2],
                "suggestion_text": row[3],
                "rationale": row[4],
                "status": row[5],
                "created_at": row[6],
                "approved_at": row[7],
            }


async def upsert_profile_dna(
    ig_user_id: str,
    themes: list[str],
    tone_hint: str,
    cta_hint: str,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    themes_csv = ",".join([t.strip() for t in themes if t.strip()])
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            """
            INSERT INTO profile_dna (ig_user_id, themes, tone_hint, cta_hint, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(ig_user_id) DO UPDATE SET
              themes = excluded.themes,
              tone_hint = excluded.tone_hint,
              cta_hint = excluded.cta_hint,
              updated_at = excluded.updated_at
            """,
            (ig_user_id, themes_csv, tone_hint, cta_hint, now),
        )
        await db.commit()
    return {
        "ig_user_id": ig_user_id,
        "themes": [x for x in themes_csv.split(",") if x],
        "tone_hint": tone_hint,
        "cta_hint": cta_hint,
        "updated_at": now,
    }


async def get_profile_dna(ig_user_id: str) -> dict | None:
    async with aiosqlite.connect(_db_path()) as db:
        async with db.execute(
            """
            SELECT ig_user_id, themes, tone_hint, cta_hint, updated_at
            FROM profile_dna
            WHERE ig_user_id = ?
            """,
            (ig_user_id,),
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            themes = [x for x in str(row[1]).split(",") if x]
            return {
                "ig_user_id": str(row[0]),
                "themes": themes,
                "tone_hint": str(row[2]),
                "cta_hint": str(row[3]),
                "updated_at": str(row[4]),
            }
