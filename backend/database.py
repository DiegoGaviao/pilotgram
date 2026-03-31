"""Token Meta: Supabase (produção/VPS) ou SQLite (dev sem Supabase)."""

from __future__ import annotations

import asyncio
import logging
import secrets
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

CREATE TABLE IF NOT EXISTS profile_brief (
    ig_user_id TEXT PRIMARY KEY,
    niche TEXT NOT NULL,
    target_audience TEXT NOT NULL,
    objective TEXT NOT NULL,
    offer_summary TEXT NOT NULL,
    preferred_language TEXT NOT NULL,
    tone_style TEXT NOT NULL,
    do_not_use_terms TEXT NOT NULL,
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
        # Migração leve para ambientes que já tinham a tabela criada.
        await _ensure_content_suggestions_columns(db)
        await _ensure_profile_brief_columns(db)
        await _ensure_profile_dna_columns(db)
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


async def _ensure_content_suggestions_columns(db: aiosqlite.Connection) -> None:
    async with db.execute("PRAGMA table_info(content_suggestions)") as cur:
        cols = {str(row[1]) async for row in cur}
    additions: list[tuple[str, str]] = [
        ("creative_prompt", "TEXT"),
        ("creative_image_url", "TEXT"),
        ("creative_fetch_token", "TEXT"),
        ("suggested_date", "TEXT"),
        ("frequency_per_week", "INTEGER"),
        ("focus_topic", "TEXT"),
        ("language", "TEXT"),
    ]
    for name, col_type in additions:
        if name not in cols:
            await db.execute(f"ALTER TABLE content_suggestions ADD COLUMN {name} {col_type}")


async def _ensure_profile_dna_columns(db: aiosqlite.Connection) -> None:
    async with db.execute("PRAGMA table_info(profile_dna)") as cur:
        cols = {str(row[1]) async for row in cur}
    if "language_hint" not in cols:
        await db.execute(
            "ALTER TABLE profile_dna ADD COLUMN language_hint TEXT NOT NULL DEFAULT 'pt'"
        )


async def _ensure_profile_brief_columns(db: aiosqlite.Connection) -> None:
    async with db.execute("PRAGMA table_info(profile_brief)") as cur:
        cols = {str(row[1]) async for row in cur}
    additions: list[tuple[str, str]] = [
        ("niche", "TEXT NOT NULL DEFAULT ''"),
        ("target_audience", "TEXT NOT NULL DEFAULT ''"),
        ("objective", "TEXT NOT NULL DEFAULT ''"),
        ("offer_summary", "TEXT NOT NULL DEFAULT ''"),
        ("preferred_language", "TEXT NOT NULL DEFAULT ''"),
        ("tone_style", "TEXT NOT NULL DEFAULT ''"),
        ("do_not_use_terms", "TEXT NOT NULL DEFAULT ''"),
        ("updated_at", "TEXT NOT NULL DEFAULT ''"),
    ]
    for name, col_type in additions:
        if name not in cols:
            await db.execute(f"ALTER TABLE profile_brief ADD COLUMN {name} {col_type}")


async def save_content_suggestions(
    ig_user_id: str,
    suggestions: list[dict[str, str | None]],
    *,
    public_api_base: str = "",
) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    base = (public_api_base or "").strip().rstrip("/")
    rows: list[dict] = []
    async with aiosqlite.connect(_db_path()) as db:
        for s in suggestions:
            token = secrets.token_urlsafe(20)
            hosted_url = f"{base}/api/v1/meta/creatives/{token}" if base else None
            cur = await db.execute(
                """
                INSERT INTO content_suggestions (
                    ig_user_id, source_media_id, suggestion_text, rationale, status, created_at,
                    creative_prompt, creative_image_url, creative_fetch_token, suggested_date,
                    frequency_per_week, focus_topic, language
                ) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ig_user_id,
                    s.get("source_media_id"),
                    s.get("suggestion_text") or "",
                    s.get("rationale"),
                    now,
                    s.get("creative_prompt"),
                    hosted_url,
                    token,
                    s.get("suggested_date"),
                    s.get("frequency_per_week"),
                    s.get("focus_topic"),
                    s.get("language"),
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
                    "creative_prompt": s.get("creative_prompt"),
                    "creative_image_url": hosted_url,
                    "creative_fetch_token": token,
                    "suggested_date": s.get("suggested_date"),
                    "frequency_per_week": s.get("frequency_per_week"),
                    "focus_topic": s.get("focus_topic"),
                    "language": s.get("language"),
                }
            )
        await db.commit()
    return rows


async def list_content_suggestions(ig_user_id: str) -> list[dict]:
    async with aiosqlite.connect(_db_path()) as db:
        async with db.execute(
            """
            SELECT id, ig_user_id, source_media_id, suggestion_text, rationale, status, created_at, approved_at,
                   creative_prompt, creative_image_url, creative_fetch_token, suggested_date, frequency_per_week,
                   focus_topic, language
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
                        "creative_prompt": row[8],
                        "creative_image_url": row[9],
                        "creative_fetch_token": row[10],
                        "suggested_date": row[11],
                        "frequency_per_week": row[12],
                        "focus_topic": row[13],
                        "language": row[14],
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
            SELECT id, ig_user_id, source_media_id, suggestion_text, rationale, status, created_at, approved_at,
                   creative_prompt, creative_image_url, creative_fetch_token, suggested_date, frequency_per_week,
                   focus_topic, language
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
                "creative_prompt": row[8],
                "creative_image_url": row[9],
                "creative_fetch_token": row[10],
                "suggested_date": row[11],
                "frequency_per_week": row[12],
                "focus_topic": row[13],
                "language": row[14],
            }


async def get_suggestion_creative_context(token: str) -> dict | None:
    async with aiosqlite.connect(_db_path()) as db:
        async with db.execute(
            "SELECT id, creative_prompt FROM content_suggestions WHERE creative_fetch_token = ?",
            (token,),
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return {"id": int(row[0]), "creative_prompt": str(row[1] or "")}


async def update_suggestion_creative_image_url(suggestion_id: int, image_url: str) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            "UPDATE content_suggestions SET creative_image_url = ? WHERE id = ?",
            (image_url, suggestion_id),
        )
        await db.commit()


async def upsert_profile_dna(
    ig_user_id: str,
    themes: list[str],
    tone_hint: str,
    cta_hint: str,
    language_hint: str = "pt",
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    themes_csv = ",".join([t.strip() for t in themes if t.strip()])
    lang = (language_hint or "pt").strip()[:8] or "pt"
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            """
            INSERT INTO profile_dna (ig_user_id, themes, tone_hint, cta_hint, language_hint, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ig_user_id) DO UPDATE SET
              themes = excluded.themes,
              tone_hint = excluded.tone_hint,
              cta_hint = excluded.cta_hint,
              language_hint = excluded.language_hint,
              updated_at = excluded.updated_at
            """,
            (ig_user_id, themes_csv, tone_hint, cta_hint, lang, now),
        )
        await db.commit()
    return {
        "ig_user_id": ig_user_id,
        "themes": [x for x in themes_csv.split(",") if x],
        "tone_hint": tone_hint,
        "cta_hint": cta_hint,
        "language_hint": lang,
        "updated_at": now,
    }


async def get_profile_dna(ig_user_id: str) -> dict | None:
    async with aiosqlite.connect(_db_path()) as db:
        async with db.execute(
            """
            SELECT ig_user_id, themes, tone_hint, cta_hint, language_hint, updated_at
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
                "language_hint": str(row[4] or "pt"),
                "updated_at": str(row[5]),
            }


async def upsert_profile_brief(
    ig_user_id: str,
    niche: str,
    target_audience: str,
    objective: str,
    offer_summary: str,
    preferred_language: str,
    tone_style: str,
    do_not_use_terms: str,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "ig_user_id": ig_user_id,
        "niche": niche.strip(),
        "target_audience": target_audience.strip(),
        "objective": objective.strip(),
        "offer_summary": offer_summary.strip(),
        "preferred_language": preferred_language.strip(),
        "tone_style": tone_style.strip(),
        "do_not_use_terms": do_not_use_terms.strip(),
        "updated_at": now,
    }
    if settings.use_supabase_for_token:
        from supabase_store import upsert_profile_brief_sync

        await asyncio.to_thread(upsert_profile_brief_sync, payload)
        return payload
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            """
            INSERT INTO profile_brief (
              ig_user_id, niche, target_audience, objective, offer_summary,
              preferred_language, tone_style, do_not_use_terms, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ig_user_id) DO UPDATE SET
              niche = excluded.niche,
              target_audience = excluded.target_audience,
              objective = excluded.objective,
              offer_summary = excluded.offer_summary,
              preferred_language = excluded.preferred_language,
              tone_style = excluded.tone_style,
              do_not_use_terms = excluded.do_not_use_terms,
              updated_at = excluded.updated_at
            """,
            (
                ig_user_id,
                niche.strip(),
                target_audience.strip(),
                objective.strip(),
                offer_summary.strip(),
                preferred_language.strip(),
                tone_style.strip(),
                do_not_use_terms.strip(),
                now,
            ),
        )
        await db.commit()
    return payload


async def get_profile_brief(ig_user_id: str) -> dict | None:
    if settings.use_supabase_for_token:
        from supabase_store import get_profile_brief_sync

        return await asyncio.to_thread(get_profile_brief_sync, ig_user_id)
    async with aiosqlite.connect(_db_path()) as db:
        async with db.execute(
            """
            SELECT ig_user_id, niche, target_audience, objective, offer_summary,
                   preferred_language, tone_style, do_not_use_terms, updated_at
            FROM profile_brief
            WHERE ig_user_id = ?
            """,
            (ig_user_id,),
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return {
                "ig_user_id": str(row[0]),
                "niche": str(row[1]),
                "target_audience": str(row[2]),
                "objective": str(row[3]),
                "offer_summary": str(row[4]),
                "preferred_language": str(row[5]),
                "tone_style": str(row[6]),
                "do_not_use_terms": str(row[7]),
                "updated_at": str(row[8]),
            }
