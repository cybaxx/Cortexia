"""External AI / Modal integrations via httpx."""

from __future__ import annotations

import json
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
    "You are the cognitive router for one synthetic agent in Cortexia. "
    "Use the agent profile, Biological State Vector (BSV), and local neighborhood context to decide "
    "whether the agent adopts or rejects the catalyst message. "
    "Return four XML-like tags only: "
    "<think>2-4 concise sentences of reasoning.</think>"
    "<action>Adopted</action> or <action>Rejected</action>"
    "<confidence>0.00-1.00</confidence>"
    "<signal>cognitive_overload|defensive_reactance|empathic_resonance|memory_alignment|social_proof</signal>. "
    "If defensive posture is high, prefer defensive_reactance. "
    "If working memory strain or cognitive load is high, prefer cognitive_overload."
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


async def call_tribe_modal_batch(
    httpx_client: httpx.AsyncClient,
    catalyst_text: str,
    agents: list[dict],
) -> dict[str, BSV]:
    """
    Call the deployed Modal `extract-batch-bsv` webhook with a text catalyst and agents array
    and return the biological state vectors tailored for each agent.
    """
    if not tribe_modal_deployment_url():
        logger.warning("TRIBE_MODAL_URL unset; using fallback multi-agent BSVs")
        results = {}
        for a in agents:
            bsv = _default_bsv()
            bsv["cognitive_load"] = min(1.0, 0.55 + 0.01 * (len(catalyst_text) % 17))
            results[str(a["id"])] = bsv
        return results

    url = tribe_modal_deployment_url().rstrip("/")
    if not url.startswith("http"):
        url = f"https://{url}"
    
    headers: dict[str, str] = {
        "Content-Type": "application/json"
    }
    if settings.tribe_modal_key and settings.tribe_modal_secret:
        headers["Modal-Key"] = settings.tribe_modal_key
        headers["Modal-Secret"] = settings.tribe_modal_secret
    
    payload = {
        "catalyst_text": catalyst_text,
        "agents": agents
    }
    
    try:
        r = await httpx_client.post(url, json=payload, headers=headers, timeout=120.0)
        r.raise_for_status()
        data = r.json()
        
        results = {}
        agents_dict = data.get("agents", {})
        for aid, adict in agents_dict.items():
            results[aid] = {
                "cognitive_load": float(adict["cognitive_load"]),
                "emotional_agitation": float(adict["emotional_agitation"]),
                "defensive_posture": float(adict["defensive_posture"]),
                "working_memory_strain": float(adict["working_memory_strain"]),
            }
        return results
    except Exception:
        logger.exception("TRIBE Modal call failed; using fallback multi-agent BSV")
        results = {}
        for a in agents:
            results[str(a["id"])] = _default_bsv()
        return results


async def call_tribe_modal(
    httpx_client: httpx.AsyncClient,
    catalyst_text: str,
) -> BSV:
    """
    Legacy single-catalyst BSV baseline: one synthetic agent, same Modal batch endpoint.
    Kept for docs and any code paths that expect `call_tribe_modal` by name.
    """
    out = await call_tribe_modal_batch(
        httpx_client,
        catalyst_text,
        [{"id": 0, "role": "baseline", "latitude": 34.0522, "longitude": -118.2437}],
    )
    if "0" in out:
        return out["0"]
    if out:
        return next(iter(out.values()))
    return _default_bsv()


def _k2_response_body_to_object(r: httpx.Response) -> Any:
    """
    Parse K2 (OpenAI-compatible) response: full JSON, or text/event-stream with `data: {...}` lines.
    `response.json()` fails on empty body, HTML errors, or SSE — this handles those cases.
    """
    raw = r.text or ""
    stripped = raw.strip()
    status = r.status_code
    ct = (r.headers.get("content-type") or "").lower()

    if not stripped:
        raise ValueError(
            f"K2 API empty response body (http {status}, content-type={ct!r})"
        )

    if "text/event-stream" in ct or stripped.startswith("data:"):
        last_full: Any = None
        delta_parts: list[str] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                continue
            last_full = chunk
            # OpenAI-style streaming: choices[0].delta.content
            if isinstance(chunk, dict) and chunk.get("choices"):
                c0 = chunk["choices"][0] if chunk["choices"] else {}
                if isinstance(c0, dict) and "delta" in c0:
                    d = c0.get("delta") or {}
                    if isinstance(d, dict) and isinstance(d.get("content"), str):
                        delta_parts.append(d["content"])
        if delta_parts:
            merged = {
                "choices": [
                    {"message": {"content": "".join(delta_parts), "role": "assistant"}}
                ]
            }
            return merged
        if last_full is not None:
            return last_full
        raise ValueError(
            f"K2 API SSE: no parseable data: lines (http {status}, head={raw[:500]!r})"
        )

    try:
        return json.loads(stripped)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"K2 API returned non-JSON (http {status}): {stripped[:500]!r}"
        ) from e


def _openai_style_assistant_text(out: Any) -> str:
    """Extract assistant text from an OpenAI-style chat completion JSON object."""
    if isinstance(out, str) and out.strip():
        return out
    if not isinstance(out, dict):
        return str(out) if out is not None else ""
    for key in ("output", "text", "response"):
        v = out.get(key)
        if isinstance(v, str) and v.strip():
            return v
    choices = out.get("choices")
    if isinstance(choices, list) and choices:
        ch0 = choices[0] or {}
        msg = ch0.get("message")
        if isinstance(msg, dict) and "content" in msg:
            return str(msg.get("content") or "")
        if "text" in ch0:
            return str(ch0.get("text") or "")
    return ""


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
    """K2 Think (api.k2think.ai) — returns raw model text for downstream parsing."""
    if not settings.ifm_api_key.strip() or not settings.ifm_api_url.strip():
        logger.warning("IFM_API_KEY (or K2_THINK_API_KEY) or IFM_API_URL unset; using deterministic mock K2 output")
        dp = bsv.get("defensive_posture", 0.0)
        cl = bsv.get("cognitive_load", 0.0)
        wm = bsv.get("working_memory_strain", 0.0)
        if dp > 0.7:
            action = "Rejected"
            think = "Threat processing dominates. The message lands as pressure rather than support."
            confidence = 0.82
            signal = "defensive_reactance"
        elif cl > 0.8 or wm > 0.78:
            action = "Rejected"
            think = "Working memory is saturated. The message asks for too much integration at once."
            confidence = 0.74
            signal = "cognitive_overload"
        else:
            action = "Adopted" if adopted_neighbor_count >= 1 else "Rejected"
            think = "Neighborhood signal reduces uncertainty and the message feels locally legible."
            confidence = 0.63 if action == "Adopted" else 0.57
            signal = "social_proof" if adopted_neighbor_count >= 1 else "memory_alignment"
        return (
            f"<think>{think}</think>"
            f"<action>{action}</action>"
            f"<confidence>{confidence:.2f}</confidence>"
            f"<signal>{signal}</signal>"
        )

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.ifm_api_key}",
    }

    # OpenAI-compatible chat completions (K2 Think docs: api.k2think.ai)
    payload: dict[str, Any] = {
        "model": settings.ifm_k2_model,
        "stream": False,
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
    out = _k2_response_body_to_object(r)
    text = _openai_style_assistant_text(out)
    if not text.strip():
        raise ValueError(
            f"K2 API returned no assistant content; keys={list(out.keys()) if isinstance(out, dict) else type(out)}"
        )
    return text


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
