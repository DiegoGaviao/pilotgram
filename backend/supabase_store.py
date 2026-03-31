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


def upsert_profile_brief_sync(payload: dict[str, str]) -> None:
    _client().table("pg_profile_brief").upsert(payload).execute()


def get_profile_brief_sync(ig_user_id: str) -> dict | None:
    r = (
        _client()
        .table("pg_profile_brief")
        .select(
            "ig_user_id, niche, target_audience, objective, offer_summary, "
            "preferred_language, tone_style, do_not_use_terms, updated_at"
        )
        .eq("ig_user_id", ig_user_id)
        .limit(1)
        .execute()
    )
    rows = r.data or []
    if not rows:
        return None
    row = rows[0]
    return {
        "ig_user_id": str(row.get("ig_user_id") or ""),
        "niche": str(row.get("niche") or ""),
        "target_audience": str(row.get("target_audience") or ""),
        "objective": str(row.get("objective") or ""),
        "offer_summary": str(row.get("offer_summary") or ""),
        "preferred_language": str(row.get("preferred_language") or ""),
        "tone_style": str(row.get("tone_style") or ""),
        "do_not_use_terms": str(row.get("do_not_use_terms") or ""),
        "updated_at": str(row.get("updated_at") or ""),
    }
