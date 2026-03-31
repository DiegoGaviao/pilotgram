#!/usr/bin/env python3
"""
Interactive debugger for Pilotgram content pipeline.

Flow:
1) Select page
2) Read recent posts + local analysis (keywords/tone/language)
3) Read questionnaire (brief) and show interpreted values
4) Generate one suggestion with debug=true
5) Show exact caption inputs + image prompt sent to OpenAI
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from typing import Any


STOPWORDS = {
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
    "from",
}


def api_get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def wait(stage: str) -> None:
    input(f"\n[{stage}] Press Enter to continue...")


def detect_language(captions: list[str]) -> str:
    text = " ".join(captions).lower()
    if not text.strip():
        return "pt"
    en_markers = [r"\bthe\b", r"\band\b", r"\byour\b", r"\byou\b", r"\bwith\b"]
    pt_markers = [r"\bvocê\b", r"\bpara\b", r"\bcom\b", r"\bque\b", r"\buma\b"]
    en = sum(len(re.findall(p, text)) for p in en_markers)
    pt = sum(len(re.findall(p, text)) for p in pt_markers)
    return "en" if en > pt else "pt"


def keywords_from_captions(captions: list[str], limit: int = 12) -> list[str]:
    tags = Counter()
    words = Counter()
    for caption in captions:
        low = caption.lower()
        for t in re.findall(r"#([a-z0-9_]{3,})", low):
            if t not in STOPWORDS:
                tags[t] += 1
        for w in re.findall(r"[a-zà-ú0-9_]{4,}", low):
            if w in STOPWORDS or w.startswith("http"):
                continue
            words[w] += 1
    out: list[str] = []
    out.extend([k for k, _ in tags.most_common(limit)])
    for k, _ in words.most_common(limit):
        if k not in out:
            out.append(k)
    return out[:limit]


def estimate_tone(captions: list[str]) -> str:
    text = " ".join(captions).lower()
    if "?" in text:
        return "conversational/question-driven"
    if any(x in text for x in ["comenta", "dm", "direct", "comment"]):
        return "action/cta-oriented"
    return "didactic/authority"


def build_openai_image_prompt(creative_prompt: str) -> str:
    guardrails = (
        "Create a single Instagram square cover image (1:1). "
        "ABSOLUTE RULE: no text, no letters, no words, no numbers, no logos, no watermarks, "
        "no UI screens, no typographic elements of any kind. "
        "Use only symbolic visual elements and people/objects/scenes related to the topic. "
        "If any text would normally appear, replace it with abstract shapes or icons. "
    )
    return (guardrails + creative_prompt.strip())[:3900]


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactive debug for Pilotgram content engine.")
    parser.add_argument("--api-base", default="https://pilotgram.onrender.com")
    parser.add_argument("--page", default="", help="Page name contains filter (optional).")
    parser.add_argument("--ig-user-id", default="", help="Direct IG user id (optional).")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--frequency", type=int, default=2)
    parser.add_argument("--focus-topic", default="self-help,coaching,personal development")
    args = parser.parse_args()

    base = args.api_base.rstrip("/")
    print("\n=== STAGE 0: HEALTH/CURRENT SESSION ===")
    health = api_get_json(f"{base}/health")
    session = api_get_json(f"{base}/api/v1/meta/session")
    print(json.dumps(health, indent=2, ensure_ascii=False))
    print(json.dumps(session, indent=2, ensure_ascii=False))
    wait("Stage 0")

    print("\n=== STAGE 1: SELECT PAGE ===")
    pages = api_get_json(f"{base}/api/v1/meta/pages")
    chosen: dict[str, Any] | None = None
    if args.ig_user_id:
        chosen = next((p for p in pages if str(p.get("ig_user_id") or "") == args.ig_user_id), None)
    elif args.page:
        page_filter = args.page.lower()
        chosen = next((p for p in pages if page_filter in str(p.get("page_name") or "").lower()), None)
    else:
        # default: pick start_u2 when available
        chosen = next((p for p in pages if str(p.get("ig_username") or "") == "start_u2"), None)
        if not chosen:
            chosen = next((p for p in pages if p.get("ig_user_id")), None)
    if not chosen:
        print("No page with IG user found.")
        return 1
    print(json.dumps(chosen, indent=2, ensure_ascii=False))
    ig_user_id = str(chosen.get("ig_user_id") or "")
    wait("Stage 1")

    print("\n=== STAGE 2: READ POSTS + LOCAL ANALYSIS ===")
    media = api_get_json(f"{base}/api/v1/meta/ig/{ig_user_id}/media?limit=12")
    items: list[dict[str, Any]] = list(media.get("data") or [])
    captions = [str(x.get("caption") or "") for x in items if str(x.get("caption") or "").strip()]
    preview = []
    for i, row in enumerate(items[:5], start=1):
        preview.append(
            {
                "idx": i,
                "id": row.get("id"),
                "media_type": row.get("media_type"),
                "like_count": row.get("like_count"),
                "comments_count": row.get("comments_count"),
                "caption_preview": (str(row.get("caption") or "").replace("\n", " "))[:140],
            }
        )
    analysis = {
        "posts_fetched": len(items),
        "language_estimate": detect_language(captions),
        "tone_estimate": estimate_tone(captions),
        "top_keywords": keywords_from_captions(captions, limit=12),
        "post_preview": preview,
    }
    print(json.dumps(analysis, indent=2, ensure_ascii=False))
    wait("Stage 2")

    print("\n=== STAGE 3: READ QUESTIONNAIRE (BRIEF) + DNA ===")
    brief = api_get_json(f"{base}/api/v1/meta/ig/{ig_user_id}/brief")
    try:
        dna = api_get_json(f"{base}/api/v1/meta/ig/{ig_user_id}/dna")
    except Exception:
        dna = {"note": "dna unavailable"}
    print("BRIEF:")
    print(json.dumps(brief, indent=2, ensure_ascii=False))
    print("\nDNA:")
    print(json.dumps(dna, indent=2, ensure_ascii=False))
    wait("Stage 3")

    print("\n=== STAGE 4: GENERATE WITH DEBUG TRACE ===")
    qs = urllib.parse.urlencode(
        {
            "count": max(1, min(args.count, 3)),
            "frequency_per_week": max(1, min(args.frequency, 7)),
            "focus_topic": args.focus_topic,
            "debug": "true",
        }
    )
    gen_url = f"{base}/api/v1/meta/ig/{ig_user_id}/suggestions/generate?{qs}"
    req = urllib.request.Request(gen_url, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        generated = json.loads(resp.read().decode("utf-8"))
    first = (generated.get("data") or [{}])[0]
    trace = first.get("debug_trace") or {}
    print("CAPTION:")
    print(first.get("suggestion_text") or "")
    print("\nDEBUG TRACE:")
    print(json.dumps(trace, indent=2, ensure_ascii=False))
    wait("Stage 4")

    print("\n=== STAGE 5: EXACT IMAGE PROMPT SENT TO OPENAI ===")
    creative_prompt = str(first.get("creative_prompt") or "")
    final_image_prompt = build_openai_image_prompt(creative_prompt)
    print("creative_prompt:")
    print(creative_prompt)
    print("\nopenai_prompt_with_guardrails:")
    print(final_image_prompt)

    print("\n=== DONE ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
