"""External AI / Modal integrations via httpx."""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any, TypedDict

import httpx

from app.config import get_settings
from app.constants import tribe_modal_deployment_url

logger = logging.getLogger(__name__)
settings = get_settings()

K2_SYSTEM_PROMPT = (
    "You are the cognitive router for a synthetic agent. "
    "Analyze the provided Biological State Vector (BSV) and spatial context. "
    "If defensive_posture > 0.7, reject the catalyst. "
    "If cognitive_load > 0.8, exhibit confusion. "
    "Output your reasoning inside <think></think> tags, "
    "and your final decision as <action>Adopted</action> or <action>Rejected</action>."
)


class BSV(TypedDict):
    cognitive_load: float
    emotional_agitation: float
    defensive_posture: float
    working_memory_strain: float


def _default_bsv() -> BSV:
    return {
        "cognitive_load": 0.5,
        "emotional_agitation": 0.5,
        "defensive_posture": 0.5,
        "working_memory_strain": 0.5,
    }


async def call_tribe_modal(
    httpx_client: httpx.AsyncClient,
    catalyst_text: str,
) -> BSV:
    """
    Call the deployed Modal `extract_bsv` webhook with a text catalyst
    and return the biological state vector.
    """
    if not tribe_modal_deployment_url():
        logger.warning("TRIBE_MODAL_URL unset; using fallback BSV")
        bsv = _default_bsv()
        bsv["cognitive_load"] = min(1.0, 0.55 + 0.01 * (len(catalyst_text) % 17))
        return bsv

    url = tribe_modal_deployment_url().rstrip("/")
    if not url.startswith("http"):
        url = f"https://{url}"
    # Modal web endpoints: POST with multipart "file" field (see modal_app.TribeExtractor).
    files = {
        "file": (
            "catalyst.txt",
            catalyst_text.encode("utf-8"),
            "text/plain",
        )
    }
    headers: dict[str, str] = {}
    if settings.tribe_modal_key and settings.tribe_modal_secret:
        headers["Modal-Key"] = settings.tribe_modal_key
        headers["Modal-Secret"] = settings.tribe_modal_secret
    try:
        r = await httpx_client.post(url, files=files, headers=headers, timeout=120.0)
        r.raise_for_status()
        data = r.json()
        return {
            "cognitive_load": float(data["cognitive_load"]),
            "emotional_agitation": float(data["emotional_agitation"]),
            "defensive_posture": float(data["defensive_posture"]),
            "working_memory_strain": float(data["working_memory_strain"]),
        }
    except Exception:
        logger.exception("TRIBE Modal call failed; using fallback BSV")
        return _default_bsv()


def _k2_user_block(
    *,
    name: str,
    role: str,
    bsv: BSV,
    adopted_neighbor_count: int,
    total_neighbors_radius: int,
    catalyst_text: str,
) -> str:
    return (
        f"Agent persona: name={name}, role={role}.\n"
        f"Biological State Vector: {bsv!s}\n"
        f"Spatial context: {adopted_neighbor_count} neighbors have adopted the belief "
        f"within the local 0.05° neighborhood (snapshot at cycle start; "
        f"approx. {total_neighbors_radius} total agents in that radius).\n"
        f"Catalyst: {catalyst_text}\n"
    )


async def call_k2_think(
    httpx_client: httpx.AsyncClient,
    *,
    name: str,
    role: str,
    bsv: BSV,
    adopted_neighbor_count: int,
    total_neighbors_in_radius: int,
    catalyst_text: str,
) -> str:
    """IFM K2 Think — returns raw model text for downstream parsing."""
    if not settings.ifm_api_url.strip():
        logger.warning("IFM_API_URL unset; using deterministic mock K2 output")
        dp = bsv.get("defensive_posture", 0.0)
        cl = bsv.get("cognitive_load", 0.0)
        if dp > 0.7:
            action = "Rejected"
            think = "defensive_posture is elevated; rejecting catalyst."
        elif cl > 0.8:
            action = "Rejected"
            think = "cognitive load very high; confused and defaulting to reject."
        else:
            action = "Adopted" if adopted_neighbor_count >= 1 else "Rejected"
            think = "weighing BSV and neighborhood adoption signal."
        return (
            f"<think>{think}</think> "
            f"<action>{action}</action>"
        )

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.ifm_api_key:
        headers["Authorization"] = f"Bearer {settings.ifm_api_key}"

    # Generic JSON body compatible with many chat-style APIs; adjust to IFM contract.
    payload: dict[str, Any] = {
        "model": "ifm-k2-think",
        "messages": [
            {"role": "system", "content": K2_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _k2_user_block(
                    name=name,
                    role=role,
                    bsv=bsv,
                    adopted_neighbor_count=adopted_neighbor_count,
                    total_neighbors_radius=total_neighbors_in_radius,
                    catalyst_text=catalyst_text,
                ),
            },
        ],
    }
    r = await httpx_client.post(
        settings.ifm_api_url,
        json=payload,
        headers=headers,
        timeout=120.0,
    )
    r.raise_for_status()
    out = r.json()
    if isinstance(out, str):
        return out
    for key in ("output", "text", "response", "message"):
        if key in out and isinstance(out[key], str):
            return out[key]
    # Some APIs return openai-style choices
    choices = out.get("choices")
    if choices and isinstance(choices, list):
        ch0 = choices[0] or {}
        msg = ch0.get("message") or {}
        if "content" in msg:
            return str(msg["content"])
    return r.text


async def call_elevenlabs(
    httpx_client: httpx.AsyncClient,
    text: str,
) -> str:
    """
    Synthesize speech with ElevenLabs, save to /tmp/audio, return file path.
    """
    if not settings.elevenlabs_api_key or not settings.elevenlabs_voice_id:
        path = str(Path("/tmp/audio") / f"disabled-{uuid.uuid4().hex}.mp3")
        os.makedirs("/tmp/audio", exist_ok=True)
        Path(path).write_bytes(b"")
        logger.warning("ElevenLabs not configured; wrote empty MP3 at %s", path)
        return path

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
    }
    r = await httpx_client.post(
        url,
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
        },
        headers=headers,
        timeout=120.0,
    )
    r.raise_for_status()
    os.makedirs("/tmp/audio", exist_ok=True)
    path = str(Path("/tmp/audio") / f"tts-{uuid.uuid4().hex}.mp3")
    Path(path).write_bytes(r.content)
    return path
