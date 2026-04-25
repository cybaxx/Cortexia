"""Application settings (environment-driven). `backend/.env` is always resolved next to the backend root."""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_BACKEND_DIR / ".env"),),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # K2 Think (OpenAI-compatible): https://api.k2think.ai/v1/chat/completions
    ifm_api_url: str = Field(
        default="https://api.k2think.ai/v1/chat/completions",
        description="K2 chat-completions URL (set empty to force local mock K2).",
    )
    ifm_k2_model: str = Field(
        default="MBZUAI-IFM/K2-Think-v2",
        description="Model id in the K2 request body.",
    )
    ifm_api_key: str = Field(
        default="",
        description="Bearer token for api.k2think.ai (or IFM).",
        validation_alias=AliasChoices("ifm_api_key", "IFM_API_KEY", "K2_THINK_API_KEY", "k2_think_api_key"),
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

    # One-shot HTTP simulation (Modal + K2)
    simulate_population_size: int = Field(
        default=110,
        ge=24,
        le=220,
        description="Synthetic agent count generated for each /api/simulate request.",
    )
    simulate_k2_concurrency: int = Field(
        default=10,
        ge=1,
        le=32,
        description="Concurrent per-agent K2 calls during /api/simulate.",
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
