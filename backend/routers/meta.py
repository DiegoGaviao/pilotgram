"""
OAuth Meta + endpoints para listar páginas/IG e sincronizar mídias.

Token: Supabase (`pilotgram_oauth_solo`) ou SQLite local.
"""

from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import quote_plus

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config import settings
from database import (
    approve_content_suggestion,
    clear_solo_session,
    get_profile_dna,
    get_solo_session_meta,
    get_solo_token,
    list_content_suggestions,
    save_content_suggestions,
    save_solo_token,
    upsert_profile_dna,
)
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


class SuggestionItem(BaseModel):
    id: int
    ig_user_id: str
    source_media_id: str | None = None
    suggestion_text: str
    rationale: str | None = None
    status: str
    created_at: str
    approved_at: str | None = None
    creative_prompt: str | None = None
    creative_image_url: str | None = None
    suggested_date: str | None = None
    frequency_per_week: int | None = None
    focus_topic: str | None = None


class SuggestionListResponse(BaseModel):
    data: list[SuggestionItem]
    count: int


class SuggestionGenerateResponse(BaseModel):
    generated: int
    data: list[SuggestionItem]


class ProfileDnaResponse(BaseModel):
    ig_user_id: str
    themes: list[str]
    tone_hint: str
    cta_hint: str
    updated_at: str


def _short_caption(caption: str | None) -> str:
    text = (caption or "").replace("\n", " ").strip()
    if not text:
        return "Post sem legenda"
    if len(text) > 120:
        return f"{text[:117]}..."
    return text


_STOPWORDS = {
    "a",
    "o",
    "as",
    "os",
    "de",
    "da",
    "do",
    "das",
    "dos",
    "e",
    "em",
    "no",
    "na",
    "nos",
    "nas",
    "com",
    "para",
    "por",
    "um",
    "uma",
    "que",
    "se",
    "ao",
    "à",
    "é",
    "the",
    "and",
    "to",
    "of",
    "in",
    "for",
    "on",
    "is",
}


def _extract_keywords(media_items: list[dict[str, Any]], limit: int = 6) -> list[str]:
    counts: dict[str, int] = {}
    for m in media_items:
        caption = str(m.get("caption") or "").lower()
        for token in re.findall(r"[a-zà-ú0-9_]{4,}", caption):
            if token in _STOPWORDS or token.startswith("http"):
                continue
            counts[token] = counts.get(token, 0) + 1
    return [k for k, _ in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]]


def _tokens(text: str) -> list[str]:
    return [
        t
        for t in re.findall(r"[a-zà-ú0-9_]{4,}", (text or "").lower())
        if t not in _STOPWORDS and not t.startswith("http")
    ]


def _filter_media_by_focus(media_items: list[dict[str, Any]], focus_topic: str) -> list[dict[str, Any]]:
    focus = set(_tokens(focus_topic))
    if not focus:
        return media_items
    filtered: list[dict[str, Any]] = []
    for m in media_items:
        caption_tokens = set(_tokens(str(m.get("caption") or "")))
        if focus.intersection(caption_tokens):
            filtered.append(m)
    return filtered or media_items


def _best_cta(media_items: list[dict[str, Any]]) -> str:
    ranked = sorted(
        media_items,
        key=lambda row: (float(row.get("comments_count") or 0) * 3.0)
        + (float(row.get("like_count") or 0) * 2.0),
        reverse=True,
    )
    for m in ranked[:5]:
        caption = str(m.get("caption") or "")
        if "comenta" in caption.lower():
            return "CTA: peça comentário com palavra-chave e responda em DM."
        if "direct" in caption.lower() or "dm" in caption.lower():
            return "CTA: leve para DM com oferta de checklist/template."
    return "CTA: peça comentário com palavra-chave para enviar o material."


def _tone_hint(media_items: list[dict[str, Any]]) -> str:
    return (
        "Tom de voz: direto, prático e humano, com exemplos reais."
        if any("você" in str(m.get("caption") or "").lower() for m in media_items[:5])
        else "Tom de voz: autoridade didática, curto e acionável."
    )


def _build_suggestions_from_media(
    ig_user_id: str,
    media_items: list[dict[str, Any]],
    count: int,
    frequency_per_week: int,
    focus_topic: str,
    dna: dict[str, Any] | None = None,
) -> list[dict[str, str | None]]:
    def score(row: dict[str, Any]) -> float:
        likes = float(row.get("like_count") or 0)
        comments = float(row.get("comments_count") or 0)
        return (likes * 2.0) + (comments * 3.0)

    focused_media = _filter_media_by_focus(media_items, focus_topic)
    ranked = sorted(focused_media, key=score, reverse=True)
    top = ranked[: max(1, count)]
    keywords = _extract_keywords(ranked, limit=6)
    tone_hint = str(dna.get("tone_hint")) if dna else _tone_hint(ranked)
    cta_hint = str(dna.get("cta_hint")) if dna else _best_cta(ranked)
    if dna and dna.get("themes"):
        persisted_themes = [str(x).strip() for x in list(dna.get("themes")) if str(x).strip()]
        keywords = (persisted_themes + keywords)[:6]
    angles = [
        "erro comum + correção prática",
        "passo a passo em 3 etapas",
        "quebra de crença com prova/exemplo",
        "bastidores de caso real",
        "checklist de execução semanal",
    ]
    out: list[dict[str, str | None]] = []
    base_date = datetime.now(timezone.utc).replace(hour=14, minute=0, second=0, microsecond=0)
    interval_days = max(1, int(round(7 / max(1, frequency_per_week))))
    for idx, m in enumerate(top):
        anchor = _short_caption(m.get("caption"))
        post_type = str(m.get("media_type") or "POST")
        angle = angles[idx % len(angles)]
        focus = ", ".join(keywords[:3]) if keywords else "tema principal do perfil"
        day = base_date + timedelta(days=idx * interval_days)
        hook = (
            f"Se você sente que está travado em {focus_topic}, este ajuste simples pode virar o jogo."
            if focus_topic
            else f"Gancho: {anchor}"
        )
        cta_clean = cta_hint.replace("CTA:", "").strip()
        hashtags = " ".join([f"#{t.replace(' ', '')}" for t in (focus_topic.split(",")[:3] if focus_topic else keywords[:3]) if t.strip()])
        suggestion_text = (
            f"{hook}\n\n"
            f"Você não precisa reinventar tudo. Comece com 1 ação prática hoje: escolha um hábito-chave, "
            f"repita por 7 dias e registre o resultado.\n\n"
            f"Exemplo real: {anchor}\n\n"
            f"{cta_clean}\n\n"
            f"{hashtags}"
        )
        creative_prompt = (
            f"Instagram post cover, niche {focus_topic or focus}, angle {angle}, "
            f"Brazilian audience, no text in image, clean composition, mobile-friendly, {post_type.lower()} style."
        )
        seed = quote_plus(f"{ig_user_id}-{idx}-{focus_topic or focus}")
        creative_image_url = f"https://picsum.photos/seed/{seed}/1080/1080"
        out.append(
            {
                "source_media_id": str(m.get("id")) if m.get("id") else None,
                "suggestion_text": suggestion_text,
                "rationale": f"Tema: {focus_topic or focus} · Ângulo: {angle} · Formato: {post_type}.",
                "creative_prompt": creative_prompt,
                "creative_image_url": creative_image_url,
                "suggested_date": day.isoformat(),
                "frequency_per_week": frequency_per_week,
                "focus_topic": focus_topic or focus,
            }
        )
    if not out:
        out.append(
            {
                "source_media_id": None,
                "suggestion_text": (
                    "Gancho: 3 erros comuns que travam teu perfil hoje.\n"
                    "Roteiro: erro 1, erro 2, erro 3 + micro-solução de cada.\n"
                    "CTA: comenta 'CHECKLIST' para receber o passo a passo."
                ),
                "rationale": f"Fallback para IG {ig_user_id} sem mídias suficientes.",
            }
        )
    return out


def _derive_dna_from_media(ig_user_id: str, media_items: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(
        media_items,
        key=lambda row: (float(row.get("like_count") or 0) * 2.0)
        + (float(row.get("comments_count") or 0) * 3.0),
        reverse=True,
    )
    return {
        "ig_user_id": ig_user_id,
        "themes": _extract_keywords(ranked, limit=8),
        "tone_hint": _tone_hint(ranked),
        "cta_hint": _best_cta(ranked),
    }


@router.get("/oauth/authorize-url", response_model=AuthorizeUrlResponse)
async def oauth_authorize_url() -> AuthorizeUrlResponse:
    # Sem App ID o graph levanta ValueError → 500 texto; o browser mostra “CORS” porque
    # essa resposta muitas vezes não traz Access-Control-Allow-Origin.
    if not (settings.meta_app_id or "").strip():
        raise HTTPException(
            status_code=503,
            detail="Defina META_APP_ID e META_APP_SECRET nas Environment Variables da API no Render e faça redeploy.",
        )
    if not (settings.meta_oauth_redirect_uri or "").strip():
        raise HTTPException(status_code=503, detail="META_OAUTH_REDIRECT_URI em falta.")
    state = secrets.token_urlsafe(24)
    _dev_state_to_user[state] = "solo"
    try:
        url = graph.oauth_authorize_url(state)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
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


@router.post("/ig/{ig_user_id}/suggestions/generate", response_model=SuggestionGenerateResponse)
async def generate_suggestions(
    ig_user_id: str,
    count: int = 5,
    frequency_per_week: int = 3,
    focus_topic: str = "",
) -> SuggestionGenerateResponse:
    token = await _access_token()
    count = max(1, min(10, count))
    frequency_per_week = max(1, min(7, frequency_per_week))
    focus_topic = (focus_topic or "").strip() or "conteúdo de valor para o nicho da conta"
    media = await graph.fetch_ig_media(token, ig_user_id, limit=max(8, min(25, count * 3)))
    dna_input = _derive_dna_from_media(ig_user_id, media)
    dna_saved = await upsert_profile_dna(
        ig_user_id=ig_user_id,
        themes=list(dna_input["themes"]),
        tone_hint=str(dna_input["tone_hint"]),
        cta_hint=str(dna_input["cta_hint"]),
    )
    draft = _build_suggestions_from_media(
        ig_user_id,
        media,
        count=count,
        frequency_per_week=frequency_per_week,
        focus_topic=focus_topic,
        dna=dna_saved,
    )
    saved = await save_content_suggestions(ig_user_id, draft)
    return SuggestionGenerateResponse(generated=len(saved), data=[SuggestionItem(**s) for s in saved])


@router.get("/ig/{ig_user_id}/suggestions", response_model=SuggestionListResponse)
async def get_suggestions(ig_user_id: str) -> SuggestionListResponse:
    rows = await list_content_suggestions(ig_user_id)
    return SuggestionListResponse(data=[SuggestionItem(**r) for r in rows], count=len(rows))


@router.get("/ig/{ig_user_id}/dna", response_model=ProfileDnaResponse)
async def get_dna(ig_user_id: str) -> ProfileDnaResponse:
    row = await get_profile_dna(ig_user_id)
    if not row:
        raise HTTPException(status_code=404, detail="DNA ainda não gerado para este perfil")
    return ProfileDnaResponse(**row)


@router.post("/suggestions/{suggestion_id}/approve", response_model=SuggestionItem)
async def approve_suggestion(suggestion_id: int) -> SuggestionItem:
    row = await approve_content_suggestion(suggestion_id)
    if not row:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada")
    return SuggestionItem(**row)
