"""
OAuth Meta + endpoints para listar páginas/IG e sincronizar mídias.

Token: Supabase (`pilotgram_oauth_solo`) ou SQLite local.
"""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from config import settings
from database import (
    approve_content_suggestion,
    clear_solo_session,
    get_profile_brief,
    get_profile_dna,
    get_solo_session_meta,
    get_solo_token,
    get_suggestion_creative_context,
    list_content_suggestions,
    save_content_suggestions,
    save_solo_token,
    update_suggestion_creative_image_url,
    upsert_profile_brief,
    upsert_profile_dna,
)
from services import meta_graph as graph
from services import openai_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/meta", tags=["meta"])

# state OAuth (curto prazo; não precisa persistir)
_dev_state_to_user: dict[str, str] = {}


def _creative_preview_svg_bytes(prompt: str) -> bytes:
    """SVG servido pela API (evita CSP do site que bloqueia data: em <img>)."""
    p = (prompt or "").strip() or "Pilotgram — preview do criativo"
    line1 = xml_escape(p[:110] + ("…" if len(p) > 110 else ""))
    line2_xml = ""
    if len(p) > 110:
        line2 = xml_escape(p[110:230] + ("…" if len(p) > 230 else ""))
        line2_xml = (
            f'<text x="540" y="530" text-anchor="middle" fill="#94a3b8" '
            f'font-size="26" font-family="system-ui,sans-serif">{line2}</text>'
        )
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1080" viewBox="0 0 1080 1080">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0%" stop-color="#0f172a"/><stop offset="100%" stop-color="#1e293b"/>
</linearGradient></defs>
<rect width="100%" height="100%" fill="url(#g)"/>
<text x="540" y="480" text-anchor="middle" fill="#e2e8f0" font-size="32" font-family="system-ui,sans-serif">{line1}</text>
{line2_xml}
</svg>"""
    return svg.encode("utf-8")


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
    creative_fetch_token: str | None = None
    suggested_date: str | None = None
    frequency_per_week: int | None = None
    focus_topic: str | None = None
    language: str | None = None


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
    language_hint: str = "pt"
    updated_at: str


class ProfileBriefBody(BaseModel):
    niche: str = ""
    target_audience: str = ""
    objective: str = ""
    offer_summary: str = ""
    preferred_language: str = ""
    tone_style: str = ""
    do_not_use_terms: str = ""


class ProfileBriefResponse(ProfileBriefBody):
    ig_user_id: str
    updated_at: str
    filled_from_dna: bool = False


def _short_caption(caption: str | None) -> str:
    text = (caption or "").replace("\n", " ").strip()
    if not text:
        return "Post sem legenda"
    if len(text) > 120:
        return f"{text[:117]}..."
    return text


def _clean_sentence(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    t = re.sub(r"[.,;:!?]{2,}", ".", t)
    return t.strip(" .")


def _is_placeholder_brief(text: str) -> bool:
    t = _clean_sentence(text).lower()
    if not t:
        return True
    placeholder_markers = [
        "suggested from recent posts",
        "adjust to your real audience",
        "refine to your goal",
        "growth, authority and conversion on instagram",
        "kads, adsoftheworld",
    ]
    return any(p in t for p in placeholder_markers)


def _looks_portuguese(text: str) -> bool:
    t = (text or "").lower()
    return any(
        m in t
        for m in [" você ", " para ", " com ", " que ", " não ", " comentário", "enviar", "material", "peça"]
    )


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
    "are",
    "you",
    "your",
    "this",
    "that",
    "with",
    "have",
    "from",
    "about",
    "more",
    "what",
    "will",
    "just",
    "into",
    "it's",
    "its",
    "it's",
    "teu",
    "tua",
    "meu",
    "minha",
    "mais",
    "sobre",
    "isso",
    "esse",
    "essa",
    "como",
    "sempre",
    "nunca",
    "hoje",
    "daily",
}


def _extract_keywords(media_items: list[dict[str, Any]], limit: int = 6) -> list[str]:
    hashtag_counts: dict[str, int] = {}
    word_counts: dict[str, int] = {}
    for m in media_items:
        caption = str(m.get("caption") or "").lower()
        for tag in re.findall(r"#([a-zà-ú0-9_]{3,})", caption):
            if tag in _STOPWORDS or tag.startswith("http"):
                continue
            hashtag_counts[tag] = hashtag_counts.get(tag, 0) + 1
        for token in re.findall(r"[a-zà-ú0-9_]{4,}", caption):
            if token in _STOPWORDS or token.startswith("http"):
                continue
            # Remove ruído de texto genérico em EN/PT.
            if token.isdigit() or token in {"http", "https", "www", "reel", "reels", "post"}:
                continue
            word_counts[token] = word_counts.get(token, 0) + 1
    ordered = [k for k, _ in sorted(hashtag_counts.items(), key=lambda x: x[1], reverse=True)]
    ordered += [k for k, _ in sorted(word_counts.items(), key=lambda x: x[1], reverse=True) if k not in ordered]
    return ordered[:limit]


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


def _normalize_focus_for_lang(focus_topic: str, lang: str) -> str:
    raw = (focus_topic or "").strip()
    if not raw:
        return "self-help, coaching, personal development" if lang == "en" else "autoajuda, coaching, desenvolvimento pessoal"
    if lang == "en" and any(x in raw.lower() for x in ["autoajuda", "desenvolvimento", "saúde mental"]):
        return "self-help, coaching, personal development"
    if lang == "pt" and any(x in raw.lower() for x in ["self-help", "personal development"]):
        return "autoajuda, coaching, desenvolvimento pessoal"
    return raw


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


def _detect_language(media_items: list[dict[str, Any]]) -> str:
    text = " ".join([str(m.get("caption") or "").lower() for m in media_items[:12]])
    if not text.strip():
        return "pt"
    en_markers = [r"\bthe\b", r"\band\b", r"\byour\b", r"\byou\b", r"\bis\b", r"\bare\b", r"\bwith\b", r"\bthis\b"]
    pt_markers = [r"\bvocê\b", r"\bpara\b", r"\bcom\b", r"\bque\b", r"\buma\b", r"\bseu\b", r"\bsua\b", r"\bisso\b"]
    en_score = sum(len(re.findall(p, text)) for p in en_markers)
    pt_score = sum(len(re.findall(p, text)) for p in pt_markers)
    return "en" if en_score > pt_score else "pt"


def _cta_by_lang(media_items: list[dict[str, Any]], lang: str) -> str:
    if lang == "en":
        return "CTA: comment with a keyword and I will send the details in DM."
    return _best_cta(media_items)


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
    brief: dict[str, Any] | None = None,
) -> list[dict[str, str | None]]:
    def score(row: dict[str, Any]) -> float:
        likes = float(row.get("like_count") or 0)
        comments = float(row.get("comments_count") or 0)
        return (likes * 2.0) + (comments * 3.0)

    focused_media = _filter_media_by_focus(media_items, focus_topic)
    ranked = sorted(focused_media, key=score, reverse=True)
    top = ranked[: max(1, count)]
    forced_lang = str((brief or {}).get("preferred_language") or "").strip().lower()
    if forced_lang in {"en", "english"}:
        lang = "en"
    elif forced_lang in {"pt", "pt-br", "portuguese"}:
        lang = "pt"
    else:
        lang = _detect_language(ranked)
    focus_topic = _normalize_focus_for_lang(focus_topic, lang)
    keywords = _extract_keywords(ranked, limit=6)
    tone_hint = str(dna.get("tone_hint")) if dna else _tone_hint(ranked)
    cta_hint = _cta_by_lang(ranked, lang)
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
    niche = str((brief or {}).get("niche") or "").strip()
    objective = str((brief or {}).get("objective") or "").strip()
    target = str((brief or {}).get("target_audience") or "").strip()
    tone_style = str((brief or {}).get("tone_style") or "").strip()
    offer = str((brief or {}).get("offer_summary") or "").strip()
    if _is_placeholder_brief(target):
        target = ""
    if _is_placeholder_brief(objective):
        objective = ""
    if _is_placeholder_brief(offer):
        offer = ""
    if forced_lang in {"en", "english"} and _looks_portuguese(offer):
        offer = ""
    blocked_terms = [
        t.strip().lower() for t in str((brief or {}).get("do_not_use_terms") or "").split(",") if t.strip()
    ]

    def clean_blocked(text: str) -> str:
        out_text = text
        for term in blocked_terms:
            out_text = re.sub(rf"\b{re.escape(term)}\b", "", out_text, flags=re.IGNORECASE)
        return re.sub(r"\s{2,}", " ", out_text).strip()

    for idx, m in enumerate(top):
        anchor = _short_caption(m.get("caption"))
        post_type = str(m.get("media_type") or "POST")
        angle = angles[idx % len(angles)]
        focus = ", ".join(keywords[:3]) if keywords else "tema principal do perfil"
        day = base_date + timedelta(days=idx * interval_days)
        # Legenda final pronta para postar — sem rótulos internos ou mini-roteiro.
        if lang == "en":
            cta_clean = _clean_sentence(cta_hint.replace("CTA:", ""))
            kws = [
                k.strip().replace(" ", "")
                for k in (keywords[:3] if keywords else ["mindset", "coaching", "growth"])
                if k.strip()
            ]
            keyword_tags = " ".join([f"#{k}" for k in kws[:3]])
            focus_tags = " ".join(
                [f"#{t.replace(' ', '')}" for t in focus_topic.split(",")[:2] if t.strip()]
            )
            audience_piece = ""
            if target:
                audience_piece = f"For {target.lower()}, "
            goal_piece = ""
            if objective:
                goal_piece = f"who want {objective.lower()}, "
            hook = (
                f"{audience_piece}{goal_piece}here's a simple move to unlock progress around {focus_topic or focus}."
            ).strip()
            middle = (
                f"Instead of repeating the same pattern, tell a quick story from a real client or from your own journey. "
                f"Show the old habit in one sentence and then the new, better action in the same tone you already use on your profile."
            )
            if offer:
                middle += f" Tie the lesson directly to what you offer: {_clean_sentence(offer)}."
            anchor_line = f"Use this post as inspiration: {anchor}."
            caption_core = f"{hook}\n\n{middle}\n\n{anchor_line}"
            if cta_clean:
                caption_core += f"\n\n{cta_clean}"
            hashtags_block = (f"{keyword_tags} {focus_tags}").strip()
            suggestion_text = caption_core if not hashtags_block else f"{caption_core}\n\n{hashtags_block}"
        else:
            cta_clean = _clean_sentence(cta_hint.replace("CTA:", ""))
            kws = [
                k.strip().replace(" ", "")
                for k in (keywords[:3] if keywords else ["mindset", "coaching", "evolucao"])
                if k.strip()
            ]
            keyword_tags = " ".join([f"#{k}" for k in kws[:3]])
            focus_tags = " ".join(
                [f"#{t.replace(' ', '')}" for t in focus_topic.split(",")[:2] if t.strip()]
            )
            audience_piece = ""
            if target:
                audience_piece = f"Se você fala com {target.lower()}, "
            goal_piece = ""
            if objective:
                goal_piece = f"que quer {objective.lower()}, "
            hook = (
                f"{audience_piece}{goal_piece}usa este post para destravar um avanço em {focus_topic or focus}."
            ).strip()
            middle = (
                f"Conte em poucas linhas uma situação real que o teu público vive hoje, mostrando o erro mais comum "
                f"e em seguida a nova ação que você recomenda, no mesmo tom de voz que já aparece nas tuas melhores postagens."
            )
            if offer:
                middle += f" Puxa o gancho naturalmente para a tua oferta: {_clean_sentence(offer)}."
            anchor_line = f"Inspiração tirada do teu próprio feed: {anchor}."
            caption_core = f"{hook}\n\n{middle}\n\n{anchor_line}"
            if cta_clean:
                caption_core += f"\n\n{cta_clean}"
            hashtags_block = (f"{keyword_tags} {focus_tags}").strip()
            suggestion_text = caption_core if not hashtags_block else f"{caption_core}\n\n{hashtags_block}"
        suggestion_text = clean_blocked(suggestion_text)
        creative_prompt = (
            f"Instagram post cover, niche {niche or focus_topic or focus}, angle {angle}, "
            f"{'English-speaking' if lang == 'en' else 'Brazilian Portuguese'} audience, "
            f"{'tone ' + tone_style + ', ' if tone_style else ''}"
            f"no text in image, clean composition, mobile-friendly, {post_type.lower()} style."
        )
        out.append(
            {
                "source_media_id": str(m.get("id")) if m.get("id") else None,
                "suggestion_text": suggestion_text,
                "rationale": f"Tema: {focus_topic or focus} · Ângulo: {angle} · Formato: {post_type}.",
                "creative_prompt": creative_prompt,
                "creative_image_url": None,
                "suggested_date": day.isoformat(),
                "frequency_per_week": frequency_per_week,
                "focus_topic": focus_topic or focus,
                "language": lang,
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
        "language_hint": _detect_language(ranked),
    }


def _suggested_brief_fields_from_dna(dna: dict[str, Any]) -> dict[str, str]:
    """Preenche lacunas do questionário com sinais extraídos das publicações (DNA)."""
    themes: list[str] = list(dna.get("themes") or [])
    niche = ", ".join(themes[:6]) if themes else ""
    tone = str(dna.get("tone_hint") or "")
    tone = re.sub(r"^tom de voz:\s*", "", tone, flags=re.I).strip()
    cta = str(dna.get("cta_hint") or "")
    cta = re.sub(r"^cta:\s*", "", cta, flags=re.I).strip()
    raw_lang = str(dna.get("language_hint") or "pt").strip().lower()
    lang = "en" if raw_lang == "en" else "pt"
    return {
        "niche": niche,
        "target_audience": (
            "Suggested from recent posts — adjust to your real audience."
            if lang == "en"
            else "Sugestão a partir das publicações recentes — ajuste ao seu público real."
        ),
        "objective": (
            "Growth, authority and conversion on Instagram — refine to your goal."
            if lang == "en"
            else "Crescimento, autoridade e conversão no Instagram — refine conforme a sua meta."
        ),
        "offer_summary": cta,
        "preferred_language": lang,
        "tone_style": tone
        or ("direct, authentic" if lang == "en" else "direto, autêntico"),
        "do_not_use_terms": "",
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


@router.get("/creatives/{token}")
async def serve_creative_preview(token: str) -> Response:
    """Imagem de preview (SVG) — URL pública opaca; não expõe dados além do prompt salvo."""
    ctx = await get_suggestion_creative_context(token)
    if not ctx:
        raise HTTPException(status_code=404, detail="criativo não encontrado")
    body = _creative_preview_svg_bytes(str(ctx.get("creative_prompt") or ""))
    return Response(
        content=body,
        media_type="image/svg+xml; charset=utf-8",
        headers={"Cache-Control": "public, max-age=300"},
    )


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
    focus_topic = (focus_topic or "").strip() or "coaching, mindset, desenvolvimento pessoal"
    media = await graph.fetch_ig_media(token, ig_user_id, limit=max(8, min(25, count * 3)))
    dna_input = _derive_dna_from_media(ig_user_id, media)
    dna_saved = await upsert_profile_dna(
        ig_user_id=ig_user_id,
        themes=list(dna_input["themes"]),
        tone_hint=str(dna_input["tone_hint"]),
        cta_hint=str(dna_input["cta_hint"]),
        language_hint=str(dna_input.get("language_hint") or "pt"),
    )
    brief_saved = await get_profile_brief(ig_user_id)
    draft = _build_suggestions_from_media(
        ig_user_id,
        media,
        count=count,
        frequency_per_week=frequency_per_week,
        focus_topic=focus_topic,
        dna=dna_saved,
        brief=brief_saved,
    )
    public_base = settings.effective_public_api_base
    saved = await save_content_suggestions(ig_user_id, draft, public_api_base=public_base)
    if not public_base:
        logger.warning(
            "PG_PUBLIC_API_URL / RENDER_EXTERNAL_URL vazio — creative_image_url ficará vazio até configurar a URL pública da API."
        )

    if (settings.openai_api_key or "").strip():
        sem = asyncio.Semaphore(2)

        async def enhance_creative(row: dict) -> None:
            async with sem:
                url = await openai_image.generate_image_url(
                    settings.openai_api_key,
                    str(row.get("creative_prompt") or ""),
                    model=settings.openai_image_model,
                )
                if url:
                    await update_suggestion_creative_image_url(int(row["id"]), url)
                    row["creative_image_url"] = url

        await asyncio.gather(*[enhance_creative(r) for r in saved])

    normalized = [_normalize_suggestion_creative_url(s) for s in saved]
    return SuggestionGenerateResponse(generated=len(normalized), data=[SuggestionItem(**s) for s in normalized])


def _normalize_suggestion_creative_url(row: dict[str, Any]) -> dict[str, Any]:
    """Preenche creative_image_url a partir do token quando a linha antiga ficou sem URL (base pública vazia)."""
    r = dict(row)
    base = settings.effective_public_api_base
    url = str(r.get("creative_image_url") or "").strip()
    tok = str(r.get("creative_fetch_token") or "").strip()
    if not url and tok and base:
        r["creative_image_url"] = f"{base}/api/v1/meta/creatives/{tok}"
    return r


@router.get("/ig/{ig_user_id}/suggestions", response_model=SuggestionListResponse)
async def get_suggestions(ig_user_id: str) -> SuggestionListResponse:
    rows = await list_content_suggestions(ig_user_id)
    fixed = [_normalize_suggestion_creative_url(r) for r in rows]
    return SuggestionListResponse(data=[SuggestionItem(**r) for r in fixed], count=len(fixed))


@router.get("/ig/{ig_user_id}/dna", response_model=ProfileDnaResponse)
async def get_dna(ig_user_id: str) -> ProfileDnaResponse:
    row = await get_profile_dna(ig_user_id)
    if not row:
        raise HTTPException(status_code=404, detail="DNA ainda não gerado para este perfil")
    return ProfileDnaResponse(
        ig_user_id=str(row["ig_user_id"]),
        themes=list(row.get("themes") or []),
        tone_hint=str(row.get("tone_hint") or ""),
        cta_hint=str(row.get("cta_hint") or ""),
        language_hint=str(row.get("language_hint") or "pt"),
        updated_at=str(row.get("updated_at") or ""),
    )


@router.post("/ig/{ig_user_id}/dna/refresh", response_model=ProfileDnaResponse)
async def refresh_dna(ig_user_id: str) -> ProfileDnaResponse:
    """Atualiza DNA a partir das mídias recentes (sem gerar sugestões). Usado ao abrir o dashboard."""
    token = await _access_token()
    media = await graph.fetch_ig_media(token, ig_user_id, limit=25)
    if not media:
        raise HTTPException(status_code=400, detail="Sem mídias Instagram para analisar neste perfil.")
    dna_input = _derive_dna_from_media(ig_user_id, media)
    await upsert_profile_dna(
        ig_user_id=ig_user_id,
        themes=list(dna_input["themes"]),
        tone_hint=str(dna_input["tone_hint"]),
        cta_hint=str(dna_input["cta_hint"]),
        language_hint=str(dna_input.get("language_hint") or "pt"),
    )
    row = await get_profile_dna(ig_user_id)
    if not row:
        raise HTTPException(status_code=500, detail="Falha ao persistir DNA")
    return ProfileDnaResponse(
        ig_user_id=str(row["ig_user_id"]),
        themes=list(row.get("themes") or []),
        tone_hint=str(row.get("tone_hint") or ""),
        cta_hint=str(row.get("cta_hint") or ""),
        language_hint=str(row.get("language_hint") or "pt"),
        updated_at=str(row.get("updated_at") or ""),
    )


@router.put("/ig/{ig_user_id}/brief", response_model=ProfileBriefResponse)
async def put_brief(ig_user_id: str, body: ProfileBriefBody) -> ProfileBriefResponse:
    await upsert_profile_brief(
        ig_user_id=ig_user_id,
        niche=body.niche,
        target_audience=body.target_audience,
        objective=body.objective,
        offer_summary=body.offer_summary,
        preferred_language=body.preferred_language,
        tone_style=body.tone_style,
        do_not_use_terms=body.do_not_use_terms,
    )
    return await get_brief(ig_user_id)


@router.get("/ig/{ig_user_id}/brief", response_model=ProfileBriefResponse)
async def get_brief(ig_user_id: str) -> ProfileBriefResponse:
    """Devolve o último briefing gravado; campos vazios são preenchidos com sugestões do DNA (posts recentes)."""
    row = await get_profile_brief(ig_user_id)
    dna = await get_profile_dna(ig_user_id)
    now = datetime.now(timezone.utc).isoformat()
    keys = [
        "niche",
        "target_audience",
        "objective",
        "offer_summary",
        "preferred_language",
        "tone_style",
        "do_not_use_terms",
    ]
    data: dict[str, str] = {k: "" for k in keys}
    updated_at = now
    if row:
        for k in keys:
            data[k] = str(row.get(k) or "").strip()
        updated_at = str(row.get("updated_at") or now)
    filled_from_dna = False
    if dna:
        sug = _suggested_brief_fields_from_dna(dna)
        for k in keys:
            if not (data.get(k) or "").strip():
                v = (sug.get(k) or "").strip()
                if v:
                    data[k] = v
                    filled_from_dna = True
    return ProfileBriefResponse(
        ig_user_id=ig_user_id,
        updated_at=updated_at,
        filled_from_dna=filled_from_dna,
        niche=data["niche"],
        target_audience=data["target_audience"],
        objective=data["objective"],
        offer_summary=data["offer_summary"],
        preferred_language=data["preferred_language"],
        tone_style=data["tone_style"],
        do_not_use_terms=data["do_not_use_terms"],
    )


@router.post("/suggestions/{suggestion_id}/approve", response_model=SuggestionItem)
async def approve_suggestion(suggestion_id: int) -> SuggestionItem:
    row = await approve_content_suggestion(suggestion_id)
    if not row:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada")
    return SuggestionItem(**_normalize_suggestion_creative_url(row))
