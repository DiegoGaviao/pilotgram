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

# União com os dois hostnames Dhawk: no Render, PG_CORS_ORIGINS às vezes fica só com www
# e o browser em https://dhawk.com.br bloqueia com "No Access-Control-Allow-Origin".
_DHAWK = frozenset({"https://www.dhawk.com.br", "https://dhawk.com.br"})
_env = {o.strip() for o in settings.cors_origins.split(",") if o.strip()}
_cors_origins = sorted(_env | _DHAWK)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"^https://(www\.)?dhawk\.com\.br$",
    allow_credentials=True,
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
        "caption_engine_version": "post-ready-v3-brief-sync-2026-04-01",
    }


@app.get("/")
async def root() -> dict:
    return {"service": "pilotgram", "docs": "/docs"}
