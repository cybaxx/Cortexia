"""Cortexia FastAPI orchestrator for independent agent simulation."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.api_simulation import run_simulation_http

settings = get_settings()
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Cortexia API ready; CORS=%s", settings.cors_origin_list)
    yield


app = FastAPI(
    title="Cortexia Cognitive Impact API",
    version="0.2.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SimulateIn(BaseModel):
    catalyst_text: str = Field(..., min_length=1)
    source_url: str | None = None
    city_id: str = "la"
    use_case: str = "political"
    message_complexity: float = Field(0.5, ge=0.0, le=1.0)


@app.get("/api/health")
async def api_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/simulate")
async def api_simulate(body: SimulateIn) -> dict[str, object]:
    """
    Main simulation path.
    Each synthetic agent receives its own TRIBE-informed neural profile and its own K2 decision.
    """
    return await run_simulation_http(
        city_id=body.city_id,
        catalyst_text=body.catalyst_text,
        source_url=body.source_url,
        use_case=body.use_case,
        message_complexity=body.message_complexity,
    )
