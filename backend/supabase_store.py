"""Persistência do token Meta na Supabase (service role). Tabela: pg_oauth_solo."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from supabase import create_client

from config import settings

logger = logging.getLogger(__name__)

SOLO_ID = "solo"


def _client():
    return create_client(
        settings.supabase_url.strip(),
        settings.supabase_service_role_key.strip(),
    )


def save_solo_token_sync(access_token: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    _client().table("pg_oauth_solo").upsert(
        {"id": SOLO_ID, "access_token": access_token, "updated_at": now}
    ).execute()


def get_solo_token_sync() -> str | None:
    r = _client().table("pg_oauth_solo").select("access_token").eq("id", SOLO_ID).limit(1).execute()
    rows = r.data or []
    if not rows:
        return None
    return str(rows[0]["access_token"])


def get_solo_session_meta_sync() -> dict | None:
    r = (
        _client()
        .table("pg_oauth_solo")
        .select("access_token, updated_at")
        .eq("id", SOLO_ID)
        .limit(1)
        .execute()
    )
    rows = r.data or []
    if not rows:
        return None
    tok = rows[0]["access_token"]
    preview = f"{tok[:8]}…{tok[-4:]}" if len(tok) > 12 else "(curto)"
    return {"connected": True, "token_preview": preview, "updated_at": rows[0].get("updated_at")}


def clear_solo_session_sync() -> None:
    _client().table("pg_oauth_solo").delete().eq("id", SOLO_ID).execute()
