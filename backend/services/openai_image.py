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
        "warm natural light, everyday coaching/self-help mood. "
        "Grounded real-world settings only: home desk, morning light, park walk, quiet café, "
        "simple objects. No mystical glow halos, no cosmic diagrams, no surreal spiritual art."
    ),
    "v2_editorial": (
        "Premium editorial lifestyle aesthetic, clean composition, elegant visual hierarchy, "
        "subtle color grading, modern social media cover look. "
        "Real photography feel, mundane relatable props, no fantasy spirituality or esoteric symbols."
    ),
    "v3_minimal": (
        "Minimalist visual metaphor, high negative space, simple geometric balance, "
        "quiet and focused mood, clean modern style. "
        "Abstract shapes only as soft gradients or plain geometry — no glyphs, no fake icons with letters."
    ),
}

# Text + religion: DALL·E still sometimes renders pseudo-text; we repeat bans and steer scene away from UI/diagrams.
_TEXT_AND_RELIGION_GUARDRAILS = (
    "TEXT BAN (strict): no readable text, no pseudo-text, no gibberish letters, no fake words, "
    "no alphabet characters, no numbers, no captions, no labels above panels, no signs, "
    "no posters with writing, no book titles, no phone screens with UI, no floating typography. "
    "Do not draw comparison panels titled Old/New/Better or any English words on the image. "
    "RELIGION (strict): no religious imagery except Roman Catholic Christian symbols when clearly appropriate; "
    "otherwise use zero religious symbols. "
    "Forbidden: Hindu/Buddhist/Sikh/New Age/Eastern guru or monk imagery, yoga-meditation guru aesthetics, "
    "mandala as spiritual symbol, prayer hall that looks generic cult, mystical cosmic wheels, "
    "alchemical diagrams, golden occult circles, tarot, crystals as spiritual focus, incense-shrine vibes. "
    "If faith appears at all, only neutral Roman Catholic context (e.g. simple crucifix in a real church) — "
    "when in doubt, keep the scene fully secular. "
)


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
        "The caption was already written separately — this image must only illustrate the mood and topic visually, "
        "without repeating or labeling the message. "
        + _TEXT_AND_RELIGION_GUARDRAILS
        + "Use everyday symbolic visuals: light through a window, hands on a blank notebook, walking outdoors, "
        "one calm breath moment, organized desk with blank paper, sunrise on a normal city horizon. "
        "No logos, no watermarks. "
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
