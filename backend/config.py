from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """
    Convenção env:
    - PG_* → Pilotgram (CORS, portas, Supabase com nome explícito)
    - SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / SUPABASE_KEY → mesmo projeto que o backend Leads AI (aliases aceites)
    - META_* → app Meta (pode ser o mesmo app do Leads; redirect URI do Pilotgram é específico)
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    meta_app_id: str = Field("", validation_alias=AliasChoices("META_APP_ID"))
    meta_app_secret: str = Field("", validation_alias=AliasChoices("META_APP_SECRET"))
    meta_oauth_redirect_uri: str = Field(
        "https://www.dhawk.com.br/projetos/pilotgram/oauth/callback",
        validation_alias=AliasChoices("META_OAUTH_REDIRECT_URI"),
    )
    meta_graph_version: str = Field("v21.0", validation_alias=AliasChoices("META_GRAPH_VERSION"))

    cors_origins: str = Field(
        "https://www.dhawk.com.br,https://dhawk.com.br",
        validation_alias=AliasChoices("PG_CORS_ORIGINS", "CORS_ORIGINS"),
    )

    pilotgram_api_host: str = Field(
        "0.0.0.0",
        validation_alias=AliasChoices("PG_API_HOST", "PILOTGRAM_API_HOST", "IGCA_API_HOST"),
    )
    pilotgram_api_port: int = Field(
        8765,
        validation_alias=AliasChoices("PG_API_PORT", "PILOTGRAM_API_PORT", "IGCA_API_PORT"),
    )
    pilotgram_sqlite_path: str = Field(
        str(_BACKEND_ROOT / "data" / "pilotgram.sqlite3"),
        validation_alias=AliasChoices(
            "PG_SQLITE_PATH", "PILOTGRAM_SQLITE_PATH", "IGCA_SQLITE_PATH"
        ),
    )

    supabase_url: str = Field(
        "",
        validation_alias=AliasChoices("PG_SUPABASE_URL", "SUPABASE_URL"),
    )
    supabase_service_role_key: str = Field(
        "",
        validation_alias=AliasChoices(
            "PG_SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_KEY",  # mesmo nome que o backend Leads AI no Render (normalmente service_role)
        ),
    )

    @property
    def graph_base(self) -> str:
        v = self.meta_graph_version.strip().lstrip("v")
        return f"https://graph.facebook.com/v{v}"

    @property
    def use_supabase_for_token(self) -> bool:
        return bool(self.supabase_url.strip() and self.supabase_service_role_key.strip())

    public_api_url: str = Field(
        "",
        validation_alias=AliasChoices("PG_PUBLIC_API_URL", "PUBLIC_API_URL"),
    )
    render_external_url: str = Field(
        "",
        validation_alias=AliasChoices("RENDER_EXTERNAL_URL"),
    )
    # Se RENDER_EXTERNAL_URL falhar, último recurso para montar URL de <img> do criativo (definir vazio para desligar).
    public_api_fallback: str = Field(
        "https://pilotgram.onrender.com",
        validation_alias=AliasChoices("PG_PUBLIC_API_FALLBACK"),
    )
    openai_api_key: str = Field(
        "",
        validation_alias=AliasChoices("OPENAI_API_KEY", "PG_OPENAI_API_KEY"),
    )
    openai_image_model: str = Field(
        "dall-e-3",
        validation_alias=AliasChoices("PG_OPENAI_IMAGE_MODEL", "OPENAI_IMAGE_MODEL"),
    )
    openai_caption_model: str = Field(
        "gpt-4o-mini",
        validation_alias=AliasChoices("PG_OPENAI_CAPTION_MODEL", "OPENAI_CAPTION_MODEL"),
    )

    @property
    def effective_public_api_base(self) -> str:
        """Base URL HTTPS da API (para <img src=...> servido pelo próprio backend)."""
        for candidate in (self.public_api_url, self.render_external_url):
            c = (candidate or "").strip().rstrip("/")
            if c:
                return c
        fb = (self.public_api_fallback or "").strip().rstrip("/")
        return fb


settings = Settings()
