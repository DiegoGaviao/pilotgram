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

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins
    or ["https://www.dhawk.com.br", "https://dhawk.com.br"],
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
    }


@app.get("/")
async def root() -> dict:
    return {"service": "pilotgram", "docs": "/docs"}
