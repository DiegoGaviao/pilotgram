import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
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

# CORS estável para o SPA (dhawk, preview, localhost com VITE_PG_API_URL):
# o dashboard não envia cookies para pilotgram.onrender.com — com credentials=False
# o browser aceita Access-Control-Allow-Origin: * e o preflight PUT/POST deixa de falhar
# por lista/regex de origens (www vs sem www, subpath, etc.).
# PG_CORS_ORIGINS no .env continua documentado no COPY_PASTE_PG.md; não é obrigatório para CORS com *.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        "caption_engine_version": "post-ready-v3-generate-hardening-2026-03-31",
    }


@app.get("/")
async def root() -> dict:
    return {"service": "pilotgram", "docs": "/docs"}
