"""
OAuth Meta + endpoints para listar páginas/IG e sincronizar mídias.

Token: Supabase (`pilotgram_oauth_solo`) ou SQLite local.
"""

from __future__ import annotations

import logging
import secrets
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import clear_solo_session, get_solo_session_meta, get_solo_token, save_solo_token
from services import meta_graph as graph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/meta", tags=["meta"])

# state OAuth (curto prazo; não precisa persistir)
_dev_state_to_user: dict[str, str] = {}


class AuthorizeUrlResponse(BaseModel):
    url: str
    state: str


class OAuthCallbackResponse(BaseModel):
    token_type: str
    long_lived: bool
    # Não devolver token completo em produção; aqui para você testar no Postman.
    access_token_preview: str


class CodeExchangeBody(BaseModel):
    code: str
    state: str | None = None


class PageIgItem(BaseModel):
    page_id: str
    page_name: str
    ig_user_id: str | None
    ig_username: str | None


@router.get("/oauth/authorize-url", response_model=AuthorizeUrlResponse)
async def oauth_authorize_url() -> AuthorizeUrlResponse:
    state = secrets.token_urlsafe(24)
    _dev_state_to_user[state] = "solo"
    url = graph.oauth_authorize_url(state)
    return AuthorizeUrlResponse(url=url, state=state)


async def _complete_oauth(code: str, state: str | None) -> OAuthCallbackResponse:
    if state:
        if state not in _dev_state_to_user:
            raise HTTPException(status_code=400, detail="state inválido ou expirado")
        _dev_state_to_user.pop(state)
    else:
        logger.warning("OAuth sem state — aceito só para dev local")
    try:
        short = await graph.exchange_code_for_short_lived_token(code)
        short_token = short.get("access_token")
        if not short_token:
            raise HTTPException(status_code=400, detail=f"resposta sem token: {short}")
        long_resp = await graph.exchange_for_long_lived_user_token(short_token)
        token = long_resp.get("access_token", short_token)
        await save_solo_token(token)
        preview = f"{token[:8]}…{token[-4:]}" if len(token) > 12 else "(curto)"
        return OAuthCallbackResponse(
            token_type="user",
            long_lived=bool(long_resp.get("access_token")),
            access_token_preview=preview,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("oauth")
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/oauth/exchange", response_model=OAuthCallbackResponse)
async def oauth_exchange(body: CodeExchangeBody) -> OAuthCallbackResponse:
    """SPA: redirect Meta → frontend com ?code= → chama este endpoint."""
    return await _complete_oauth(body.code, body.state)


@router.get("/oauth/callback", response_model=OAuthCallbackResponse)
async def oauth_callback(
    code: str = Query(...),
    state: Optional[str] = Query(None),
) -> OAuthCallbackResponse:
    """Se META_OAUTH_REDIRECT_URI for a URL do próprio backend."""
    return await _complete_oauth(code, state)


class SessionStatusResponse(BaseModel):
    connected: bool
    token_preview: str | None = None
    updated_at: str | None = None


@router.get("/session", response_model=SessionStatusResponse)
async def session_status() -> SessionStatusResponse:
    meta = await get_solo_session_meta()
    if not meta:
        return SessionStatusResponse(connected=False)
    return SessionStatusResponse(
        connected=True,
        token_preview=meta.get("token_preview"),
        updated_at=meta.get("updated_at"),
    )


@router.post("/session/disconnect")
async def session_disconnect() -> dict[str, str]:
    await clear_solo_session()
    return {"status": "ok"}


async def _access_token() -> str:
    tok = await get_solo_token()
    if not tok:
        raise HTTPException(
            status_code=401,
            detail="Faça OAuth primeiro (/api/v1/meta/oauth/authorize-url)",
        )
    return tok


@router.get("/pages", response_model=list[PageIgItem])
async def list_pages() -> list[PageIgItem]:
    token = await _access_token()
    pages = await graph.fetch_pages_with_instagram(token)
    out: list[PageIgItem] = []
    for p in pages:
        ig = p.get("instagram_business_account") or {}
        out.append(
            PageIgItem(
                page_id=str(p.get("id", "")),
                page_name=str(p.get("name", "")),
                ig_user_id=str(ig["id"]) if ig.get("id") else None,
                ig_username=ig.get("username"),
            )
        )
    return out


@router.get("/ig/{ig_user_id}/media")
async def ig_media(ig_user_id: str, limit: int = 15) -> dict[str, Any]:
    token = await _access_token()
    items = await graph.fetch_ig_media(token, ig_user_id, limit=limit)
    return {"data": items, "count": len(items)}


@router.get("/ig/{ig_user_id}/media-with-insights")
async def ig_media_with_insights(
    ig_user_id: str,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Busca mídias e tenta anexar insights por item (pode falhar silenciosamente por tipo/permissão).
    """
    token = await _access_token()
    items = await graph.fetch_ig_media(token, ig_user_id, limit=limit)
    enriched = []
    for m in items:
        mid = m.get("id")
        insights: list[dict[str, Any]] = []
        if mid:
            insights = await graph.fetch_media_insights(token, str(mid))
        row = {**m, "insights": insights}
        enriched.append(row)
    return {"data": enriched, "count": len(enriched)}
