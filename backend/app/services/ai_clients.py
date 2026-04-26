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
7. Return only the words the agent would actually say out loud.
8. Do not include hidden reasoning, <think> tags, analysis, preambles, or explanations of your process.

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
- Every item must be a JSON object. Never return strings, commentary, code fences, XML, or a preamble.
- Keep each reasoning sentence specific and non-generic.
- Different agents must not receive near-duplicate wording unless their profiles are genuinely near-identical.
- Explicitly vary the explanation based on role, traits, local exposure, and the score breakdown.
- Prefer concrete mechanisms like evidence scrutiny, institutional trust, identity threat, peer normalization, overload, or prior-fit mismatch instead of repeating the same brain-region formula for everyone.
- Use the agent's role as the first interpretive lens. The first reasoning sentence should sound specific to that role.
- Do not start every explanation the same way. Vary sentence openings across agents.
- Do not copy raw field names or dump numbers mechanically. Use only the few numbers that matter most to explain the outcome.
- Mention social context only if it materially changes the explanation. If supportive_neighbors is 0, say the lack of peer reinforcement matters.
- Confidence should reflect how internally coherent the supplied outcome is, not how persuasive the rumor sounds.

Output discipline:
- Return one array only.
- The array length must equal the number of input agents.
- Preserve input ids exactly.
- If an agent is rejected because of overload, explain what specifically could not be processed or verified for that role.
- If multiple agents share the same final signal, still differentiate them using role, traits, and neighborhood context.

Example output shape:
[{"id": 1, "reasoning": ["Sentence 1.", "Sentence 2."], "action": "Rejected", "confidence": 0.81, "signal": "cognitive_overload"}]
""".strip()

K2_ACTION_CENTER_PROMPT = """
You are the final-step operations synthesis engine for Cortexia.

Inputs include:
- the scenario the user simulated
- city and use-case context
- the user's case goal from the intake step
- simulation findings from TRIBE + K2
- optional live web research results and structured extraction results

Your task:
1. Summarize what matters most right now.
2. Turn the research and simulation into concrete operational next steps.
3. Identify what should be monitored next.
4. Flag which sources deserve browser-based manual verification.

Return strict JSON only with exactly these top-level keys:
- headline: string
- executive_summary: string
- decision_window: string
- urgency: "low" | "medium" | "high"
- confidence_note: string
- recommended_actions: array of objects with keys:
  - title: string
  - owner: string
  - audience: string
  - timeline: string
  - action: string
  - why_now: string
- monitoring_queries: array of strings
- source_briefings: array of objects with keys:
  - url: string
  - why_it_matters: string
  - credibility_note: string
- browser_verification_queue: array of objects with keys:
  - url: string
  - reason: string
  - check_for: string

Rules:
- Be operational, not academic.
- The brief must be explicitly grounded in the user's case goal. Treat that goal as the decision lens for the headline, executive summary, recommended actions, and monitoring priorities.
- Make it obvious what decision or learning objective the team is trying to satisfy.
- Recommended actions should be immediately usable by a comms, policy, trust, or response team.
- If live sources are thin, say so clearly in the confidence note and lean more on simulation findings.
- Never output markdown or prose outside the JSON object.
""".strip()

K2_EXPLANATION_ONLY_PROMPT = """
You explain why one synthetic person reached a precomputed outcome in Cortexia.

Important:
- The outcome, signal, and confidence are already computed elsewhere.
- Your only job is to write 2 concise sentences that sound specific to this person.
- Do not output JSON, XML, markdown, tags, or analysis of your process.
- Do not include hidden reasoning or preambles.
- Return plain text only.

Writing rules:
- Sentence 1 should begin from the person's role or decision lens.
- Sentence 2 should explain the strongest reason the person ended at the supplied outcome, using only the most relevant factors.
- Be concrete and role-specific.
- Do not repeat identical wording across agents.
- Avoid generic phrases like "the content feels effortful" unless absolutely necessary.
""".strip()

K2_TIMELINE_BATCH_PROMPT = """
You generate the propagation-timeline language for Cortexia.

You will receive a JSON array. Each item represents one agent at one round of the simulation.
The state, confidence, trigger pressures, messenger fit, and structural context are already computed.
Your job is to write the user-facing text only.

Return strict JSON only. No markdown. No prose outside the JSON.
Return one JSON array where each item has exactly these fields:
- agent_id: integer
- round: integer
- phase_label: string
- trigger_label: string
- post: string
- change_summary: string

Rules:
- Everything should sound like a distinct person in a distinct moment, not a template.
- Use the agent's role, demographics, signal, local messenger context, and state transition.
- Do not start every item the same way.
- Avoid canned phrases like "from a civic lens" or "the evidence gap stayed unresolved."
- `post` should sound like the actual thought or message that explains the round.
- `change_summary` should explain what changed using the provided metrics, but in natural language.
- `phase_label` should be short and human-readable, tied to the actual event.
- `trigger_label` should be short and specific to the cause, not generic.
- Preserve agent_id and round exactly.
""".strip()


class BSV(TypedDict):
    cognitive_load: float
    emotional_agitation: float
    defensive_posture: float
    working_memory_strain: float


class TribeBatchResult(TypedDict):
    agents: dict[str, BSV]
    tribe_meta: dict[str, Any]


def _find_first_list_candidate(value: Any, *, max_depth: int = 4) -> list[Any] | None:
    if max_depth < 0:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for nested in value.values():
            found = _find_first_list_candidate(nested, max_depth=max_depth - 1)
            if found is not None:
                return found
    return None


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
        candidates: list[tuple[tuple[int, int, int, int], int, Any, str]] = []
        for match in re.finditer(r"[\[{]", stripped):
            start = match.start()
            try:
                parsed, end = decoder.raw_decode(stripped[start:])
            except json.JSONDecodeError:
                continue
            trailing = stripped[start + end :].strip()
            if isinstance(parsed, list):
                dict_count = sum(1 for item in parsed if isinstance(item, dict))
                scalar_count = sum(1 for item in parsed if not isinstance(item, dict))
                score = (2 if dict_count > 0 else 1, dict_count, len(parsed), end - len(trailing))
                candidates.append((score, start, parsed, trailing))
            elif isinstance(parsed, dict):
                score = (1, 1 if "id" in parsed else 0, len(parsed), end - len(trailing))
                candidates.append((score, start, parsed, trailing))

        if not candidates:
            raise ValueError("K2 batch response did not contain parseable JSON.")

        _score, start, parsed, trailing = max(candidates, key=lambda item: item[0])
        logger.warning("K2 batch response required recovery from noisy text; using JSON payload starting at byte %s.", start)
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


def _strip_k2_hidden_reasoning(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""

    if "</think>" in cleaned:
        cleaned = cleaned.rsplit("</think>", 1)[-1].strip()

    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</?(action|confidence|signal)>", "", cleaned, flags=re.IGNORECASE)

    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if lines:
        cleaned = "\n".join(lines)

    return cleaned.strip()


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
    if isinstance(parsed, dict):
        for key in ("results", "items", "data", "agents", "output"):
            candidate = parsed.get(key)
            if isinstance(candidate, list):
                parsed = candidate
                break
        else:
            nested = _find_first_list_candidate(parsed)
            if nested is not None:
                parsed = nested
    if not isinstance(parsed, list):
        raise ValueError("K2 batch reasoning did not return a JSON array.")

    results: dict[int, dict[str, Any]] = {}
    skipped_items = 0
    for item in parsed:
        if isinstance(item, str):
            try:
                recovered = _extract_json_payload(item)
            except ValueError:
                skipped_items += 1
                continue
            if isinstance(recovered, list):
                recovered_objects = [candidate for candidate in recovered if isinstance(candidate, dict)]
                if len(recovered_objects) == 1:
                    item = recovered_objects[0]
                else:
                    skipped_items += 1
                    continue
            elif isinstance(recovered, dict):
                item = recovered
            else:
                skipped_items += 1
                continue

        if not isinstance(item, dict):
            skipped_items += 1
            continue
        if "id" not in item or "action" not in item or "confidence" not in item or "signal" not in item:
            skipped_items += 1
            continue
        agent_id = int(item["id"])
        reasoning = item.get("reasoning")
        if isinstance(reasoning, str):
            reasoning_lines = [reasoning.strip()] if reasoning.strip() else []
        elif isinstance(reasoning, list):
            reasoning_lines = [str(line).strip() for line in reasoning if str(line).strip()]
        else:
            skipped_items += 1
            continue
        results[agent_id] = {
            "reasoning": reasoning_lines,
            "action": str(item["action"]).strip(),
            "confidence": float(item["confidence"]),
            "signal": str(item["signal"]).strip(),
        }

    if skipped_items:
        logger.warning("K2 batch reasoning skipped %s malformed item(s) while recovering usable results.", skipped_items)

    missing = sorted(set(int(agent["id"]) for agent in agents) - set(results.keys()))
    if missing:
        raise ValueError(f"K2 batch reasoning omitted agent ids: {missing[:8]}")
    return results


async def call_k2_explanation_only(
    httpx_client: httpx.AsyncClient,
    *,
    agent_name: str,
    agent_role: str,
    role_lens: str,
    scenario: str,
    case_goal: str,
    precomputed_outcome: str,
    dominant_signal: str,
    social_context_label: str,
    primary_decision_anchor: str,
    traits: dict[str, float],
    demographics: dict[str, Any] | None,
    bsv: dict[str, float],
    score_breakdown: dict[str, float],
) -> list[str]:
    if not settings.ifm_api_key.strip() or not settings.ifm_api_url.strip():
        raise RuntimeError("IFM_API_KEY and IFM_API_URL are required. No K2 fallback is available.")

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.ifm_api_key}",
    }
    payload: dict[str, Any] = {
        "model": settings.ifm_k2_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": K2_EXPLANATION_ONLY_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Agent name: {agent_name}\n"
                    f"Agent role: {agent_role}\n"
                    f"Role lens: {role_lens}\n"
                    f"Scenario: {scenario[:900]}\n"
                    f"Case goal: {case_goal}\n"
                    f"Precomputed outcome: {precomputed_outcome}\n"
                    f"Dominant signal: {dominant_signal}\n"
                    f"Primary decision anchor: {primary_decision_anchor}\n"
                    f"Social context: {social_context_label}\n"
                    f"Demographics: {json.dumps(demographics or {}, ensure_ascii=True)}\n"
                    f"Traits: {json.dumps(traits, ensure_ascii=True)}\n"
                    f"BSV: {json.dumps(bsv, ensure_ascii=True)}\n"
                    f"Score breakdown: {json.dumps(score_breakdown, ensure_ascii=True)}\n"
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
    text = _strip_k2_hidden_reasoning(_openai_style_assistant_text(out)).strip()
    if not text:
        raise ValueError("K2 explanation-only call returned empty content.")
    lines = [line.strip(" -") for line in re.split(r"(?<=[.!?])\s+", text) if line.strip(" -")]
    return lines[:2] if lines else []


async def call_k2_timeline_batch(
    httpx_client: httpx.AsyncClient,
    *,
    items: list[dict[str, Any]],
) -> dict[tuple[int, int], dict[str, str]]:
    if not settings.ifm_api_key.strip() or not settings.ifm_api_url.strip():
        raise RuntimeError("IFM_API_KEY and IFM_API_URL are required. No K2 fallback is available.")
    if not items:
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
            {"role": "system", "content": K2_TIMELINE_BATCH_PROMPT},
            {"role": "user", "content": json.dumps(items, ensure_ascii=True)},
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
        raise ValueError("K2 timeline batch returned empty content.")
    parsed = _extract_json_payload(text)
    if isinstance(parsed, dict):
        for key in ("results", "items", "data", "timeline", "output"):
            candidate = parsed.get(key)
            if isinstance(candidate, list):
                parsed = candidate
                break
        else:
            nested = _find_first_list_candidate(parsed)
            if nested is not None:
                parsed = nested
    if not isinstance(parsed, list):
        raise ValueError("K2 timeline batch did not return a JSON array.")

    results: dict[tuple[int, int], dict[str, str]] = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        if not {"agent_id", "round", "phase_label", "trigger_label", "post", "change_summary"} <= set(item):
            continue
        key = (int(item["agent_id"]), int(item["round"]))
        results[key] = {
            "phase_label": str(item["phase_label"]).strip(),
            "trigger": str(item["trigger_label"]).strip(),
            "post": _strip_k2_hidden_reasoning(str(item["post"])).strip(),
            "change_summary": _strip_k2_hidden_reasoning(str(item["change_summary"])).strip(),
        }

    missing = sorted((int(item["agent_id"]), int(item["round"])) for item in items if (int(item["agent_id"]), int(item["round"])) not in results)
    if missing:
        raise ValueError(f"K2 timeline batch omitted entries: {missing[:8]}")
    return results


async def call_k2_action_center(
    httpx_client: httpx.AsyncClient,
    *,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not settings.ifm_api_key.strip() or not settings.ifm_api_url.strip():
        raise RuntimeError("IFM_API_KEY and IFM_API_URL are required. No K2 fallback is available.")

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.ifm_api_key}",
    }
    request_body: dict[str, Any] = {
        "model": settings.ifm_k2_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": K2_ACTION_CENTER_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
        ],
    }
    r = await httpx_client.post(
        settings.ifm_api_url,
        json=request_body,
        headers=headers,
        timeout=settings.simulate_k2_timeout_seconds,
    )
    r.raise_for_status()
    out = _k2_response_body_to_object(r)
    text = _openai_style_assistant_text(out)
    if not text.strip():
        raise ValueError("K2 action-center call returned empty content.")
    parsed = _extract_json_payload(text)
    if not isinstance(parsed, dict):
        raise ValueError("K2 action-center call did not return a JSON object.")
    return parsed


async def call_elevenlabs(
    httpx_client: httpx.AsyncClient,
    text: str,
    *,
    voice_context: dict[str, Any] | None = None,
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
    voice_settings = _voice_settings_from_context(voice_context or {})
    r = await httpx_client.post(
        url,
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": voice_settings,
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
    demographics: dict[str, Any] | None,
    spread_notes: str | None,
    tribe_state: dict[str, Any] | None,
    calibrated_state: dict[str, Any] | None,
    agent_profile: dict[str, Any] | None,
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
                    f"Demographics: {json.dumps(demographics or {}, ensure_ascii=True)}\n"
                    f"Operator spread notes: {spread_notes or 'None recorded yet'}\n"
                    f"TRIBE base state: {json.dumps(tribe_state or {}, ensure_ascii=True)}\n"
                    f"Calibrated state: {json.dumps(calibrated_state or {}, ensure_ascii=True)}\n"
                    f"Agent simulation profile: {json.dumps(agent_profile or {}, ensure_ascii=True)}\n"
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
    text = _strip_k2_hidden_reasoning(_openai_style_assistant_text(out)).strip()
    if not text:
        raise ValueError("K2 agent conversation returned empty content.")
    return text


def _voice_settings_from_context(voice_context: dict[str, Any]) -> dict[str, float | bool]:
    demographics = voice_context.get("demographics") or {}
    outcome = voice_context.get("outcome") or {}
    tribe = voice_context.get("tribe") or {}
    calibrated = voice_context.get("calibrated") or {}
    digital_habit = str(demographics.get("digital_media_habit") or "").lower()
    age_band = str(demographics.get("age_band") or "").lower()
    stance = str(outcome.get("belief_state") or outcome.get("stance") or "").lower()
    confidence = float(outcome.get("confidence") or 0.55)
    cognitive_load = float(tribe.get("cognitive_load") or calibrated.get("cognitive_load") or 0.5)
    agitation = float(tribe.get("emotional_agitation") or calibrated.get("emotional_agitation") or 0.5)
    defensive = float(tribe.get("defensive_posture") or calibrated.get("defensive_posture") or 0.4)
    memory_strain = float(tribe.get("working_memory_strain") or calibrated.get("working_memory_strain") or 0.5)

    stability = 0.48
    similarity_boost = 0.76
    style = 0.22
    speed = 1.0

    if "group-chat" in digital_habit or "public-feed" in digital_habit:
        style += 0.12
        stability -= 0.05
    if "local-news" in digital_habit or "mixed verification" in digital_habit:
        stability += 0.1
        style -= 0.04
    if "55-64" in age_band:
        speed -= 0.05
        stability += 0.06
    elif "18-24" in age_band or "25-34" in age_band:
        speed += 0.03
        style += 0.04
    if stance == "rejected":
        stability += 0.05
        style -= 0.03
    elif stance == "adopted":
        style += 0.05
    stability += (defensive - 0.45) * 0.12
    style += (agitation - 0.5) * 0.18
    speed += (agitation - 0.5) * 0.08
    speed -= (memory_strain - 0.5) * 0.06
    similarity_boost += (cognitive_load - 0.5) * 0.08
    style += max(-0.05, min(0.10, (confidence - 0.5) * 0.18))
    return {
        "stability": max(0.2, min(0.85, round(stability, 3))),
        "similarity_boost": max(0.2, min(0.95, round(similarity_boost, 3))),
        "style": max(0.0, min(0.75, round(style, 3))),
        "speed": max(0.88, min(1.08, round(speed, 3))),
        "use_speaker_boost": True,
    }
