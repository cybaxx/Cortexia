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

K2_SYSTEM_PROMPT = """
You are the agent-level reasoning engine for Cortexia.

Your task is to simulate how one synthetic person processes a narrative after TRIBE has produced a Biological State Vector
and after Cortexia has applied a lightweight calibration model. You are not writing marketing copy. You are performing a
structured behavioral judgment.

Use all of the following inputs:
- agent role and context
- calibrated Biological State Vector (BSV)
- neighborhood adoption signal
- local resonance / openness conditions
- case goal and narrative content

Interpretive rubric:
1. Start from the BSV. High defensive_posture and emotional_agitation imply threat sensitivity and reactance risk.
2. High cognitive_load or working_memory_strain imply overload, confusion, and lower integration capacity.
3. Supportive neighbor count and favorable resonance increase social proof and lower uncertainty.
4. Prefer memory_alignment only when the message plausibly fits familiar priors without strong threat or overload signals.
5. Prefer empathic_resonance only when the agent is comparatively open and affectively reachable.
6. Do not over-index on one field if the rest of the state disagrees. Reconcile conflicts explicitly in the reasoning.
7. If the agent sees the content as identity-threatening, status-threatening, or institutionally coercive, prefer defensive_reactance.
8. If the agent can process the content but only because nearby signals normalize it, prefer social_proof.

Decision rules:
- "Adopted" means the agent is likely to accept, repeat, or move with the message.
- "Rejected" means the agent resists the message or treats it as untrustworthy/threatening.
- Use confidence to reflect internal coherence of the evidence, not rhetorical certainty.

Return exactly these XML-like tags and nothing else:
<think>3-5 concise sentences explaining the dominant mechanism, the secondary factor, and why the final state follows.</think>
<action>Adopted</action> or <action>Rejected</action>
<confidence>0.00-1.00</confidence>
<signal>cognitive_overload|defensive_reactance|empathic_resonance|memory_alignment|social_proof</signal>
""".strip()


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
    claim_credibility: float,
    claim_risk: str,
) -> str:
    return (
        f"Agent persona: name={name}, role={role}.\n"
        f"Calibrated Biological State Vector: {bsv!s}\n"
        f"Neighborhood context: {adopted_neighbor_count} nearby agents are dispositionally open to the claim within the local 0.05° neighborhood; "
        f"approximately {total_neighbors_radius} total agents are present in that radius.\n"
        f"Claim credibility estimate: {claim_credibility:.2f} on a 0-1 scale.\n"
        f"Claim risk label: {claim_risk}.\n"
        "Reasoning instructions:\n"
        "- Explain the dominant mechanism first.\n"
        "- Mention one secondary force if present.\n"
        "- Tie the final action directly to the calibrated BSV and neighborhood context.\n"
        "- If the claim credibility is low, adoption should require unusually strong social proof or prior alignment.\n"
        "- Avoid generic wording like 'the message resonates' unless you specify why.\n"
        f"Narrative and case context:\n{catalyst_text}\n"
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
    claim_credibility: float,
    claim_risk: str,
) -> str:
    """K2 Think (api.k2think.ai) — returns raw model text for downstream parsing."""
    if not settings.ifm_api_key.strip() or not settings.ifm_api_url.strip():
        logger.warning("IFM_API_KEY (or K2_THINK_API_KEY) or IFM_API_URL unset; using deterministic mock K2 output")
        dp = bsv.get("defensive_posture", 0.0)
        cl = bsv.get("cognitive_load", 0.0)
        wm = bsv.get("working_memory_strain", 0.0)
        if claim_credibility < 0.28 and adopted_neighbor_count < 4:
            action = "Rejected"
            think = "The claim has weak baseline credibility and there is not enough local proof to overcome skepticism. The agent defaults to rejection rather than internalizing the claim."
            confidence = 0.81
            signal = "defensive_reactance" if dp > 0.58 else "memory_alignment"
        elif dp > 0.7:
            action = "Rejected"
            think = "Defensive posture is dominant, so the content is interpreted as pressure or status threat. Emotional activation reinforces rejection rather than deliberation."
            confidence = 0.82
            signal = "defensive_reactance"
        elif cl > 0.8 or wm > 0.78:
            action = "Rejected"
            think = "Working memory strain is elevated and the message asks for too much integration at once. The agent cannot comfortably absorb the claim and defaults to overload-based rejection."
            confidence = 0.74
            signal = "cognitive_overload"
        else:
            action = "Adopted" if adopted_neighbor_count >= 4 and claim_credibility >= 0.42 else "Rejected"
            think = "Local openness reduces uncertainty, but adoption only occurs when neighborhood reinforcement is strong enough to offset weak priors. Social proof is influential here, but it is not enough on its own when the claim looks flimsy."
            confidence = 0.66 if action == "Adopted" else 0.64
            signal = "social_proof" if adopted_neighbor_count >= 4 else "memory_alignment"
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
                    claim_credibility=claim_credibility,
                    claim_risk=claim_risk,
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


async def transcribe_audio_with_elevenlabs(
    httpx_client: httpx.AsyncClient,
    *,
    filename: str,
    content: bytes,
    content_type: str,
    language_code: str | None = None,
) -> dict[str, Any]:
    """
    Transcribe audio using ElevenLabs Speech-to-Text.
    Official docs: POST /v1/speech-to-text with multipart form, model_id=scribe_v2 or scribe_v1.
    """
    if not settings.elevenlabs_api_key.strip():
        raise RuntimeError("ELEVENLABS_API_KEY is required for audio transcription.")

    files = {
        "file": (filename, content, content_type or "application/octet-stream"),
    }
    data: dict[str, Any] = {
        "model_id": settings.elevenlabs_stt_model,
        "diarize": "true",
        "timestamps_granularity": "word",
        "tag_audio_events": "true",
    }
    if language_code:
        data["language_code"] = language_code

    response = await httpx_client.post(
        "https://api.elevenlabs.io/v1/speech-to-text",
        headers={"xi-api-key": settings.elevenlabs_api_key},
        data=data,
        files=files,
        timeout=180.0,
    )
    response.raise_for_status()
    return response.json()
