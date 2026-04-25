"""Application settings (environment-driven). `backend/.env` is always resolved next to the backend root."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _default_database_url() -> str:
    p = _BACKEND_DIR / "cortexia.db"
    return f"sqlite+aiosqlite:///{p.as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_BACKEND_DIR / ".env"),),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # SQLite
    database_url: str = Field(
        default_factory=_default_database_url,
        description="Async SQLAlchemy URL",
    )

    # IFM K2 Think
    ifm_api_url: str = Field(
        default="",
        description="Full HTTP URL for K2 Think API",
    )
    ifm_api_key: str = Field(
        default="",
        description="Optional bearer/API key for IFM",
    )

    # ElevenLabs
    elevenlabs_api_key: str = Field(default="")
    elevenlabs_voice_id: str = Field(default="")

    # TRIBE v2 on Modal (same as `tribe_modal_deployment_url()` in app.constants)
    tribe_modal_url: str = Field(
        default="",
        description="Deployed Modal extract_bsv endpoint base URL (TRIBE_MODAL_URL)",
    )
    # Only if the Modal endpoint was deployed with requires_proxy_auth=True
    tribe_modal_key: str = Field(
        default="",
        description="Modal-Key header (token id) for protected web endpoints",
    )
    tribe_modal_secret: str = Field(
        default="",
        description="Modal-Secret header (token secret) for protected web endpoints",
    )

    # CORS
    cors_origins: str = Field(
        default=(
            "http://localhost:3000,http://127.0.0.1:3000,"
            "http://localhost:8080,http://127.0.0.1:8080,"
            "http://localhost:5173,http://127.0.0.1:5173"
        ),
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
