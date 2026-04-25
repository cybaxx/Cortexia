"""Cortexia FastAPI orchestrator for case-based misinformation analysis."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.ai_clients import transcribe_audio_with_elevenlabs
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
    version="0.3.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EvidenceAudioAssetIn(BaseModel):
    filename: str | None = None
    mime_type: str | None = None
    duration_seconds: float | None = None
    transcript_confidence: float | None = None
    source_type: str | None = None
    transcript_edited: bool = False


class EvidenceIn(BaseModel):
    text_input: str = ""
    source_url: str | None = None
    transcript: str | None = None
    edited_analysis_text: str | None = None
    speaker_context: str | None = None
    audio_input: EvidenceAudioAssetIn | None = None


class SimulateIn(BaseModel):
    domain: str = "political"
    city_id: str = "la"
    case_goal: str = Field(default="Understand how this information spreads and what interventions could reduce harm.")
    evidence: EvidenceIn
    message_complexity: float = Field(0.5, ge=0.0, le=1.0)


@app.get("/api/health")
async def api_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/transcribe")
async def api_transcribe(
    file: UploadFile = File(...),
    language_code: str | None = Form(default=None),
) -> dict[str, Any]:
    """
    Audio transcription endpoint backed by ElevenLabs Speech-to-Text.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Audio filename is required.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    async with httpx.AsyncClient() as httpx_client:
        try:
            data = await transcribe_audio_with_elevenlabs(
                httpx_client,
                filename=file.filename,
                content=content,
                content_type=file.content_type or "application/octet-stream",
                language_code=language_code,
            )
        except Exception as exc:
            logger.exception("Audio transcription failed")
            raise HTTPException(status_code=502, detail=f"Transcription failed: {exc}") from exc

    words = data.get("words") or []
    duration = 0.0
    if words:
        last_word = words[-1]
        duration = float(last_word.get("end") or 0.0)

    avg_prob = 0.0
    prob_count = 0
    for word in words:
        logprob = word.get("logprob")
        if isinstance(logprob, (int, float)):
            avg_prob += max(0.0, min(1.0, 1.0 + float(logprob)))
            prob_count += 1
    confidence = avg_prob / prob_count if prob_count else float(data.get("language_probability") or 0.72)
    speaker_ids = sorted({str(word.get("speaker_id")) for word in words if word.get("speaker_id")})

    return {
        "text": data.get("text", ""),
        "language_code": data.get("language_code"),
        "duration_seconds": duration,
        "transcript_confidence": round(max(0.0, min(1.0, confidence)), 3),
        "speaker_ids": speaker_ids,
        "filename": file.filename,
        "mime_type": file.content_type,
        "source_type": "audio_upload",
    }


@app.post("/api/simulate")
async def api_simulate(body: SimulateIn) -> dict[str, object]:
    """
    Main case-analysis path.
    """
    return await run_simulation_http(
        city_id=body.city_id,
        domain=body.domain,
        case_goal=body.case_goal,
        evidence=body.evidence.model_dump(),
        message_complexity=body.message_complexity,
    )
