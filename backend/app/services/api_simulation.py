"""
Independent-agent simulation for `POST /api/simulate`.

Every agent receives:
- a TRIBE-derived biological state vector
- spatial/social context from nearby agents
- an independent K2 decision and reasoning trace
- a richer derived brain-region profile for UI visualization
"""

from __future__ import annotations

import asyncio
import html
import hashlib
import math
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

from app.city_presets import get_city
from app.config import get_settings
from app.services.ai_clients import BSV, call_k2_think, call_tribe_modal_batch

settings = get_settings()

SignalType = Literal[
    "cognitive_overload",
    "defensive_reactance",
    "empathic_resonance",
    "memory_alignment",
    "social_proof",
]

ROLES = (
    "Civic analyst",
    "Field organizer",
    "Educator",
    "Healthcare worker",
    "Policy aide",
    "Journalist",
    "Engineer",
    "Small business owner",
    "Researcher",
    "First responder",
    "Operations lead",
)

USE_CASE_CONTEXT: dict[str, str] = {
    "political": "campaign persuasion and turnout framing",
    "public_health": "public-health trust, uptake, and behavioral change",
    "urban": "urban planning, zoning, and neighborhood buy-in",
    "corporate": "corporate communications and change management",
}

FIRST = [
    "Ava",
    "Noah",
    "Mia",
    "Liam",
    "Zoe",
    "Eli",
    "Maya",
    "Owen",
    "Iris",
    "Kai",
    "Lena",
    "Theo",
    "Nora",
    "Ezra",
]
LAST = [
    "Ramos",
    "Chen",
    "Patel",
    "Nguyen",
    "Okafor",
    "Silva",
    "Khan",
    "Walsh",
    "Brooks",
    "Tanaka",
    "Mendez",
    "Park",
    "Aoki",
    "Diallo",
]

_THINK_RE = re.compile(r"<think>([\s\S]*?)</think>", re.IGNORECASE)
_ACTION_RE = re.compile(r"<action>\s*(Adopted|Rejected)\s*</action>", re.IGNORECASE)
_CONFIDENCE_RE = re.compile(r"<confidence>\s*([01](?:\.\d+)?)\s*</confidence>", re.IGNORECASE)
_SIGNAL_RE = re.compile(r"<signal>\s*([a-z_]+)\s*</signal>", re.IGNORECASE)


class _ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if self._skip_depth == 0 and tag in {"p", "h1", "h2", "h3", "li", "article", "section", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
        if self._skip_depth == 0 and tag in {"p", "h1", "h2", "h3", "li", "article", "section"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self.parts.append(text)


def _compress_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_page_text(html_text: str) -> str:
    parser = _ReadableHTMLParser()
    parser.feed(html_text)
    raw = html.unescape(" ".join(parser.parts))
    lines = [_compress_ws(line) for line in raw.splitlines()]
    text = "\n".join(line for line in lines if line)
    return text[:3200]


async def _fetch_source_context(
    httpx_client: httpx.AsyncClient,
    source_url: str | None,
) -> tuple[str | None, str | None]:
    if not source_url:
        return None, None

    try:
        parsed = urlparse(source_url)
        if parsed.scheme not in {"http", "https"}:
            return None, "Source URL must use http or https."

        response = await httpx_client.get(
            source_url,
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "CortexiaCompass/0.2 (+source-ingestion)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
            },
        )
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "").lower()

        if "text/html" in content_type or "<html" in response.text[:500].lower():
            extracted = _extract_page_text(response.text)
        else:
            extracted = response.text[:3200]

        extracted = _compress_ws(extracted)
        if not extracted:
            return None, "Source URL responded, but no readable text could be extracted."
        return extracted[:2000], None
    except Exception:
        return None, "Source URL could not be fetched; simulation used the typed message only."


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _seeded(i: int) -> float:
    x = math.sin(i * 9301 + 49297) * 233280
    return x - math.floor(x)


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return ["No reasoning returned."]
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()][:6]


@dataclass(frozen=True)
class _Virt:
    id: int
    name: str
    role: str
    lat: float
    lng: float


@dataclass(frozen=True)
class _Region:
    agent_id: int
    latitude: float
    longitude: float
    bsv: BSV


def _build_virtual_population(city_id: str, count: int) -> list[_Virt]:
    city = get_city(city_id)
    half = city.span / 2
    out: list[_Virt] = []
    for i in range(count):
        r1 = _seeded(i + 1)
        r2 = _seeded(i + 1001)
        lng = city.longitude - half + r1 * city.span
        lat = city.latitude - half * 0.8 + r2 * city.span * 0.8
        out.append(
            _Virt(
                id=i,
                name=f"{FIRST[i % len(FIRST)]} {LAST[(i * 3) % len(LAST)]}",
                role=ROLES[i % len(ROLES)],
                lat=lat,
                lng=lng,
            )
        )
    return out


def _noise_bsv(base: BSV, agent_id: int, message_complexity: float) -> BSV:
    message_complexity = _clamp(message_complexity)
    jitter = 0.16 * (0.35 + message_complexity)

    def value(key: str, offset: int) -> float:
        raw = float(base[key])  # type: ignore[index]
        delta = (_seeded(agent_id * 17 + offset) - 0.5) * jitter
        return _clamp(raw + delta)

    return {
        "cognitive_load": value("cognitive_load", 11),
        "emotional_agitation": value("emotional_agitation", 23),
        "defensive_posture": value("defensive_posture", 37),
        "working_memory_strain": value("working_memory_strain", 51),
    }


def _within_radius(a_lat: float, a_lng: float, b_lat: float, b_lng: float, radius_deg: float = 0.05) -> bool:
    dlat, dlng = abs(a_lat - b_lat), abs(a_lng - b_lng)
    return (dlat**2 + dlng**2) ** 0.5 <= radius_deg


def _neighbor_context(me: _Virt, regions: list[_Region]) -> tuple[int, int, float]:
    supportive = 0
    total = 0
    resonance = 0.0
    for other in regions:
        if other.agent_id == me.id:
            continue
        if not _within_radius(me.lat, me.lng, other.latitude, other.longitude):
            continue
        total += 1
        openness = 1.0 - (0.55 * other.bsv["defensive_posture"] + 0.45 * other.bsv["cognitive_load"])
        resonance += max(0.0, openness)
        if other.bsv["defensive_posture"] < 0.52 and other.bsv["cognitive_load"] < 0.68:
            supportive += 1
    if total == 0:
        return 0, 0, 0.0
    return supportive, total, resonance / total


def _apply_spatial_bsv(base: BSV, supportive_neighbors: int, total_neighbors: int, resonance: float) -> BSV:
    social_boost = 0.0 if total_neighbors == 0 else min(0.16, supportive_neighbors / max(1, total_neighbors) * 0.18)
    return {
        "cognitive_load": _clamp(base["cognitive_load"] - social_boost * 0.35),
        "emotional_agitation": _clamp(base["emotional_agitation"] + (0.5 - resonance) * 0.08),
        "defensive_posture": _clamp(base["defensive_posture"] - social_boost + (0.45 - resonance) * 0.1),
        "working_memory_strain": _clamp(base["working_memory_strain"] + base["cognitive_load"] * 0.06),
    }


def _derive_brain_regions(bsv: BSV, *, role: str, supportive_neighbors: int, resonance: float, agent_id: int) -> dict[str, float]:
    role_lower = role.lower()
    analytic_bias = 0.08 if any(token in role_lower for token in ("analyst", "engineer", "research")) else 0.0
    service_bias = 0.07 if any(token in role_lower for token in ("health", "educator", "responder")) else 0.0
    social_bias = min(0.12, supportive_neighbors * 0.02 + resonance * 0.06)
    novelty = (_seeded(agent_id + 902) - 0.5) * 0.08

    prefrontal = _clamp(0.35 + bsv["working_memory_strain"] * 0.45 + analytic_bias)
    amygdala = _clamp(0.18 + bsv["emotional_agitation"] * 0.5 + bsv["defensive_posture"] * 0.22)
    insula = _clamp(0.2 + bsv["defensive_posture"] * 0.55 + novelty * 0.4)
    hippocampus = _clamp(0.22 + (1 - bsv["working_memory_strain"]) * 0.24 + service_bias)
    anterior_cingulate = _clamp(0.25 + bsv["cognitive_load"] * 0.32 + (0.5 - resonance) * 0.18)
    temporoparietal_junction = _clamp(0.24 + social_bias + service_bias * 0.45)

    return {
        "prefrontal_cortex": prefrontal,
        "amygdala": amygdala,
        "insula": insula,
        "hippocampus": hippocampus,
        "anterior_cingulate": anterior_cingulate,
        "temporoparietal_junction": temporoparietal_junction,
    }


def _dominant_signal(bsv: BSV, regions: dict[str, float], supportive_neighbors: int) -> SignalType:
    if bsv["defensive_posture"] > 0.7 or regions["insula"] > 0.72:
        return "defensive_reactance"
    if bsv["cognitive_load"] > 0.72 or bsv["working_memory_strain"] > 0.72:
        return "cognitive_overload"
    if supportive_neighbors >= 4 or regions["temporoparietal_junction"] > 0.72:
        return "social_proof"
    if regions["hippocampus"] > 0.68:
        return "memory_alignment"
    return "empathic_resonance"


def _parse_k2_output(raw: str, fallback_signal: SignalType) -> tuple[list[str], str, float, SignalType]:
    think_match = _THINK_RE.search(raw)
    action_match = _ACTION_RE.search(raw)
    confidence_match = _CONFIDENCE_RE.search(raw)
    signal_match = _SIGNAL_RE.search(raw)

    thinking = think_match.group(1).strip() if think_match else raw.strip()
    action = action_match.group(1).lower() if action_match else "rejected"
    confidence = float(confidence_match.group(1)) if confidence_match else 0.58
    signal_text = signal_match.group(1).strip().lower() if signal_match else fallback_signal
    signal: SignalType = fallback_signal
    if signal_text in {
        "cognitive_overload",
        "defensive_reactance",
        "empathic_resonance",
        "memory_alignment",
        "social_proof",
    }:
        signal = signal_text  # type: ignore[assignment]
    return _sentences(thinking), action, _clamp(confidence), signal


def _signal_label(signal: SignalType) -> str:
    return {
        "cognitive_overload": "cognitive overload",
        "defensive_reactance": "defensive reactance",
        "empathic_resonance": "empathic resonance",
        "memory_alignment": "memory alignment",
        "social_proof": "social proof",
    }[signal]


def _signal_summary(signal: SignalType, state: str, regions: dict[str, float]) -> str:
    if signal == "defensive_reactance":
        return (
            f"Insula {regions['insula']:.2f} and amygdala {regions['amygdala']:.2f} dominate, "
            f"so this agent reads the message as threat and lands in {state}."
        )
    if signal == "cognitive_overload":
        return (
            f"Prefrontal cortex {regions['prefrontal_cortex']:.2f} and ACC {regions['anterior_cingulate']:.2f} "
            f"show overload, so the message feels effortful and resolves to {state}."
        )
    if signal == "social_proof":
        return (
            f"TPJ {regions['temporoparietal_junction']:.2f} is elevated and nearby resonance is favorable, "
            f"so social proof pushes this agent toward {state}."
        )
    if signal == "memory_alignment":
        return (
            f"Hippocampus {regions['hippocampus']:.2f} is comparatively high, suggesting the message maps "
            f"to familiar priors and settles at {state}."
        )
    return (
        f"Empathic and reflective regions stay balanced, giving this agent enough openness to remain {state} "
        f"without strong threat activation."
    )


async def _run_agent_reasoning(
    httpx_client: httpx.AsyncClient,
    *,
    agent: _Virt,
    catalyst_text: str,
    use_case: str,
    bsv: BSV,
    supportive_neighbors: int,
    total_neighbors: int,
    resonance: float,
    regions: dict[str, float],
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    signal = _dominant_signal(bsv, regions, supportive_neighbors)

    async with semaphore:
        try:
            raw = await call_k2_think(
                httpx_client,
                name=agent.name,
                role=f"{agent.role} in {USE_CASE_CONTEXT.get(use_case, use_case)}",
                bsv=bsv,
                adopted_neighbor_count=supportive_neighbors,
                total_neighbors_in_radius=total_neighbors,
                catalyst_text=(
                    f"{catalyst_text}\n"
                    f"Context: target domain={USE_CASE_CONTEXT.get(use_case, use_case)}; "
                    f"neural dominant signal={_signal_label(signal)}; local resonance={resonance:.2f}."
                ),
            )
        except Exception:
            raw = (
                "<think>Upstream K2 failure; falling back to a conservative local decision based on the "
                f"agent's neural profile and neighborhood context.</think>"
                f"<action>{'Rejected' if signal in ('defensive_reactance', 'cognitive_overload') else 'Adopted'}</action>"
                f"<confidence>{0.62 if signal in ('defensive_reactance', 'cognitive_overload') else 0.57:.2f}</confidence>"
                f"<signal>{signal}</signal>"
            )

    reasoning, action, confidence, parsed_signal = _parse_k2_output(raw, signal)
    if confidence < 0.58 and parsed_signal in {"memory_alignment", "empathic_resonance", "social_proof"}:
        state = "neutral"
    else:
        state = "adopted" if action == "adopted" else "rejected"

    return {
        "id": agent.id,
        "name": agent.name,
        "role": agent.role,
        "longitude": agent.lng,
        "latitude": agent.lat,
        "belief_state": state,
        "k2_reasoning_trace": reasoning,
        "k2_decision_confidence": confidence,
        "dominant_signal": parsed_signal,
        "brain_regions": regions,
        "brain_summary": _signal_summary(parsed_signal, state, regions),
        "tribe_neurological_metrics": {
            "cognitive_load": float(bsv["cognitive_load"]),
            "emotional_friction": float(bsv["emotional_agitation"]),
            "defensive_activation": float(bsv["defensive_posture"]),
            "working_memory_strain": float(bsv["working_memory_strain"]),
        },
        "_supportive_neighbors": supportive_neighbors,
        "_neighbor_total": total_neighbors,
        "_resonance": resonance,
    }


def _cluster_key(city_id: str, latitude: float, longitude: float) -> tuple[str, str]:
    city = get_city(city_id)
    vertical = "North" if latitude >= city.latitude else "South"
    horizontal = "East" if longitude >= city.longitude else "West"
    return f"{vertical}{horizontal}", f"{vertical} {horizontal} corridor"


def _build_hotspots(city_id: str, agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rejected = [a for a in agents if a["belief_state"] == "rejected"]
    if not rejected:
        return []

    buckets: dict[str, dict[str, Any]] = {}
    for agent in rejected:
        key, label = _cluster_key(city_id, agent["latitude"], agent["longitude"])
        bucket = buckets.setdefault(
            key,
            {
                "id": key.lower(),
                "label": label,
                "area": label,
                "count": 0,
                "lat_sum": 0.0,
                "lng_sum": 0.0,
                "share_sum": 0.0,
            },
        )
        bucket["count"] += 1
        bucket["lat_sum"] += agent["latitude"]
        bucket["lng_sum"] += agent["longitude"]
        bucket["share_sum"] += 1.0 / len(rejected)

    ranked = sorted(buckets.values(), key=lambda item: item["count"], reverse=True)[:3]
    return [
        {
            "id": item["id"],
            "label": item["label"],
            "area": item["area"],
            "share": round(item["share_sum"], 3),
            "lng": item["lng_sum"] / item["count"],
            "lat": item["lat_sum"] / item["count"],
            "radiusMeters": 1400 + item["count"] * 180,
        }
        for item in ranked
    ]


def _top_reason(agents: list[dict[str, Any]], signal: SignalType) -> int:
    return sum(1 for agent in agents if agent["dominant_signal"] == signal)


def _build_synthetic_thoughts(agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        agents,
        key=lambda agent: (
            1 if agent["belief_state"] == "rejected" else 0,
            agent["k2_decision_confidence"],
            agent["tribe_neurological_metrics"]["defensive_activation"],
        ),
        reverse=True,
    )[:14]

    thoughts: list[dict[str, Any]] = []
    for agent in ranked:
        sentiment = (
            "negative"
            if agent["belief_state"] == "rejected"
            else "positive"
            if agent["belief_state"] == "adopted"
            else "neutral"
        )
        first_line = agent["k2_reasoning_trace"][0] if agent["k2_reasoning_trace"] else agent["brain_summary"]
        thoughts.append(
            {
                "agent_id": agent["id"],
                "text": first_line,
                "sentiment": sentiment,
                "driver": _signal_label(agent["dominant_signal"]),
            }
        )
    return thoughts


def _build_suggested_rewrite(catalyst_text: str, rejected: int, overload: int, defense: int, social: int) -> str:
    opener = catalyst_text.strip().split(".")[0][:90].strip() or catalyst_text.strip()[:90]
    if defense >= max(overload, social):
        return (
            f"Lead with a low-threat community benefit instead of a hard directive: "
            f"'{opener} because it reduces friction for your local team, with support built in from day one.'"
        )
    if overload >= max(defense, social):
        return (
            f"Simplify the first sentence and front-load the payoff: "
            f"'{opener} in one clear step, with the timeline and support details spelled out upfront.'"
        )
    if rejected > 0:
        return (
            f"Add neighborhood-level social proof and a visible peer anchor: "
            f"'{opener} and teams like yours are already testing it successfully in similar conditions.'"
        )
    return (
        f"Keep the current framing, but make the benefit concrete and local: "
        f"'{opener} with one clear example, one timeline, and one support promise.'"
    )


def _build_report(city_id: str, catalyst_text: str, use_case: str, agents: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(agents)
    adopted = sum(1 for agent in agents if agent["belief_state"] == "adopted")
    rejected = sum(1 for agent in agents if agent["belief_state"] == "rejected")
    neutral = total - adopted - rejected
    avg_load = sum(agent["tribe_neurological_metrics"]["cognitive_load"] for agent in agents) / max(1, total)
    avg_defense = sum(agent["tribe_neurological_metrics"]["defensive_activation"] for agent in agents) / max(1, total)
    avg_confidence = sum(agent["k2_decision_confidence"] for agent in agents) / max(1, total)
    adoption_rate = adopted / max(1, total)

    overload = _top_reason(agents, "cognitive_overload")
    defense = _top_reason(agents, "defensive_reactance")
    social = _top_reason(agents, "social_proof")

    score = round(
        _clamp(
            0.58 * adoption_rate
            + 0.18 * (1 - avg_defense)
            + 0.14 * (1 - avg_load)
            + 0.10 * avg_confidence,
            0.0,
            1.0,
        )
        * 100
    )
    risk_level = "Strong" if score >= 72 else "Moderate" if score >= 48 else "High Risk"
    hotspots = _build_hotspots(city_id, agents)

    top_hotspot = hotspots[0]["label"] if hotspots else "the city perimeter"
    city = get_city(city_id)
    insights = [
        {
            "where": top_hotspot,
            "why": (
                "Threat detection dominates the message read."
                if defense >= max(overload, social)
                else "The message is too dense for fast uptake."
                if overload >= max(defense, social)
                else "Adoption depends heavily on peer confirmation."
            ),
            "who": (
                "agents with elevated insula/amygdala activation"
                if defense >= max(overload, social)
                else "agents with high prefrontal and ACC load"
                if overload >= max(defense, social)
                else "socially attentive agents waiting for local proof"
            ),
        },
        {
            "where": f"{city.label} network-wide",
            "why": f"Average cognitive load is {avg_load:.2f} and defensive activation is {avg_defense:.2f}.",
            "who": f"{adopted} adopted, {rejected} rejected, {neutral} stayed neutral.",
        },
        {
            "where": "Agent-level neural profile",
            "why": "Each node now carries its own K2 decision, confidence, and region-level brain signature.",
            "who": f"The strongest recurring driver was {_signal_label('defensive_reactance' if defense >= max(overload, social) else 'cognitive_overload' if overload >= social else 'social_proof')}.",
        },
    ]

    return {
        "score": score,
        "risk_level": risk_level,
        "insights": insights,
        "suggested_rewrite": _build_suggested_rewrite(catalyst_text, rejected, overload, defense, social),
        "synthetic_thoughts": _build_synthetic_thoughts(agents),
        "hotspots": hotspots,
        "summary_text": (
            f"{adopted} of {total} agents adopted the message. "
            f"The network average load is {avg_load:.2f} and average defensive activation is {avg_defense:.2f}."
        ),
        "sentiment_mix": {
            "adopted": adopted,
            "rejected": rejected,
            "neutral": neutral,
        },
        "input_summary": catalyst_text[:240],
    }


async def run_simulation_http(
    *,
    city_id: str,
    catalyst_text: str,
    source_url: str | None,
    use_case: str,
    message_complexity: float,
) -> dict[str, object]:
    n_agents = settings.simulate_population_size
    population = _build_virtual_population(city_id, n_agents)

    async with httpx.AsyncClient() as httpx_client:
        source_context, source_warning = await _fetch_source_context(httpx_client, source_url)
        effective_catalyst_text = catalyst_text.strip()
        if source_context:
            effective_catalyst_text = (
                f"{effective_catalyst_text}\n\n"
                f"Source context excerpt:\n{source_context}"
            )

        batch_agents = [
            {
                "id": agent.id,
                "role": agent.role,
                "latitude": agent.lat,
                "longitude": agent.lng,
            }
            for agent in population
        ]
        tribe_results = await call_tribe_modal_batch(httpx_client, effective_catalyst_text, batch_agents)

        noisy_regions: list[_Region] = []
        for agent in population:
            base = tribe_results.get(
                str(agent.id),
                {
                    "cognitive_load": 0.5,
                    "emotional_agitation": 0.5,
                    "defensive_posture": 0.5,
                    "working_memory_strain": 0.5,
                },
            )
            noisy_regions.append(
                _Region(
                    agent_id=agent.id,
                    latitude=agent.lat,
                    longitude=agent.lng,
                    bsv=_noise_bsv(base, agent.id, message_complexity),
                )
            )

        semaphore = asyncio.Semaphore(settings.simulate_k2_concurrency)
        tasks = []
        for agent in population:
            raw_region = next(region for region in noisy_regions if region.agent_id == agent.id)
            supportive_neighbors, total_neighbors, resonance = _neighbor_context(agent, noisy_regions)
            adjusted_bsv = _apply_spatial_bsv(raw_region.bsv, supportive_neighbors, total_neighbors, resonance)
            regions = _derive_brain_regions(
                adjusted_bsv,
                role=agent.role,
                supportive_neighbors=supportive_neighbors,
                resonance=resonance,
                agent_id=agent.id,
            )
            tasks.append(
                _run_agent_reasoning(
                    httpx_client,
                    agent=agent,
                    catalyst_text=effective_catalyst_text,
                    use_case=use_case,
                    bsv=adjusted_bsv,
                    supportive_neighbors=supportive_neighbors,
                    total_neighbors=total_neighbors,
                    resonance=resonance,
                    regions=regions,
                    semaphore=semaphore,
                )
            )

        agents = list(await asyncio.gather(*tasks))
        agents.sort(key=lambda agent: agent["id"])
        report = _build_report(city_id, effective_catalyst_text, use_case, agents)
        report["source_context_summary"] = source_context[:280] if source_context else None
        report["source_warning"] = source_warning

        cleaned_agents = []
        for agent in agents:
            cleaned = dict(agent)
            cleaned.pop("_supportive_neighbors", None)
            cleaned.pop("_neighbor_total", None)
            cleaned.pop("_resonance", None)
            cleaned_agents.append(cleaned)

        adopted = report["sentiment_mix"]["adopted"]
        rejected = report["sentiment_mix"]["rejected"]
        neutral = report["sentiment_mix"]["neutral"]

        return {
            "city_id": city_id,
            "use_case": use_case,
            "source_url": source_url,
            "effective_catalyst_text": effective_catalyst_text,
            "agents": cleaned_agents,
            "macro_result": report,
            "summary": {
                "total": len(cleaned_agents),
                "adopted": adopted,
                "rejected": rejected,
                "neutral": neutral,
            },
        }
