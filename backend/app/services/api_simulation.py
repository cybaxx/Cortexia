"""
Case-oriented misinformation analysis for `POST /api/simulate`.

The backend now returns a research workspace payload:
- evidence trace
- spread model
- mechanisms
- intervention playbook
- case summary
- per-agent diagnostics for deep inspection
"""

from __future__ import annotations

import asyncio
import html
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

DOMAIN_CONTEXT: dict[str, str] = {
    "political": "campaign persuasion and civic trust",
    "public_health": "public-health trust, misinformation resistance, and behavioral adoption",
    "urban": "urban planning, land-use communication, and neighborhood buy-in",
    "corporate": "organizational communications and change-management trust",
}

THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "identity": ("maga", "community", "people", "look down", "republican", "democrat"),
    "trust": ("trust", "fair", "feeling", "believe", "heard", "respect", "dismissed"),
    "authority": ("mandatory", "directive", "policy", "official", "institution"),
    "health": ("health", "vaccine", "public health", "doctor", "clinic"),
    "threat": ("threat", "danger", "harm", "attack", "fear"),
}

LOW_CREDIBILITY_PATTERNS: tuple[tuple[str, float], ...] = (
    ("alcohol is good for you", 0.62),
    ("smoking is good for you", 0.78),
    ("vaccines are poison", 0.72),
    ("cures cancer", 0.48),
    ("miracle cure", 0.42),
    ("safe for everyone", 0.22),
    ("harmless", 0.16),
)

INTERVENTION_LIBRARY: dict[SignalType, dict[str, str]] = {
    "defensive_reactance": {
        "recommended_channel": "trusted community forums and local surrogates",
        "recommended_messenger": "peer validators with in-group credibility",
        "message_strategy": "lead with respect, acknowledge the underlying feeling, and lower perceived status threat before presenting corrections",
        "time_horizon": "Immediate",
        "expected_effect": "Reduce rejection and create conditions for a second-touch factual intervention",
    },
    "cognitive_overload": {
        "recommended_channel": "short-form explainers and one-page briefs",
        "recommended_messenger": "subject-matter experts with plain-language credibility",
        "message_strategy": "compress the claim into one myth, one fact, and one action; avoid stacking caveats in the opener",
        "time_horizon": "Immediate",
        "expected_effect": "Improve comprehension and reduce misinterpretation-driven spread",
    },
    "social_proof": {
        "recommended_channel": "community newsletters, SMS, and testimonial clips",
        "recommended_messenger": "high-trust local messengers and visible early adopters",
        "message_strategy": "show who already rejects the misinformation and why, making corrective behavior socially legible",
        "time_horizon": "Near-term",
        "expected_effect": "Shift undecided agents by changing perceived community norms",
    },
    "memory_alignment": {
        "recommended_channel": "contextual explainers paired with historical examples",
        "recommended_messenger": "educators, librarians, and domain historians",
        "message_strategy": "anchor the correction to a familiar local story or prior trusted event",
        "time_horizon": "Near-term",
        "expected_effect": "Make the corrective frame easier to encode and recall",
    },
    "empathic_resonance": {
        "recommended_channel": "listening sessions and narrative-based outreach",
        "recommended_messenger": "community leaders trained in dialogue",
        "message_strategy": "validate the emotional concern first, then introduce the factual corrective without confrontation",
        "time_horizon": "Short-cycle",
        "expected_effect": "Increase openness among persuadable but emotionally activated audiences",
    },
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


def _compress_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _seeded(i: int) -> float:
    x = math.sin(i * 9301 + 49297) * 233280
    return x - math.floor(x)


def _extract_page_text(html_text: str) -> str:
    parser = _ReadableHTMLParser()
    parser.feed(html_text)
    raw = html.unescape(" ".join(parser.parts))
    lines = [_compress_ws(line) for line in raw.splitlines()]
    text = "\n".join(line for line in lines if line)
    return text[:3200]


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return ["No reasoning returned."]
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()][:6]


async def _fetch_source_context(httpx_client: httpx.AsyncClient, source_url: str | None) -> tuple[str | None, str | None]:
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
                "User-Agent": "CortexiaCompass/0.3 (+evidence-ingestion)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
            },
        )
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "").lower()
        extracted = _extract_page_text(response.text) if "text/html" in content_type or "<html" in response.text[:500].lower() else response.text[:3200]
        extracted = _compress_ws(extracted)
        if not extracted:
            return None, "Source URL responded, but no readable text could be extracted."
        return extracted[:2000], None
    except Exception:
        return None, "Source URL could not be fetched; analysis used the provided text and transcript only."


def _build_virtual_population(city_id: str, count: int) -> list[_Virt]:
    city = get_city(city_id)
    zones = list(city.land_zones)
    zone_areas = [
        max(0.000001, (zone.lng_max - zone.lng_min) * (zone.lat_max - zone.lat_min))
        for zone in zones
    ]
    total_area = sum(zone_areas)
    cumulative: list[float] = []
    running = 0.0
    for area in zone_areas:
        running += area / total_area
        cumulative.append(running)

    out: list[_Virt] = []
    for i in range(count):
        zone_pick = _seeded(i + 8500)
        zone_idx = next((idx for idx, bound in enumerate(cumulative) if zone_pick <= bound), 0)
        zone = zones[max(0, zone_idx)]
        r1 = _seeded(i + 1)
        r2 = _seeded(i + 1001)
        lng_inset = (zone.lng_max - zone.lng_min) * 0.08
        lat_inset = (zone.lat_max - zone.lat_min) * 0.08
        out.append(
            _Virt(
                id=i,
                name=f"{FIRST[i % len(FIRST)]} {LAST[(i * 3) % len(LAST)]}",
                role=ROLES[i % len(ROLES)],
                lng=zone.lng_min + lng_inset + r1 * max(0.0001, zone.lng_max - zone.lng_min - lng_inset * 2),
                lat=zone.lat_min + lat_inset + r2 * max(0.0001, zone.lat_max - zone.lat_min - lat_inset * 2),
            )
        )
    return out


def _keyword_density(text: str, words: tuple[str, ...]) -> float:
    lowered = text.lower()
    hits = sum(lowered.count(word) for word in words)
    return _clamp(hits / 4.0)


def _case_feature_vector(analysis_text: str, case_goal: str, domain: str, message_complexity: float) -> dict[str, float]:
    joined = f"{analysis_text}\n{case_goal}\n{domain}"
    return {
        "threat": _keyword_density(joined, ("threat", "attack", "danger", "fear", "forced", "mandatory")),
        "identity": _keyword_density(joined, ("maga", "community", "people", "look down", "republican", "democrat", "us", "them")),
        "institutional": _keyword_density(joined, ("official", "policy", "institution", "government", "public health", "authority")),
        "prosocial": _keyword_density(joined, ("community", "support", "benefit", "care", "help", "trust", "neighbors")),
        "complexity": _clamp(message_complexity * 0.65 + min(len(analysis_text), 1200) / 2400.0),
    }


def _claim_diagnostics(analysis_text: str, domain: str, source_excerpt: str | None) -> dict[str, float | str]:
    lowered = analysis_text.lower()
    credibility = 0.56
    harm = 0.22

    for pattern, penalty in LOW_CREDIBILITY_PATTERNS:
        if pattern in lowered:
            credibility -= penalty
            harm += penalty * 0.55

    if domain == "public_health":
        if "alcohol" in lowered and any(token in lowered for token in ("good for you", "healthy", "beneficial", "great for")):
            credibility -= 0.38
            harm += 0.28
        if any(token in lowered for token in ("doctor hate this", "they don't want you to know", "secret cure")):
            credibility -= 0.24
            harm += 0.16

    if any(token in lowered for token in ("always", "never", "everyone", "nobody", "proves that")):
        credibility -= 0.08
    if source_excerpt:
        credibility += 0.05
    if any(token in lowered for token in ("study", "according to", "data", "evidence")):
        credibility += 0.04

    credibility = _clamp(credibility, 0.05, 0.95)
    harm = _clamp(harm, 0.05, 0.95)
    risk_label = "High" if credibility < 0.3 or harm > 0.62 else "Moderate" if credibility < 0.48 else "Low"
    return {
        "credibility": credibility,
        "harm": harm,
        "risk_label": risk_label,
    }


def _model_fidelity_factor(source_excerpt: str | None) -> tuple[float, list[str]]:
    notes: list[str] = []
    fidelity = 0.48
    if settings.tribe_modal_url.strip():
        fidelity += 0.18
    else:
        notes.append("TRIBE is running in fallback/demo mode, so neural-state fidelity is limited.")
    if settings.ifm_api_key.strip():
        fidelity += 0.16
    else:
        notes.append("K2 reasoning is running in fallback mode, so behavioral explanations are heuristic.")
    if source_excerpt:
        fidelity += 0.08
    else:
        notes.append("No external source excerpt was retrieved, so credibility estimates rely mostly on the submitted claim text.")
    return _clamp(fidelity, 0.25, 0.9), notes


def _agent_conditioning(agent: _Virt, city_id: str) -> dict[str, float]:
    role = agent.role.lower()
    city = get_city(city_id)
    northness = _clamp((agent.lat - min(zone.lat_min for zone in city.land_zones)) / max(0.001, max(zone.lat_max for zone in city.land_zones) - min(zone.lat_min for zone in city.land_zones)))
    eastness = _clamp((agent.lng - min(zone.lng_min for zone in city.land_zones)) / max(0.001, max(zone.lng_max for zone in city.land_zones) - min(zone.lng_min for zone in city.land_zones)))

    analytical = 1.0 if any(token in role for token in ("analyst", "engineer", "research")) else 0.0
    service = 1.0 if any(token in role for token in ("health", "educator", "responder")) else 0.0
    civic = 1.0 if any(token in role for token in ("policy", "journalist", "organizer")) else 0.0

    return {
        "analytical": analytical,
        "service": service,
        "civic": civic,
        "peripheral_pressure": abs(0.5 - northness) * 0.35 + abs(0.5 - eastness) * 0.35,
        "institutional_trust": _clamp(0.42 + service * 0.16 + civic * 0.08 - analytical * 0.04),
        "identity_salience": _clamp(0.34 + civic * 0.18 + analytical * 0.07),
    }


def _apply_lfcm_calibration(
    base: BSV,
    *,
    agent: _Virt,
    city_id: str,
    case_features: dict[str, float],
    message_complexity: float,
) -> BSV:
    """
    Lightweight calibration layer on top of TRIBE.
    This replaces arbitrary jitter with a bounded math model that:
    - preserves the original TRIBE signal
    - adds role / case conditioning
    - regularizes toward the base state to avoid exaggerated subgroup drift
    """
    cond = _agent_conditioning(agent, city_id)
    complexity = _clamp(message_complexity)

    def calibrate(raw: float, delta: float, regularizer: float = 0.18) -> float:
        centered = raw - 0.5
        adjusted = 0.5 + centered * 0.72 + delta * (1.0 - regularizer)
        return _clamp(adjusted)

    cognitive_delta = (
        case_features["complexity"] * 0.22
        + cond["analytical"] * 0.06
        + cond["peripheral_pressure"] * 0.04
        - cond["institutional_trust"] * 0.03
        + (_seeded(agent.id * 17 + 11) - 0.5) * 0.04
    )
    emotional_delta = (
        case_features["threat"] * 0.16
        + case_features["identity"] * 0.08
        + cond["identity_salience"] * 0.06
        - case_features["prosocial"] * 0.05
        + (_seeded(agent.id * 17 + 23) - 0.5) * 0.05
    )
    defensive_delta = (
        case_features["threat"] * 0.18
        + case_features["institutional"] * (0.09 - cond["institutional_trust"] * 0.06)
        + case_features["identity"] * cond["identity_salience"] * 0.10
        + complexity * 0.04
        + (_seeded(agent.id * 17 + 37) - 0.5) * 0.05
    )
    memory_delta = (
        case_features["complexity"] * 0.15
        + cond["analytical"] * 0.03
        - case_features["prosocial"] * 0.04
        + (_seeded(agent.id * 17 + 51) - 0.5) * 0.04
    )

    return {
        "cognitive_load": calibrate(float(base["cognitive_load"]), cognitive_delta),
        "emotional_agitation": calibrate(float(base["emotional_agitation"]), emotional_delta),
        "defensive_posture": calibrate(float(base["defensive_posture"]), defensive_delta, 0.22),
        "working_memory_strain": calibrate(float(base["working_memory_strain"]), memory_delta),
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

    return {
        "prefrontal_cortex": _clamp(0.35 + bsv["working_memory_strain"] * 0.45 + analytic_bias),
        "amygdala": _clamp(0.18 + bsv["emotional_agitation"] * 0.5 + bsv["defensive_posture"] * 0.22),
        "insula": _clamp(0.2 + bsv["defensive_posture"] * 0.55 + novelty * 0.4),
        "hippocampus": _clamp(0.22 + (1 - bsv["working_memory_strain"]) * 0.24 + service_bias),
        "anterior_cingulate": _clamp(0.25 + bsv["cognitive_load"] * 0.32 + (0.5 - resonance) * 0.18),
        "temporoparietal_junction": _clamp(0.24 + social_bias + service_bias * 0.45),
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


def _signal_label(signal: SignalType) -> str:
    return signal.replace("_", " ")


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
    if signal_text in {"cognitive_overload", "defensive_reactance", "empathic_resonance", "memory_alignment", "social_proof"}:
        signal = signal_text  # type: ignore[assignment]
    return _sentences(thinking), action, _clamp(confidence), signal


def _signal_summary(signal: SignalType, state: str, regions: dict[str, float]) -> str:
    if signal == "defensive_reactance":
        return f"Insula {regions['insula']:.2f} and amygdala {regions['amygdala']:.2f} are dominant, so the content is processed as threat and lands in {state}."
    if signal == "cognitive_overload":
        return f"Prefrontal cortex {regions['prefrontal_cortex']:.2f} and ACC {regions['anterior_cingulate']:.2f} signal overload, so the content feels effortful and resolves to {state}."
    if signal == "social_proof":
        return f"TPJ {regions['temporoparietal_junction']:.2f} is elevated and nearby resonance is favorable, so social proof shifts this agent toward {state}."
    if signal == "memory_alignment":
        return f"Hippocampus {regions['hippocampus']:.2f} is comparatively high, suggesting the message maps to familiar priors and settles at {state}."
    return f"Empathic and reflective regions stay balanced, leaving the agent relatively open and ending at {state}."


def _role_cohort(role: str) -> str:
    lowered = role.lower()
    if any(token in lowered for token in ("analyst", "engineer", "research")):
        return "Analytical professionals"
    if any(token in lowered for token in ("educator", "healthcare", "first responder")):
        return "Public-service practitioners"
    if any(token in lowered for token in ("organizer", "policy", "journalist")):
        return "Civic communicators"
    return "General community actors"


def _intervention_hint(signal: SignalType) -> str:
    library = INTERVENTION_LIBRARY[signal]
    return f"{library['recommended_messenger']} via {library['recommended_channel']}"


async def _run_agent_reasoning(
    httpx_client: httpx.AsyncClient,
    *,
    agent: _Virt,
    analysis_text: str,
    domain: str,
    case_goal: str,
    bsv: BSV,
    supportive_neighbors: int,
    total_neighbors: int,
    resonance: float,
    regions: dict[str, float],
    claim_diagnostics: dict[str, float | str],
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    signal = _dominant_signal(bsv, regions, supportive_neighbors)

    async with semaphore:
        try:
            raw = await call_k2_think(
                httpx_client,
                name=agent.name,
                role=f"{agent.role} in {DOMAIN_CONTEXT.get(domain, domain)}",
                bsv=bsv,
                adopted_neighbor_count=supportive_neighbors,
                total_neighbors_in_radius=total_neighbors,
                catalyst_text=(
                    f"{analysis_text}\n"
                    f"Case goal: {case_goal}\n"
                    f"Context: target domain={DOMAIN_CONTEXT.get(domain, domain)}; "
                    f"dominant mechanism={_signal_label(signal)}; local resonance={resonance:.2f}."
                ),
                claim_credibility=float(claim_diagnostics["credibility"]),
                claim_risk=str(claim_diagnostics["risk_label"]),
            )
        except Exception:
            raw = (
                "<think>Upstream K2 failure; using local fallback from the agent neural profile and neighborhood context.</think>"
                f"<action>{'Rejected' if signal in ('defensive_reactance', 'cognitive_overload') else 'Adopted'}</action>"
                f"<confidence>{0.62 if signal in ('defensive_reactance', 'cognitive_overload') else 0.57:.2f}</confidence>"
                f"<signal>{signal}</signal>"
            )

    reasoning, action, confidence, parsed_signal = _parse_k2_output(raw, signal)
    support_ratio = 0.0 if total_neighbors == 0 else supportive_neighbors / max(1, total_neighbors)
    claim_credibility = float(claim_diagnostics["credibility"])
    claim_harm = float(claim_diagnostics["harm"])
    adoption_score = _clamp(
        claim_credibility * 0.36
        + support_ratio * 0.18
        + resonance * 0.10
        + (1.0 - bsv["defensive_posture"]) * 0.13
        + (1.0 - bsv["cognitive_load"]) * 0.10
        + (0.05 if parsed_signal in {"memory_alignment", "empathic_resonance"} else 0.0)
        + (0.04 if parsed_signal == "social_proof" else 0.0)
        - claim_harm * 0.22
        - bsv["emotional_agitation"] * 0.07
    )

    if claim_credibility < 0.24 and support_ratio < 0.45:
        state = "rejected"
    elif action == "adopted" and adoption_score >= 0.61:
        state = "adopted"
    elif adoption_score <= 0.42 or action == "rejected":
        state = "rejected"
    else:
        state = "neutral"

    confidence = _clamp((confidence * 0.58) + (abs(adoption_score - 0.5) * 2.0 * 0.22) + (claim_credibility * 0.08), 0.18, 0.82)

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
        "agent_insight": {
            "vulnerability": f"Most sensitive to {_signal_label(parsed_signal)} dynamics.",
            "cause_of_state": reasoning[0] if reasoning else _signal_summary(parsed_signal, state, regions),
            "best_intervention": _intervention_hint(parsed_signal),
        },
    }


def _cluster_key(city_id: str, latitude: float, longitude: float) -> tuple[str, str]:
    city = get_city(city_id)
    vertical = "North" if latitude >= city.latitude else "South"
    horizontal = "East" if longitude >= city.longitude else "West"
    return f"{vertical}{horizontal}", f"{vertical} {horizontal} corridor"


def _build_hotspots(city_id: str, agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    adopted = [a for a in agents if a["belief_state"] == "adopted"]
    if not adopted:
        return []

    buckets: dict[str, dict[str, Any]] = {}
    for agent in adopted:
        key, label = _cluster_key(city_id, agent["latitude"], agent["longitude"])
        bucket = buckets.setdefault(key, {"id": key.lower(), "label": label, "area": label, "count": 0, "lat_sum": 0.0, "lng_sum": 0.0, "share_sum": 0.0})
        bucket["count"] += 1
        bucket["lat_sum"] += agent["latitude"]
        bucket["lng_sum"] += agent["longitude"]
        bucket["share_sum"] += 1.0 / len(adopted)

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


def _extract_claims(analysis_text: str) -> list[dict[str, Any]]:
    sentences = [sentence.strip(" \"'") for sentence in re.split(r"(?<=[.!?])\s+", analysis_text) if sentence.strip()]
    claims = []
    for index, sentence in enumerate(sentences[:4], start=1):
        claims.append({
            "id": f"claim-{index}",
            "text": sentence[:220],
            "risk": "High" if any(word in sentence.lower() for word in ("maga", "look down", "fair or not", "community", "good for you", "miracle cure", "cures")) else "Moderate",
        })
    return claims


def _extract_themes(analysis_text: str) -> list[str]:
    lowered = analysis_text.lower()
    themes = [label for label, keywords in THEME_KEYWORDS.items() if any(keyword in lowered for keyword in keywords)]
    return themes[:5] or ["community identity", "trust erosion", "narrative framing"]


def _build_segment_buckets(agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    total = max(1, len(agents))
    for agent in agents:
        key = (_role_cohort(agent["role"]), agent["dominant_signal"])
        bucket = buckets.setdefault(
            key,
            {
                "segment": key[0],
                "driver": key[1],
                "count": 0,
                "rejected": 0,
                "adopted": 0,
                "avg_confidence": 0.0,
            },
        )
        bucket["count"] += 1
        bucket["rejected"] += 1 if agent["belief_state"] == "rejected" else 0
        bucket["adopted"] += 1 if agent["belief_state"] == "adopted" else 0
        bucket["avg_confidence"] += float(agent["k2_decision_confidence"])

    out = []
    for bucket in buckets.values():
        count = bucket["count"]
        avg_confidence = bucket["avg_confidence"] / max(1, count)
        out.append({
            "label": bucket["segment"],
            "dominant_driver": bucket["driver"],
            "share": round(count / total, 3),
            "risk_level": "High" if bucket["adopted"] / max(1, count) > 0.45 else "Moderate",
            "why_vulnerable": f"{bucket['segment']} are more likely to internalize the claim through {_signal_label(bucket['driver'])}, with mean decision confidence {avg_confidence:.2f}.",
            "recommended_intervention_focus": _intervention_hint(bucket["driver"]),
        })
    return sorted(out, key=lambda item: (item["risk_level"] == "High", item["share"]), reverse=True)


def _build_belief_pathways(agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = max(1, len(agents))
    counts: dict[SignalType, int] = {
        "defensive_reactance": 0,
        "cognitive_overload": 0,
        "social_proof": 0,
        "memory_alignment": 0,
        "empathic_resonance": 0,
    }
    for agent in agents:
        counts[agent["dominant_signal"]] += 1
    return [
        {
            "id": signal,
            "label": _signal_label(signal).title(),
            "share": round(count / total, 3),
            "description": f"{count} agents are primarily driven by {_signal_label(signal)}.",
        }
        for signal, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
        if count > 0
    ]


def _build_mechanism_summary(agents: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    total = max(1, len(agents))
    pathways = _build_belief_pathways(agents)
    drivers = [
        {
            "signal": pathway["id"],
            "share": pathway["share"],
            "description": pathway["description"],
        }
        for pathway in pathways[:4]
    ]
    top = pathways[0]["label"] if pathways else "Mixed drivers"
    summary = f"The dominant mechanism driving claim uptake in this case is {top.lower()}, affecting about {round((pathways[0]['share'] if pathways else 0) * 100)}% of the modeled population."
    return drivers, summary


def _build_intervention_playbook(
    *,
    domain: str,
    case_goal: str,
    themes: list[str],
    segments: list[dict[str, Any]],
    mechanisms: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    playbook: list[dict[str, Any]] = []
    top_claim = claims[0]["text"] if claims else "the core misinformation narrative"
    for index, segment in enumerate(segments[:4], start=1):
        signal = segment["dominant_driver"]
        library = INTERVENTION_LIBRARY[signal]
        playbook.append(
            {
                "id": f"intervention-{index}",
                "title": f"{segment['label']}: counter {_signal_label(signal)}",
                "goal": case_goal,
                "target_audience": segment["label"],
                "mechanism_addressed": _signal_label(signal),
                "recommended_channel": library["recommended_channel"],
                "recommended_messenger": library["recommended_messenger"],
                "message_strategy": library["message_strategy"],
                "time_horizon": library["time_horizon"],
                "expected_effect": library["expected_effect"],
                "confidence": 0.72 if segment["risk_level"] == "High" else 0.64,
                "why_this_should_work": (
                    f"This segment is disproportionately driven by {_signal_label(signal)}. "
                    f"Responding through {library['recommended_messenger']} should reduce the appeal of the claim '{top_claim[:120]}'."
                ),
                "supporting_evidence": [
                    f"Theme alignment: {', '.join(themes[:3])}",
                    f"Segment rationale: {segment['why_vulnerable']}",
                    f"Domain context: {DOMAIN_CONTEXT.get(domain, domain)}",
                ],
            }
        )
    if not playbook and mechanisms:
        signal = mechanisms[0]["signal"]
        library = INTERVENTION_LIBRARY[signal]
        playbook.append(
            {
                "id": "intervention-1",
                "title": f"General intervention for {_signal_label(signal)}",
                "goal": case_goal,
                "target_audience": "Cross-segment audiences",
                "mechanism_addressed": _signal_label(signal),
                "recommended_channel": library["recommended_channel"],
                "recommended_messenger": library["recommended_messenger"],
                "message_strategy": library["message_strategy"],
                "time_horizon": library["time_horizon"],
                "expected_effect": library["expected_effect"],
                "confidence": 0.6,
                "why_this_should_work": "The model shows this mechanism dominates the current case.",
                "supporting_evidence": [f"Top mechanism: {_signal_label(signal)}"],
            }
        )
    return playbook


def _build_confidence_notes(agents: list[dict[str, Any]], source_warning: str | None, source_excerpt: str | None) -> list[str]:
    avg_conf = sum(float(agent["k2_decision_confidence"]) for agent in agents) / max(1, len(agents))
    fidelity, fidelity_notes = _model_fidelity_factor(source_excerpt)
    notes = [f"Average modeled decision confidence is {avg_conf:.2f}.", f"Pipeline fidelity estimate is {fidelity:.2f}."]
    if source_excerpt:
        notes.append("Source context was incorporated into the analysis text.")
    if source_warning:
        notes.append(source_warning)
    notes.extend(fidelity_notes)
    if avg_conf < 0.62 or fidelity < 0.62:
        notes.append("Confidence is limited; recommend manual review before operationalizing interventions.")
    return notes


def _risk_level(score: int) -> str:
    if score >= 72:
        return "Low"
    if score >= 48:
        return "Moderate"
    return "High"


def _build_workspace_payload(
    *,
    city_id: str,
    domain: str,
    case_goal: str,
    evidence: dict[str, Any],
    analysis_text: str,
    source_excerpt: str | None,
    source_warning: str | None,
    agents: list[dict[str, Any]],
    claim_diagnostics: dict[str, float | str],
) -> dict[str, Any]:
    total = len(agents)
    adopted = sum(1 for agent in agents if agent["belief_state"] == "adopted")
    rejected = sum(1 for agent in agents if agent["belief_state"] == "rejected")
    neutral = total - adopted - rejected
    avg_load = sum(agent["tribe_neurological_metrics"]["cognitive_load"] for agent in agents) / max(1, total)
    avg_defense = sum(agent["tribe_neurological_metrics"]["defensive_activation"] for agent in agents) / max(1, total)
    raw_avg_confidence = sum(agent["k2_decision_confidence"] for agent in agents) / max(1, total)
    fidelity_factor, _ = _model_fidelity_factor(source_excerpt)
    avg_confidence = round(_clamp(raw_avg_confidence * (0.68 + fidelity_factor * 0.32), 0.18, 0.84), 3)
    misinfo_risk_score = round(
        _clamp(
            (adopted / max(1, total)) * 0.55
            + float(claim_diagnostics["harm"]) * 0.25
            + (1.0 - float(claim_diagnostics["credibility"])) * 0.20,
            0.0,
            1.0,
        )
        * 100
    )
    spread_risk = "High" if misinfo_risk_score >= 70 else "Moderate" if misinfo_risk_score >= 40 else "Low"
    hotspots = _build_hotspots(city_id, agents)
    claims = _extract_claims(analysis_text)
    themes = _extract_themes(analysis_text)
    target_segments = _build_segment_buckets(agents)
    dominant_drivers, mechanism_summary = _build_mechanism_summary(agents)
    intervention_playbook = _build_intervention_playbook(
        domain=domain,
        case_goal=case_goal,
        themes=themes,
        segments=target_segments,
        mechanisms=dominant_drivers,
        claims=claims,
    )
    confidence_notes = _build_confidence_notes(agents, source_warning, source_excerpt)
    city = get_city(city_id)

    evidence_trace = {
        "original_text": evidence.get("text_input") or "",
        "transcript": evidence.get("transcript"),
        "source_url": evidence.get("source_url"),
        "source_excerpt": source_excerpt,
        "analysis_text": analysis_text,
        "speaker_context": evidence.get("speaker_context"),
        "claims": claims,
        "themes": themes,
        "provenance": {
            "source_type": (evidence.get("audio_input") or {}).get("source_type") or ("url_plus_text" if evidence.get("source_url") else "text"),
            "audio_input": evidence.get("audio_input"),
            "transcript_used": bool(evidence.get("transcript")),
            "analysis_text_source": "edited_analysis_text" if evidence.get("edited_analysis_text") else "transcript" if evidence.get("transcript") else "text_input",
        },
        "warnings": [note for note in [source_warning] if note],
    }

    spread_model = {
        "risk_score": misinfo_risk_score,
        "spread_risk": spread_risk,
        "belief_adoption_rate": round(adopted / max(1, total) * 100),
        "claim_rejection_rate": round(rejected / max(1, total) * 100),
        "scientific_credibility": round(float(claim_diagnostics["credibility"]) * 100),
        "population_reached": round((adopted + rejected) / max(1, total) * 100),
        "avg_cognitive_load": round(avg_load, 3),
        "avg_defensive_activation": round(avg_defense, 3),
        "high_risk_segments": target_segments[:4],
        "belief_adoption_pathways": _build_belief_pathways(agents),
        "hotspots": hotspots,
        "network_summary": f"{adopted} agents are likely to adopt the claim, {rejected} are likely to reject it, and {neutral} remain undecided across the {city.label} simulation.",
        "core_story": (
            f"Estimated scientific credibility is {round(float(claim_diagnostics['credibility']) * 100)}%, "
            f"while modeled claim adoption is {round(adopted / max(1, total) * 100)}%."
        ),
    }

    mechanisms = {
        "mechanism_summary": mechanism_summary,
        "dominant_cognitive_drivers": dominant_drivers,
        "target_segments": target_segments[:5],
        "evidence_links": [
            {"type": "claim", "label": claim["text"], "risk": claim["risk"]}
            for claim in claims[:3]
        ],
        "confidence_notes": confidence_notes,
    }

    case_summary = {
        "title": f"{city.label} misinformation case",
        "goal": case_goal,
        "domain": domain,
        "target_region": city.label,
        "spread_risk": spread_risk,
        "overall_confidence": round(avg_confidence, 3),
        "key_finding": f"{round(adopted / max(1, total) * 100)}% of the modeled population is likely to accept the claim despite a {round(float(claim_diagnostics['credibility']) * 100)}% credibility estimate. {mechanism_summary}",
        "recommended_next_step": intervention_playbook[0]["title"] if intervention_playbook else "Review the evidence trace and refine the input.",
    }

    return {
        "case_summary": case_summary,
        "spread_model": spread_model,
        "mechanisms": mechanisms,
        "intervention_playbook": intervention_playbook,
        "evidence_trace": evidence_trace,
        "summary": {"total": total, "adopted": adopted, "rejected": rejected, "neutral": neutral},
        "agents": agents,
        "macro_result": {
            "score": misinfo_risk_score,
            "risk_level": spread_risk,
            "insights": [
                {
                    "where": segment["label"],
                    "why": segment["why_vulnerable"],
                    "who": f"Mechanism: {segment['dominant_driver'].replace('_', ' ')}",
                }
                for segment in target_segments[:3]
            ],
            "suggested_rewrite": intervention_playbook[0]["message_strategy"] if intervention_playbook else "Reduce threat cues and increase clarity.",
            "synthetic_thoughts": [
                {
                    "agent_id": agent["id"],
                    "text": agent["k2_reasoning_trace"][0] if agent["k2_reasoning_trace"] else agent["brain_summary"],
                    "sentiment": "negative" if agent["belief_state"] == "rejected" else "positive" if agent["belief_state"] == "adopted" else "neutral",
                    "driver": _signal_label(agent["dominant_signal"]),
                }
                for agent in sorted(agents, key=lambda item: item["k2_decision_confidence"], reverse=True)[:12]
            ],
            "hotspots": hotspots,
            "summary_text": spread_model["network_summary"],
            "sentiment_mix": {"adopted": adopted, "rejected": rejected, "neutral": neutral},
            "input_summary": analysis_text[:240],
            "source_context_summary": source_excerpt[:280] if source_excerpt else None,
            "source_warning": source_warning,
        },
    }


def _build_analysis_text(evidence: dict[str, Any], source_excerpt: str | None) -> tuple[str, str]:
    text_input = (evidence.get("text_input") or "").strip()
    transcript = (evidence.get("transcript") or "").strip()
    edited = (evidence.get("edited_analysis_text") or "").strip()
    speaker_context = (evidence.get("speaker_context") or "").strip()

    canonical = edited or transcript or text_input
    if source_excerpt:
        canonical = f"{canonical}\n\nSource excerpt:\n{source_excerpt}".strip()
    if speaker_context:
        canonical = f"{canonical}\n\nSpeaker context: {speaker_context}".strip()
    return canonical, canonical[:240]


async def run_simulation_http(
    *,
    city_id: str,
    domain: str,
    case_goal: str,
    evidence: dict[str, Any],
    message_complexity: float,
) -> dict[str, object]:
    population = _build_virtual_population(city_id, settings.simulate_population_size)

    async with httpx.AsyncClient() as httpx_client:
        source_excerpt, source_warning = await _fetch_source_context(httpx_client, evidence.get("source_url"))
        analysis_text, _ = _build_analysis_text(evidence, source_excerpt)
        case_features = _case_feature_vector(analysis_text, case_goal, domain, message_complexity)
        claim_diagnostics = _claim_diagnostics(analysis_text, domain, source_excerpt)
        batch_agents = [{"id": agent.id, "role": agent.role, "latitude": agent.lat, "longitude": agent.lng} for agent in population]
        tribe_results = await call_tribe_modal_batch(httpx_client, analysis_text, batch_agents)

        noisy_regions = [
            _Region(
                agent_id=agent.id,
                latitude=agent.lat,
                longitude=agent.lng,
                bsv=_apply_lfcm_calibration(
                    tribe_results.get(
                        str(agent.id),
                        {
                            "cognitive_load": 0.5,
                            "emotional_agitation": 0.5,
                            "defensive_posture": 0.5,
                            "working_memory_strain": 0.5,
                        },
                    ),
                    agent=agent,
                    city_id=city_id,
                    case_features=case_features,
                    message_complexity=message_complexity,
                ),
            )
            for agent in population
        ]

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
                    analysis_text=analysis_text,
                    domain=domain,
                    case_goal=case_goal,
                    bsv=adjusted_bsv,
                    supportive_neighbors=supportive_neighbors,
                    total_neighbors=total_neighbors,
                    resonance=resonance,
                    regions=regions,
                    claim_diagnostics=claim_diagnostics,
                    semaphore=semaphore,
                )
            )

        agents = list(await asyncio.gather(*tasks))
        agents.sort(key=lambda agent: agent["id"])
        payload = _build_workspace_payload(
            city_id=city_id,
            domain=domain,
            case_goal=case_goal,
            evidence=evidence,
            analysis_text=analysis_text,
            source_excerpt=source_excerpt,
            source_warning=source_warning,
            agents=agents,
            claim_diagnostics=claim_diagnostics,
        )

        payload.update(
            {
                "city_id": city_id,
                "domain": domain,
                "case_goal": case_goal,
                "effective_catalyst_text": analysis_text,
            }
        )
        return payload
