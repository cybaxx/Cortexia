"""Cortexia FastAPI orchestrator for case-based misinformation analysis."""

from __future__ import annotations

from contextlib import asynccontextmanager

import asyncio
import logging
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from app.config import get_settings
from app.pipeline_store import (
    append_agent_conversation,
    fetch_agent_outcome,
    fetch_case_run,
    init_pipeline_store,
    list_agent_conversations,
    list_recent_runs,
)
from app.services.ai_clients import call_elevenlabs, call_k2_agent_conversation, transcribe_audio_with_elevenlabs
from app.services.api_simulation import run_simulation_http

settings = get_settings()
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_pipeline_store()
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

    @field_validator("message_complexity", mode="before")
    @classmethod
    def _coerce_message_complexity(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"simple", "low"}:
                return 0.3
            if normalized in {"realistic", "medium", "default"}:
                return 0.65
            if normalized in {"complex", "high"}:
                return 0.85
        return value


class AgentConversationIn(BaseModel):
    message: str = Field(min_length=2, max_length=1200)


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
    try:
        return await run_simulation_http(
            city_id=body.city_id,
            domain=body.domain,
            case_goal=body.case_goal,
            evidence=body.evidence.model_dump(),
            message_complexity=body.message_complexity,
        )
    except asyncio.TimeoutError as exc:
        logger.exception("Simulation timed out")
        raise HTTPException(
            status_code=504,
            detail=f"Simulation exceeded the {settings.simulate_total_timeout_seconds:.0f}s pipeline timeout.",
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("Upstream HTTP failure during simulation")
        raise HTTPException(status_code=502, detail=f"Upstream simulation service failed: {exc}") from exc
    except Exception as exc:
        logger.exception("Simulation failed")
        raise HTTPException(status_code=500, detail=f"Simulation failed: {exc}") from exc


@app.get("/api/runs/recent")
async def api_recent_runs(limit: int = Query(default=8, ge=1, le=25)) -> dict[str, list[dict[str, Any]]]:
    """
    Recent persisted case runs for reproducibility and inspection.
    """
    return {"runs": list_recent_runs(limit)}


@app.get("/api/runs/{run_id}")
async def api_case_run(run_id: int) -> dict[str, Any]:
    """
    Load a persisted case run by id.
    """
    record = fetch_case_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return record


@app.get("/api/runs/{run_id}/agents/{agent_id}/conversation")
async def api_agent_conversation_history(run_id: int, agent_id: int) -> dict[str, Any]:
    rows = list_agent_conversations(run_id, agent_id)
    return {
        "messages": [
            {
                **row,
                "audio_url": f"/api/audio/{row['audio_filename']}" if row.get("audio_filename") else None,
            }
            for row in rows
        ]
    }


@app.post("/api/runs/{run_id}/agents/{agent_id}/conversation")
async def api_agent_conversation(run_id: int, agent_id: int, body: AgentConversationIn) -> dict[str, Any]:
    record = fetch_case_run(run_id)
    agent = fetch_agent_outcome(run_id, agent_id)
    if record is None or agent is None:
        raise HTTPException(status_code=404, detail="Agent or run not found.")

    agents = record["response"].get("agents") or []
    payload_agent = next((item for item in agents if int(item.get("id")) == agent_id), None)
    if payload_agent is None:
        raise HTTPException(status_code=404, detail="Agent payload not found in stored run.")

    prior_turns = list_agent_conversations(run_id, agent_id, limit=8)

    async with httpx.AsyncClient() as httpx_client:
        try:
            reply = await call_k2_agent_conversation(
                httpx_client,
                agent_name=agent["name"],
                agent_role=agent["role"],
                analysis_text=record["analysis_text"],
                speaker_context=(record["evidence"] or {}).get("speaker_context"),
                outcome={
                    "belief_state": payload_agent.get("belief_state"),
                    "confidence": payload_agent.get("k2_decision_confidence"),
                    "dominant_signal": payload_agent.get("dominant_signal"),
                    "sentiment": "negative"
                    if payload_agent.get("belief_state") == "rejected"
                    else "positive"
                    if payload_agent.get("belief_state") == "adopted"
                    else "neutral",
                },
                traits=agent["traits"],
                scores=agent["scores"],
                user_message=body.message,
                prior_turns=prior_turns,
            )
            audio_path = await call_elevenlabs(httpx_client, reply)
        except httpx.HTTPError as exc:
            logger.exception("Agent conversation upstream HTTP failure")
            raise HTTPException(status_code=502, detail=f"Agent conversation upstream failed: {exc}") from exc
        except Exception as exc:
            logger.exception("Agent conversation failed")
            raise HTTPException(status_code=500, detail=f"Agent conversation failed: {exc}") from exc

    sentiment = (
        "negative"
        if payload_agent.get("belief_state") == "rejected"
        else "positive"
        if payload_agent.get("belief_state") == "adopted"
        else "neutral"
    )
    audio_filename = Path(audio_path).name if audio_path else None
    turn_id = append_agent_conversation(
        run_id=run_id,
        agent_id=agent_id,
        user_message=body.message,
        agent_reply=reply,
        sentiment=sentiment,
        stance=str(payload_agent.get("belief_state") or "neutral"),
        audio_filename=audio_filename,
    )
    return {
        "id": turn_id,
        "user_message": body.message,
        "agent_reply": reply,
        "sentiment": sentiment,
        "stance": payload_agent.get("belief_state"),
        "audio_url": f"/api/audio/{audio_filename}" if audio_filename else None,
    }


@app.get("/api/audio/{filename}")
async def api_audio_file(filename: str):
    safe_name = Path(filename).name
    path = Path("/tmp/audio") / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found.")
    return FileResponse(path, media_type="audio/mpeg", filename=safe_name)
