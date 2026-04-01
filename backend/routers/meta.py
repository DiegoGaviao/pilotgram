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
from services import openai_caption, openai_image

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
    debug_trace: dict[str, Any] | None = None


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


def _canonical_lang_from_brief_field(raw: str) -> str | None:
    """Normaliza o campo preferred_language do questionário → 'en' | 'pt' | None (auto)."""
    s = (raw or "").strip().lower().replace("_", "-")
    if not s:
        return None
    if s in {"en", "english"} or s.startswith("en-") or s in {"ingles", "inglês", "inglés"}:
        return "en"
    if s in {"pt", "pt-br", "portuguese", "português", "portugues"} or s.startswith("pt-"):
        return "pt"
    if "english" in s or "ingl" in s:
        return "en"
    if "portug" in s:
        return "pt"
    return None


def _canonical_lang_from_dna_hint(dna: dict[str, Any] | None) -> str | None:
    h = str((dna or {}).get("language_hint") or "").strip().lower()
    if h == "en":
        return "en"
    if h in {"pt", "pt-br"}:
        return "pt"
    return None


def _resolve_caption_language(
    brief: dict[str, Any] | None,
    dna: dict[str, Any] | None,
    ranked_media: list[dict[str, Any]],
) -> tuple[str, str]:
    """
    Ordem: questionário (normalizado) → DNA → detecção nas legendas.
    Devolve (lang, fonte) com fonte em brief | dna | detect.
    """
    from_brief = _canonical_lang_from_brief_field(str((brief or {}).get("preferred_language") or ""))
    if from_brief:
        return from_brief, "brief"
    from_dna = _canonical_lang_from_dna_hint(dna)
    if from_dna:
        return from_dna, "dna"
    return _detect_language(ranked_media), "detect"


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


# Cenas mínimas só com objetos (reduz texto/UI/esoterismo no DALL·E). Inglês para o modelo de imagem.
_SAFE_IMAGE_SCENES: list[str] = [
    (
        "Single photorealistic still life, square 1:1: closed laptop, matte ceramic coffee mug, "
        "one green houseplant leaf at frame edge, pale wood desk, soft morning sidelight, "
        "shallow depth of field, no people, no books, no frames, no phones, no posters, no wall art with glyphs."
    ),
    (
        "Single photorealistic POV: sneakers on a quiet paved path, trees softly blurred, daylight, "
        "neutral calm mood, no faces, no signage, no screens, no spiritual glow."
    ),
    (
        "Single photorealistic detail: hands adjusting a simple wristwatch or sleeve, neutral clothing, "
        "soft window light, tight crop, no text, no jewelry with symbols, no yoga pose."
    ),
    (
        "Single photorealistic scene: ceramic mug and small plate on a kitchen counter, morning light, "
        "minimal clutter, no packaging with readable labels, no books, no UI."
    ),
    (
        "Single photorealistic interior: empty chair with a folded jacket, simple bag on floor nearby, "
        "calm home office corner, daylight, no desk clutter with paper text, no frames on wall."
    ),
    (
        "Single photorealistic outdoor: clear sky with soft clouds over a normal city roofline, "
        "telephoto compression, mundane horizon, no monuments, no sacred architecture, no lens-flare sermon vibe."
    ),
]


def _safe_creative_scene(idx: int) -> str:
    return _SAFE_IMAGE_SCENES[idx % len(_SAFE_IMAGE_SCENES)]


def _reader_facing_caption(
    *,
    lang: str,
    angle: str,
    cta_clean: str,
    hashtags_block: str,
    offer: str,
    focus_topic: str,
    focus: str,
) -> str:
    """Legenda pronta para o leitor — zero 'mini-roteiro' ou instruções ao criador."""
    theme = (focus_topic or focus or "").strip()
    if lang == "en":
        bodies: dict[str, str] = {
            "erro comum + correção prática": (
                "You know that Sunday-night feeling? You swear Monday will be different — "
                "then you open your phone for a second and forty minutes vanish.\n\n"
                "The old loop: trying to fix everything with willpower alone.\n\n"
                "The small shift: pick one 10-minute win before bed — lay out clothes, queue one task, "
                "or write the first line of the thing you keep postponing. You wake up already ahead."
            ),
            "passo a passo em 3 etapas": (
                "When growth work feels heavy, it is usually because you are planning, doing, and judging "
                "in the same hour.\n\n"
                "Try this: (1) dump what is actually on your mind in bullets — no editing; "
                "(2) circle the one move that would make tomorrow easier; "
                "(3) do only that for 15 minutes on a timer.\n\n"
                "Tiny structure beats another motivational quote."
            ),
            "quebra de crença com prova/exemplo": (
                "You probably do not need more discipline. You need less shame when you slip.\n\n"
                "Most people I work with are not lazy — they are running on empty and still expecting "
                "Olympic output.\n\n"
                "When we shrink the next step until it feels almost silly, completion rate jumps. "
                "Start embarrassingly small."
            ),
            "bastidores de caso real": (
                "Real week snapshot: someone kept saying they had no time for content. "
                "We looked at the calendar — the gap was not hours, it was decision fatigue.\n\n"
                "Old habit: waiting for a perfect hour that never arrives.\n\n"
                "Better move: 20 minutes, same slot daily, same simple template, ship something imperfect on purpose."
            ),
            "checklist de execução semanal": (
                "Your weekly reset does not need a 90-minute life audit.\n\n"
                "Quick checklist: one priority for work, one for health, one for relationships — "
                "each with a single next action written like a text to a friend.\n\n"
                "If it does not fit in one line, it is still too vague."
            ),
        }
        hook_theme = theme or "self-help, coaching, and personal development"
        default_body = (
            f"If {hook_theme} is your world, here is a grounded take: stop collecting tips and start "
            f"with one tiny repeatable action today — timer on, no debate, done beats perfect."
        )
    else:
        bodies = {
            "erro comum + correção prática": (
                "Você conhece aquela sensação de domingo à noite? Você jura que segunda será diferente — "
                "aí abre o celular ‘só um segundo’ e somem quarenta minutos.\n\n"
                "O loop velho: tentar consertar tudo só na força de vontade.\n\n"
                "O ajuste pequeno: escolher uma vitória de 10 minutos antes de dormir — separar roupa, "
                "filar uma tarefa ou escrever a primeira linha daquilo que você adia. Você acorda já na frente."
            ),
            "passo a passo em 3 etapas": (
                "Quando o trabalho de evolução pesa, normalmente é porque você mistura planejar, fazer "
                "e julgar na mesma hora.\n\n"
                "Teste: (1) jogue o que está na cabeça em bullets — sem editar; "
                "(2) circule um passo que deixaria amanhã mais leve; "
                "(3) faça só isso por 15 minutos, com timer.\n\n"
                "Estrutura mínima ganha de mais um vídeo motivacional."
            ),
            "quebra de crença com prova/exemplo": (
                "Você provavelmente não precisa de mais disciplina. Precisa de menos culpa quando escorrega.\n\n"
                "A maioria das pessoas com quem trabalho não é preguiçosa — está no limite e ainda espera "
                "rendimento de atleta.\n\n"
                "Quando a gente encolhe o próximo passo até quase virar piada, a conclusão sobe rápido. "
                "Começa ridículamente pequeno."
            ),
            "bastidores de caso real": (
                "Bastidor da semana: alguém dizia que não tinha tempo pra conteúdo. Olhamos a agenda — "
                "não faltava hora, faltava energia de decisão.\n\n"
                "Hábito antigo: esperar a hora perfeita que nunca chega.\n\n"
                "Ajuste: 20 minutos, mesmo horário todo dia, mesmo modelo simples, posta algo imperfeito de propósito."
            ),
            "checklist de execução semanal": (
                "Seu reset semanal não precisa virar auditoria de vida.\n\n"
                "Checklist rápido: uma prioridade pro trabalho, uma pra saúde, uma pros vínculos — "
                "cada uma com uma próxima ação escrita como mensagem de texto.\n\n"
                "Se não cabe em uma linha, ainda está vago demais."
            ),
        }
        hook_theme = theme or "autoajuda, coaching e desenvolvimento pessoal"
        default_body = (
            f"Se {hook_theme} é o seu jogo, um caminho simples: pare de colecionar dicas e comece com "
            f"uma ação minúscula repetível hoje — timer ligado, sem debate, feito vale mais que perfeito."
        )
    body = bodies.get(angle, default_body)
    if offer:
        o = _clean_sentence(offer)
        if lang == "en":
            body += f"\n\nIf this is the kind of shift you help people make, say it in one honest line: {o}."
        else:
            body += f"\n\nSe esse é o tipo de mudança que você ajuda a construir, diz numa linha honesta: {o}."
    tail = []
    if cta_clean:
        tail.append(cta_clean)
    if hashtags_block:
        tail.append(hashtags_block)
    suffix = "\n\n".join(tail) if tail else ""
    return f"{body}\n\n{suffix}" if suffix else body


async def _enrich_drafts_with_openai_captions(
    draft: list[dict[str, Any]],
    *,
    brief: dict[str, Any] | None,
    dna: dict[str, Any] | None,
) -> None:
    """Substitui legenda estática por copy gerada no Chat quando OPENAI_API_KEY está definida."""
    api_key = (settings.openai_api_key or "").strip()
    if not api_key:
        return
    niche = str((brief or {}).get("niche") or "").strip() or "coaching and mindset"
    target = str((brief or {}).get("target_audience") or "").strip()
    if _is_placeholder_brief(target):
        target = ""
    if not target:
        first_lang = str(draft[0].get("language") or "pt") if draft else "pt"
        target = (
            "people building habits, clarity, and consistency"
            if first_lang == "en"
            else "pessoas construindo hábitos, clareza e consistência"
        )
    tone = str((brief or {}).get("tone_style") or "").strip() or "direct, warm, practical"
    offer = str((brief or {}).get("offer_summary") or "").strip()
    if _is_placeholder_brief(offer):
        offer = ""
    themes = [str(x).strip() for x in (dna or {}).get("themes") or [] if str(x).strip()][:8]
    sem = asyncio.Semaphore(3)

    async def one_row(d: dict[str, Any]) -> None:
        async with sem:
            lang = str(d.get("language") or "pt")
            out_lang = "en" if lang == "en" else "pt"
            trace = d.get("debug_trace") if isinstance(d.get("debug_trace"), dict) else {}
            st2 = trace.get("stage_2_signals") if isinstance(trace.get("stage_2_signals"), dict) else {}
            angle = str(st2.get("selected_angle") or "")
            cta_raw = str(st2.get("cta_hint") or "")
            cta_line = _clean_sentence(cta_raw.replace("CTA:", ""))
            if not cta_line:
                cta_line = (
                    "Comenta uma palavra-chave e te chamo no DM."
                    if out_lang != "en"
                    else "Comment with a keyword and I will send the details in DM."
                )
            anchor = str(d.get("anchor_caption") or "")
            focus_topic = str(d.get("focus_topic") or "")
            cap = await openai_caption.generate_caption_openai(
                api_key,
                model=settings.openai_caption_model,
                output_language=out_lang,
                niche=niche,
                target_audience=target,
                tone_style=tone,
                offer_summary=offer,
                angle=angle,
                focus_topic=focus_topic,
                themes=themes,
                anchor_post_excerpt=anchor,
                cta_line=cta_line,
            )
            if cap:
                d["suggestion_text"] = cap
                st3 = trace.get("stage_3_outputs")
                if isinstance(st3, dict):
                    st3["caption_preview"] = cap[:280]
                    st3["caption_source"] = "openai_chat"

    await asyncio.gather(*[one_row(d) for d in draft])


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
    lang, lang_source = _resolve_caption_language(brief, dna, ranked)
    brief_lang_raw = str((brief or {}).get("preferred_language") or "").strip()
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
    if lang == "en" and _looks_portuguese(offer):
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
        cta_clean = _clean_sentence(cta_hint.replace("CTA:", ""))
        kws = [
            k.strip().replace(" ", "")
            for k in (
                keywords[:3]
                if keywords
                else (["mindset", "coaching", "growth"] if lang == "en" else ["mindset", "coaching", "evolucao"])
            )
            if k.strip()
        ]
        keyword_tags = " ".join([f"#{k}" for k in kws[:3]])
        focus_tags = " ".join(
            [f"#{t.replace(' ', '')}" for t in focus_topic.split(",")[:2] if t.strip()]
        )
        hashtags_block = (f"{keyword_tags} {focus_tags}").strip()
        suggestion_text = _reader_facing_caption(
            lang=lang,
            angle=angle,
            cta_clean=cta_clean,
            hashtags_block=hashtags_block,
            offer=offer,
            focus_topic=focus_topic,
            focus=focus,
        )
        suggestion_text = clean_blocked(suggestion_text)
        creative_prompt = _safe_creative_scene(idx)
        debug_trace = {
            "stage_1_inputs": {
                "ig_user_id": ig_user_id,
                "source_media_id": str(m.get("id") or ""),
                "focus_topic_input": focus_topic,
                "preferred_language": brief_lang_raw or "(auto)",
                "caption_language_resolved": lang,
                "caption_language_source": lang_source,
                "brief": {
                    "niche": niche,
                    "target_audience": target,
                    "objective": objective,
                    "offer_summary": offer,
                    "tone_style": tone_style,
                    "do_not_use_terms": ",".join(blocked_terms),
                },
            },
            "stage_2_signals": {
                "detected_language": lang,
                "top_keywords": keywords[:6],
                "selected_angle": angle,
                "selected_focus": focus,
                "tone_hint": tone_hint,
                "cta_hint": cta_hint,
            },
            "stage_3_outputs": {
                "caption_preview": suggestion_text[:280],
                "caption_source": "static_reader_v3",
                "creative_prompt": creative_prompt,
            },
        }
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
                "debug_trace": debug_trace,
                "anchor_caption": str(m.get("caption") or "")[:900],
            }
        )
    if not out:
        out.append(
            {
                "source_media_id": None,
                "suggestion_text": (
                    "Três erros silenciosos que travam consistência no Instagram:\n\n"
                    "1) Você só posta quando “inspira” — e inspiração é evento raro.\n"
                    "2) Você mistura planejar, produzir e julgar no mesmo bloco de tempo.\n"
                    "3) Você espera perfeição antes de publicar.\n\n"
                    "Troca mínima: 20 minutos no mesmo horário, mesmo formato, publicar algo simples e repetir.\n\n"
                    "Comenta CHECKLIST que eu te mando o passo a passo no DM.\n\n"
                    "#mindset #instagram #consistencia"
                ),
                "rationale": f"Fallback para IG {ig_user_id} sem mídias suficientes.",
                "creative_prompt": _safe_creative_scene(0),
                "creative_image_url": None,
                "suggested_date": base_date.isoformat(),
                "frequency_per_week": frequency_per_week,
                "focus_topic": focus_topic or "consistência no Instagram",
                "language": "pt",
                "anchor_caption": "",
                "debug_trace": {
                    "stage_3_outputs": {"caption_source": "static_fallback"},
                },
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
    image_style: str = Query(
        "v1_realistic",
        description="Preset visual para geração de imagem: v1_realistic | v2_editorial | v3_minimal",
    ),
    debug: bool = Query(False, description="Retorna debug_trace por sugestão para inspeção passo a passo."),
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
    await _enrich_drafts_with_openai_captions(draft, brief=brief_saved, dna=dna_saved)
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
                creative_prompt = str(row.get("creative_prompt") or "")
                caption_text = str(row.get("suggestion_text") or "")
                url = await openai_image.generate_image_url(
                    settings.openai_api_key,
                    creative_prompt,
                    caption=caption_text,
                    style=image_style,
                    model=settings.openai_image_model,
                )
                if url:
                    await update_suggestion_creative_image_url(int(row["id"]), url)
                    row["creative_image_url"] = url

        await asyncio.gather(*[enhance_creative(r) for r in saved])

    normalized = [_normalize_suggestion_creative_url(s) for s in saved]
    if debug:
        for i, row in enumerate(normalized):
            if i < len(draft) and isinstance(draft[i], dict):
                row["debug_trace"] = draft[i].get("debug_trace")
            row["debug_trace"] = row.get("debug_trace") or {}
            row["debug_trace"]["image_style"] = image_style
            row["debug_trace"]["image_prompt_final"] = openai_image.build_image_prompt(
                creative_prompt=str(row.get("creative_prompt") or ""),
                caption=str(row.get("suggestion_text") or ""),
                style=image_style,
            )
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
async def get_brief(ig_user_id: str, response: Response) -> ProfileBriefResponse:
    """Devolve o último briefing gravado; campos vazios são preenchidos com sugestões do DNA (posts recentes)."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
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
