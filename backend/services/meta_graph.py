"""Client mínimo para OAuth e Instagram Graph API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from config import settings

logger = logging.getLogger(__name__)

# Escopos para: listar páginas, ver IG ligado, ler mídias, insights, publicar.
# App Review exigido para produção além do modo desenvolvimento.
DEFAULT_SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "instagram_basic",
    "instagram_manage_insights",
    "instagram_content_publish",
    "business_management",
]


def oauth_authorize_url(state: str) -> str:
    if not settings.meta_app_id or not settings.meta_oauth_redirect_uri:
        raise ValueError("META_APP_ID e META_OAUTH_REDIRECT_URI são obrigatórios")
    scope = ",".join(DEFAULT_SCOPES)
    from urllib.parse import urlencode

    q = urlencode(
        {
            "client_id": settings.meta_app_id,
            "redirect_uri": settings.meta_oauth_redirect_uri,
            "scope": scope,
            "state": state,
            "response_type": "code",
        }
    )
    v = settings.meta_graph_version.strip().lstrip("v")
    return f"https://www.facebook.com/v{v}/dialog/oauth?{q}"


async def exchange_code_for_short_lived_token(code: str) -> dict[str, Any]:
    """Troca o `code` por user access token (curta duração)."""
    url = f"{settings.graph_base}/oauth/access_token"
    params = {
        "client_id": settings.meta_app_id,
        "client_secret": settings.meta_app_secret,
        "redirect_uri": settings.meta_oauth_redirect_uri,
        "code": code,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()


async def exchange_for_long_lived_user_token(short_token: str) -> dict[str, Any]:
    """Estende user token (~60 dias)."""
    url = f"{settings.graph_base}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": settings.meta_app_id,
        "client_secret": settings.meta_app_secret,
        "fb_exchange_token": short_token,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()


async def fetch_pages_with_instagram(access_token: str) -> list[dict[str, Any]]:
    """
    Páginas que o usuário pode gerenciar + instagram_business_account.
    """
    fields = "id,name,instagram_business_account{id,username,profile_picture_url}"
    url = f"{settings.graph_base}/me/accounts"
    params = {"fields": fields, "access_token": access_token}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, params=params)
        if r.status_code != 200:
            logger.warning("me/accounts falhou: %s %s", r.status_code, r.text)
            r.raise_for_status()
        data = r.json()
    return data.get("data", [])


async def fetch_ig_media(
    access_token: str,
    ig_user_id: str,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """
    Mídias recentes. Campos variam conforme tipo; alguns só aparecem com permissões extras.
    """
    fields = (
        "id,caption,media_type,media_url,permalink,thumbnail_url,timestamp,"
        "like_count,comments_count"
    )
    url = f"{settings.graph_base}/{ig_user_id}/media"
    params = {"fields": fields, "limit": limit, "access_token": access_token}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, params=params)
        if r.status_code != 200:
            logger.warning("IG media falhou: %s %s", r.status_code, r.text)
            r.raise_for_status()
        data = r.json()
    return data.get("data", [])


async def fetch_media_insights(
    access_token: str,
    media_id: str,
    metrics: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Insights por mídia (quando permitido pela API / tipo de mídia)."""
    if metrics is None:
        metrics = ["engagement", "impressions", "reach", "saved"]
    url = f"{settings.graph_base}/{media_id}/insights"
    params = {
        "metric": ",".join(metrics),
        "access_token": access_token,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, params=params)
        if r.status_code != 200:
            logger.info("insights não disponíveis para %s: %s", media_id, r.text[:200])
            return []
        data = r.json()
    return data.get("data", [])
