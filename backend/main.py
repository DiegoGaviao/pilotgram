import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import settings
from cors_middleware import PilotgramCORSMiddleware
from database import init_db
from routers import meta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
    force=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Pilotgram API",
    description="OAuth Meta + Instagram + Supabase. Dhawk Labs.",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS manual: preflight OPTIONS + cabeçalhos em erro (evita "No Access-Control-Allow-Origin" no /brief PUT).
app.add_middleware(PilotgramCORSMiddleware)

app.include_router(meta.router)


@app.get("/health")
async def health() -> dict:
    has_meta = bool(settings.meta_app_id and settings.meta_app_secret)
    mode = "supabase" if settings.use_supabase_for_token else "solo_sqlite"
    return {
        "status": "ok",
        "service": "pilotgram",
        "meta_app_configured": has_meta,
        "graph_version": settings.meta_graph_version,
        "token_store": mode,
        "sqlite_path": None if settings.use_supabase_for_token else settings.pilotgram_sqlite_path,
        "supabase_configured": settings.use_supabase_for_token,
        "public_api_base_configured": bool(settings.effective_public_api_base),
        "public_api_base": settings.effective_public_api_base or None,
        "openai_image_configured": bool((settings.openai_api_key or "").strip()),
        "caption_engine_version": "post-ready-v3-cors-mw-2026-04-01",
    }


@app.get("/")
async def root() -> dict:
    return {"service": "pilotgram", "docs": "/docs"}
