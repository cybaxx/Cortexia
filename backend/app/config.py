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

    hf_token: str = Field(
        default="",
        description="Hugging Face token with access to gated TRIBE dependencies such as Llama 3.2.",
        validation_alias=AliasChoices("hf_token", "HF_TOKEN", "huggingface_token", "HUGGINGFACE_TOKEN"),
    )
    tribe_runtime_mode: str = Field(
        default="framework",
        description="Neural pipeline runtime: 'framework' for local tribe_neural processing, 'modal' for remote web endpoint.",
    )
    tribe_data_dir: str = Field(
        default=str(_BACKEND_DIR / "tribe_data"),
        description="Local cache/data directory for the vendored tribe_neural framework.",
    )
    tribe_device: str = Field(
        default="",
        description="Device override for TRIBE inference: 'cuda', 'mps', or 'cpu'. Auto-detected if empty.",
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
    elevenlabs_stt_model: str = Field(
        default="scribe_v2",
        description="ElevenLabs Speech-to-Text model id.",
    )

    # Action Center live research providers
    tavily_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("tavily_api_key", "TAVILY_API_KEY"),
        description="Tavily API key for live web research in the final Action Center step.",
    )
    firecrawl_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("firecrawl_api_key", "FIRECRAWL_API_KEY"),
        description="Firecrawl API key for structured extraction in the final Action Center step.",
    )
    action_center_max_sources: int = Field(
        default=6,
        ge=2,
        le=12,
        description="Maximum number of live web sources to pull into the Action Center dossier.",
    )
    action_center_timeout_seconds: float = Field(
        default=35.0,
        gt=5.0,
        le=120.0,
        description="Timeout for Action Center provider calls such as Tavily and Firecrawl.",
    )

    # TRIBE v2 on Modal
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
        default=72,
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
    simulate_source_fetch_timeout_seconds: float = Field(
        default=15.0,
        gt=1.0,
        le=120.0,
        description="Timeout for fetching source URLs.",
    )
    simulate_tribe_timeout_seconds: float = Field(
        default=120.0,
        gt=5.0,
        le=600.0,
        description="Timeout for TRIBE batch inference.",
    )
    simulate_k2_timeout_seconds: float = Field(
        default=90.0,
        gt=5.0,
        le=300.0,
        description="Timeout for each agent K2 reasoning call.",
    )
    simulate_total_timeout_seconds: float = Field(
        default=180.0,
        gt=10.0,
        le=3600.0,
        description="Hard timeout for the full /api/simulate pipeline.",
    )
    pipeline_db_path: str = Field(
        default=str(_BACKEND_DIR / "cortexia.db"),
        description="Local SQLite path for persisted case runs and agent outcomes.",
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
