"""Optional OpenAI Chat for Instagram-ready captions (Pilotgram)."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CHAT_URL = "https://api.openai.com/v1/chat/completions"


async def generate_caption_openai(
    api_key: str,
    *,
    model: str = "gpt-4o-mini",
    output_language: str,
    niche: str,
    target_audience: str,
    tone_style: str,
    offer_summary: str,
    angle: str,
    focus_topic: str,
    themes: list[str],
    anchor_post_excerpt: str,
    cta_line: str,
    timeout_s: float = 90.0,
) -> str | None:
    if not (api_key or "").strip():
        return None
    lang_label = "English" if output_language == "en" else "Portuguese (Brazil)"
    lang_lock = (
        "LANGUAGE LOCK: Every word of the caption must be in English (US). "
        "Do not use Portuguese, Spanish, or French. "
        "If the inspiration excerpt below is in another language, translate ideas only — output stays English."
        if output_language == "en"
        else "LANGUAGE LOCK: Every word must be in Portuguese (Brazil). Do not use English sentences."
    )
    system = (
        "You are a senior Instagram copywriter. Write ONE caption ready to post for followers. "
        "Never give instructions to the creator ('tell a story', 'name the habit'). "
        "Never expose internal business strategy. No template labels. "
        f"{lang_lock} "
        f"Primary language label: {lang_label} only."
    )
    user = {
        "task": "Write one Instagram caption (hook + short body + natural CTA + 4-6 hashtags).",
        "mandatory_output_language": lang_label,
        "rules": [
            "Speak directly to the reader in second person or inclusive 'we'.",
            "One concrete relatable situation + one clear actionable micro-shift.",
            "No clichés: believe in yourself, you got this, everything happens for a reason.",
            "No words: engagement, funnel, conversion, target audience, business objective.",
            "End with the CTA line provided (adapt slightly if needed for flow).",
        ],
        "brand": {
            "niche": niche,
            "audience": target_audience,
            "tone": tone_style,
            "offer_context_internal": offer_summary,
        },
        "content_signals": {
            "angle": angle,
            "focus_topic": focus_topic,
            "themes_from_posts": themes[:8],
            "inspiration_from_recent_post": anchor_post_excerpt[:400],
        },
        "cta_to_include": cta_line,
    }
    body: dict[str, Any] = {
        "model": model.strip(),
        "temperature": 0.75,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": "Return only the caption text, ready to paste on Instagram.\n\n"
                + json.dumps(user, ensure_ascii=False),
            },
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.post(
                CHAT_URL,
                headers={
                    "Authorization": f"Bearer {api_key.strip()}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            if r.status_code >= 400:
                logger.warning("OpenAI chat caption error %s: %s", r.status_code, r.text[:400])
                return None
            data = r.json()
            choices = data.get("choices") or []
            if not choices:
                return None
            msg = choices[0].get("message") or {}
            text = str(msg.get("content") or "").strip()
            return text if text else None
    except Exception:
        logger.exception("OpenAI chat caption request failed")
        return None
