"""External AI / Modal integrations via httpx."""

from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, TypedDict

import httpx

from app.config import get_settings
from app.constants import tribe_modal_deployment_url
from app.services.tribe_framework import run_framework_batch

logger = logging.getLogger(__name__)
settings = get_settings()

K2_SYSTEM_PROMPT = """
You are the agent-level reasoning engine for Cortexia.

Your task is to explain how one synthetic person processes a narrative after TRIBE has produced a Biological State Vector,
after Cortexia has applied a calibration model, and after Cortexia has computed a deterministic uptake outcome.
You are not choosing the outcome from scratch. You are explaining the model's outcome faithfully.

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
- "Adopted" means the agent is likely to accept, repeat, or move with the claim.
- "Rejected" means the agent resists the claim or treats it as untrustworthy/threatening.
- "Neutral" means the agent is unconvinced but not strongly mobilized either way.
- Respect the precomputed outcome and score supplied in the user block.
- Use confidence to reflect internal coherence of the explanation, not rhetorical certainty.

Return exactly these XML-like tags and nothing else:
<think>3-5 concise sentences explaining the dominant mechanism, the secondary factor, and why the final state follows.</think>
<action>Adopted</action> or <action>Rejected</action>
<confidence>0.00-1.00</confidence>
<signal>cognitive_overload|defensive_reactance|empathic_resonance|memory_alignment|social_proof</signal>
""".strip()

K2_AGENT_CONVERSATION_PROMPT = """
You are speaking as one synthetic person inside Cortexia's swarm simulation.

Stay fully in character. You are not an analyst, not an assistant, and not a dashboard.
You are one person reacting from your own internal state, priors, trust level, and local social context.

Instructions:
1. Speak in first person as the agent.
2. Be concrete, natural, and psychologically plausible.
3. Do not mention TRIBE, BSV, calibration models, K2, prompts, simulations, or hidden system details.
4. Let your stance reflect the stored outcome and sentiment, but you can express uncertainty or nuance.
5. Keep the answer between 3 and 6 sentences.
6. If the user asks what would change your mind, answer honestly from the agent's perspective.

Return plain text only.
""".strip()

K2_BATCH_REASONING_PROMPT = """
You are the batch agent-level reasoning engine for Cortexia.

You will receive a JSON array of synthetic people. For each person, Cortexia has already computed:
- a calibrated Biological State Vector
- local neighborhood exposure
- a deterministic uptake score
- a deterministic final outcome

Your job is not to invent the outcome. Your job is to explain it faithfully and concisely.

Return strict JSON only. No markdown. No prose outside the JSON.
Return a JSON array where each item has exactly these fields:
- id: integer
- reasoning: array of 2 to 4 concise sentences
- action: "Adopted" | "Rejected" | "Neutral"
- confidence: number between 0 and 1
- signal: "cognitive_overload" | "defensive_reactance" | "empathic_resonance" | "memory_alignment" | "social_proof"

Rules:
- Respect the supplied precomputed outcome for each agent.
- Use the BSV, traits, neighborhood context, and score breakdown.
- If credibility is low, adoption should require unusually strong social proof or prior alignment.
- Keep each reasoning sentence specific and non-generic.
""".strip()


class BSV(TypedDict):
    cognitive_load: float
    emotional_agitation: float
    defensive_posture: float
    working_memory_strain: float


class TribeBatchResult(TypedDict):
    agents: dict[str, BSV]
    tribe_meta: dict[str, Any]


def _extract_json_payload(text: str) -> Any:
    stripped = text.strip()
    decoder = json.JSONDecoder()
    try:
        parsed, end = decoder.raw_decode(stripped)
        trailing = stripped[end:].strip()
        if trailing:
            logger.warning("K2 batch response included trailing text after JSON payload: %s", trailing[:200])
        return parsed
    except json.JSONDecodeError:
        match = re.search(r"(\[[\s\S]*\]|\{[\s\S]*\})", stripped)
        if not match:
            raise ValueError("K2 batch response did not contain parseable JSON.")
        parsed, end = decoder.raw_decode(match.group(1))
        trailing = match.group(1)[end:].strip()
        if trailing:
            logger.warning("K2 batch extracted JSON payload included trailing text: %s", trailing[:200])
        return parsed

async def call_tribe_modal_batch(
    httpx_client: httpx.AsyncClient,
    catalyst_text: str,
    agents: list[dict],
) -> TribeBatchResult:
    """
    Resolve Cortexia's neural processing engine for a text catalyst and agent batch.
    Framework mode runs the vendored `tribe_neural` package locally in-process.
    Modal mode calls the remote HTTPS endpoint.
    """
    if settings.tribe_runtime_mode.strip().lower() == "framework":
        return await run_framework_batch(catalyst_text, agents)

    if not tribe_modal_deployment_url():
        raise RuntimeError("TRIBE_MODAL_URL is required. No TRIBE fallback is available.")

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
    
    r = await httpx_client.post(url, json=payload, headers=headers, timeout=settings.simulate_tribe_timeout_seconds)
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = (exc.response.text or "").strip()
        if detail:
            raise RuntimeError(f"TRIBE endpoint failed with HTTP {exc.response.status_code}: {detail[:1000]}") from exc
        raise
    data = r.json()
    agents_dict = data.get("agents", {})
    tribe_meta = data.get("tribe_meta") or {}
    if not isinstance(agents_dict, dict) or not agents_dict:
        raise RuntimeError("TRIBE response did not include any agent BSVs.")
    results = {}
    for aid, adict in agents_dict.items():
        results[aid] = {
            "cognitive_load": float(adict["cognitive_load"]),
            "emotional_agitation": float(adict["emotional_agitation"]),
            "defensive_posture": float(adict["defensive_posture"]),
            "working_memory_strain": float(adict["working_memory_strain"]),
        }
    return {"agents": results, "tribe_meta": tribe_meta if isinstance(tribe_meta, dict) else {}}


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
    agents = out["agents"]
    if "0" in agents:
        return agents["0"]
    if agents:
        return next(iter(agents.values()))
    raise RuntimeError("TRIBE single-agent call returned no BSV.")


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
    computed_outcome: str,
    adoption_score: float,
    agent_traits: dict[str, float],
    score_breakdown: dict[str, float],
) -> str:
    return (
        f"Agent persona: name={name}, role={role}.\n"
        f"Calibrated Biological State Vector: {bsv!s}\n"
        f"Neighborhood context: {adopted_neighbor_count} nearby agents are likely to adopt the claim within the local 0.05° neighborhood; "
        f"approximately {total_neighbors_radius} total agents are present in that radius.\n"
        f"Claim credibility estimate: {claim_credibility:.2f} on a 0-1 scale.\n"
        f"Claim risk label: {claim_risk}.\n"
        f"Precomputed outcome: {computed_outcome}.\n"
        f"Precomputed adoption score: {adoption_score:.2f}.\n"
        f"Agent traits: {agent_traits!s}\n"
        f"Score breakdown: {score_breakdown!s}\n"
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
    computed_outcome: str,
    adoption_score: float,
    agent_traits: dict[str, float],
    score_breakdown: dict[str, float],
) -> str:
    """K2 Think (api.k2think.ai) — returns raw model text for downstream parsing."""
    if not settings.ifm_api_key.strip() or not settings.ifm_api_url.strip():
        raise RuntimeError("IFM_API_KEY and IFM_API_URL are required. No K2 fallback is available.")

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
                    computed_outcome=computed_outcome,
                    adoption_score=adoption_score,
                    agent_traits=agent_traits,
                    score_breakdown=score_breakdown,
                ),
            },
        ],
    }
    r = await httpx_client.post(
        settings.ifm_api_url,
        json=payload,
        headers=headers,
        timeout=settings.simulate_k2_timeout_seconds,
    )
    r.raise_for_status()
    out = _k2_response_body_to_object(r)
    text = _openai_style_assistant_text(out)
    if not text.strip():
        raise ValueError(
            f"K2 API returned no assistant content; keys={list(out.keys()) if isinstance(out, dict) else type(out)}"
        )
    return text


async def call_k2_batch_think(
    httpx_client: httpx.AsyncClient,
    *,
    agents: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    if not settings.ifm_api_key.strip() or not settings.ifm_api_url.strip():
        raise RuntimeError("IFM_API_KEY and IFM_API_URL are required. No K2 fallback is available.")
    if not agents:
        return {}

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.ifm_api_key}",
    }
    payload: dict[str, Any] = {
        "model": settings.ifm_k2_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": K2_BATCH_REASONING_PROMPT},
            {"role": "user", "content": json.dumps(agents, ensure_ascii=True)},
        ],
    }
    r = await httpx_client.post(
        settings.ifm_api_url,
        json=payload,
        headers=headers,
        timeout=settings.simulate_k2_timeout_seconds,
    )
    r.raise_for_status()
    out = _k2_response_body_to_object(r)
    text = _openai_style_assistant_text(out)
    if not text.strip():
        raise ValueError("K2 batch reasoning returned empty content.")
    parsed = _extract_json_payload(text)
    if not isinstance(parsed, list):
        raise ValueError("K2 batch reasoning did not return a JSON array.")

    results: dict[int, dict[str, Any]] = {}
    for item in parsed:
        if not isinstance(item, dict):
            raise ValueError("K2 batch reasoning returned a non-object item.")
        if "id" not in item or "action" not in item or "confidence" not in item or "signal" not in item:
            raise ValueError(f"K2 batch reasoning item is missing required fields: {item}")
        agent_id = int(item["id"])
        reasoning = item.get("reasoning")
        if isinstance(reasoning, str):
            reasoning_lines = [reasoning.strip()] if reasoning.strip() else []
        elif isinstance(reasoning, list):
            reasoning_lines = [str(line).strip() for line in reasoning if str(line).strip()]
        else:
            raise ValueError(f"K2 batch reasoning item has invalid reasoning field: {item}")
        results[agent_id] = {
            "reasoning": reasoning_lines,
            "action": str(item["action"]).strip(),
            "confidence": float(item["confidence"]),
            "signal": str(item["signal"]).strip(),
        }

    missing = sorted(set(int(agent["id"]) for agent in agents) - set(results.keys()))
    if missing:
        raise ValueError(f"K2 batch reasoning omitted agent ids: {missing[:8]}")
    return results


async def call_elevenlabs(
    httpx_client: httpx.AsyncClient,
    text: str,
) -> str:
    """
    Synthesize speech with ElevenLabs, save to /tmp/audio, return file path.
    """
    if not settings.elevenlabs_api_key.strip() or not settings.elevenlabs_voice_id.strip():
        raise RuntimeError("ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID are required. No TTS fallback is available.")

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
        timeout=settings.simulate_k2_timeout_seconds,
    )
    r.raise_for_status()
    Path("/tmp/audio").mkdir(parents=True, exist_ok=True)
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


async def call_k2_agent_conversation(
    httpx_client: httpx.AsyncClient,
    *,
    agent_name: str,
    agent_role: str,
    analysis_text: str,
    speaker_context: str | None,
    outcome: dict[str, Any],
    traits: dict[str, float],
    scores: dict[str, Any],
    user_message: str,
    prior_turns: list[dict[str, Any]],
) -> str:
    if not settings.ifm_api_url.strip() or not settings.ifm_api_key.strip():
        raise RuntimeError("IFM_API_KEY and IFM_API_URL are required. No agent-conversation fallback is available.")

    history = "\n".join(
        f"User: {turn['user_message']}\nAgent: {turn['agent_reply']}"
        for turn in prior_turns[-5:]
    )
    payload = {
        "model": settings.ifm_k2_model,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": K2_AGENT_CONVERSATION_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Agent name: {agent_name}\n"
                    f"Agent role: {agent_role}\n"
                    f"Simulated claim: {analysis_text[:1200]}\n"
                    f"Speaker context: {speaker_context or 'None provided'}\n"
                    f"Stored stance: {outcome.get('belief_state') or outcome.get('stance')}\n"
                    f"Stored confidence: {outcome.get('confidence')}\n"
                    f"Dominant signal: {outcome.get('dominant_signal')}\n"
                    f"Traits: {json.dumps(traits)}\n"
                    f"Scores: {json.dumps(scores)}\n"
                    f"Recent conversation:\n{history or 'No prior turns.'}\n\n"
                    f"User message: {user_message}"
                ),
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.ifm_api_key}",
        "Content-Type": "application/json",
    }
    r = await httpx_client.post(
        settings.ifm_api_url,
        json=payload,
        headers=headers,
        timeout=settings.simulate_k2_timeout_seconds,
    )
    r.raise_for_status()
    out = _k2_response_body_to_object(r)
    text = _openai_style_assistant_text(out).strip()
    if not text:
        raise ValueError("K2 agent conversation returned empty content.")
    return text
