"""Optional OpenAI Images API for Pilotgram creative previews."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"


async def generate_image_url(
    api_key: str,
    prompt: str,
    *,
    model: str = "dall-e-3",
    size: str = "1024x1024",
    timeout_s: float = 120.0,
) -> str | None:
    if not api_key.strip() or not (prompt or "").strip():
        return None
    body: dict[str, Any] = {
        "model": model.strip(),
        "prompt": prompt.strip()[:4000],
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
