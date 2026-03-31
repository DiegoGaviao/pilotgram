"""Optional OpenAI Images API for Pilotgram creative previews."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"


STYLE_PRESETS: dict[str, str] = {
    "v1_realistic": (
        "Photorealistic cinematic scene, emotionally grounded, realistic people and environments, "
        "warm natural light, practical coaching/self-help mood."
    ),
    "v2_editorial": (
        "Premium editorial lifestyle aesthetic, clean composition, elegant visual hierarchy, "
        "subtle color grading, modern social media cover look."
    ),
    "v3_minimal": (
        "Minimalist visual metaphor, high negative space, simple geometric balance, "
        "quiet and focused mood, clean modern style."
    ),
}


def build_image_prompt(
    *,
    creative_prompt: str,
    caption: str = "",
    style: str = "v1_realistic",
) -> str:
    """Build the final image prompt after caption generation."""
    base = (creative_prompt or "").strip()
    if not base:
        return ""
    style_key = (style or "v1_realistic").strip().lower()
    style_block = STYLE_PRESETS.get(style_key, STYLE_PRESETS["v1_realistic"])
    caption_hint = " ".join((caption or "").strip().split())[:260]
    guardrails = (
        "Create a single Instagram square cover image (1:1). "
        "ABSOLUTE RULE: no text, no letters, no words, no numbers, no logos, no watermarks, "
        "no UI screens, no typographic elements of any kind. "
        "Use only symbolic visual elements and people/objects/scenes related to the topic. "
        "If any text would normally appear, replace it with abstract shapes or icons. "
    )
    context = (
        f"Visual style preset: {style_key}. {style_block} "
        + (f"Caption context (internal reference only): {caption_hint}. " if caption_hint else "")
        + f"Creative direction: {base}"
    )
    return (guardrails + context)[:3900]


async def generate_image_url(
    api_key: str,
    prompt: str,
    *,
    caption: str = "",
    style: str = "v1_realistic",
    model: str = "dall-e-3",
    size: str = "1024x1024",
    timeout_s: float = 120.0,
) -> str | None:
    if not api_key.strip() or not (prompt or "").strip():
        return None
    final_prompt = build_image_prompt(
        creative_prompt=prompt,
        caption=caption,
        style=style,
    )
    body: dict[str, Any] = {
        "model": model.strip(),
        "prompt": final_prompt,
        "n": 1,
        "size": size,
        "response_format": "url",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.post(
                OPENAI_IMAGES_URL,
                headers={
                    "Authorization": f"Bearer {api_key.strip()}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            if r.status_code >= 400:
                logger.warning("OpenAI images error %s: %s", r.status_code, r.text[:500])
                return None
            data = r.json()
            arr = data.get("data") or []
            if not arr:
                return None
            url = arr[0].get("url")
            return str(url) if url else None
    except Exception:
        logger.exception("OpenAI images request failed")
        return None
