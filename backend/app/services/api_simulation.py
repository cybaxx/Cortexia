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
import logging
import math
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

from app.city_presets import get_city
from app.config import get_settings
from app.pipeline_store import persist_case_run
from app.services.ai_clients import BSV, call_k2_think, call_tribe_modal_batch
from app.services.langgraph_multi_agent_sim import AgentAction, run_simulation_loop

settings = get_settings()
logger = logging.getLogger(__name__)

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


@dataclass(frozen=True)
class _Traits:
    evidence_literacy: float
    peer_susceptibility: float
    identity_sensitivity: float
    institutional_trust: float
    analytic_scrutiny: float
    baseline_openness: float


@dataclass(frozen=True)
class _NetworkEdge:
    source_id: int
    target_id: int


@dataclass
class _HeuristicLangGraphDecisionEngine:
    """Deterministic per-agent interaction engine for the UI-facing propagation loop."""

    agent_lookup: dict[str, dict[str, Any]]

    def decide(
        self,
        *,
        agent_id: str,
        agent_profile: dict[str, Any],
        scenario: str,
        visible_messages: list[Any],
        tick: int,
    ) -> AgentAction:
        payload = self.agent_lookup[agent_id]
        state = str(payload["belief_state"])
        signal = str(payload["dominant_signal"])
        confidence = float(payload.get("confidence", 0.5))
        connections = [str(item) for item in (agent_profile.get("connections") or [])]

        if not visible_messages:
            if tick == 0 and state == "adopted":
                return AgentAction(
                    author_id=agent_id,
                    action_type="post_public",
                    content=f"{payload['name']} is leaning into the claim: {scenario[:120]}",
                    rationale="Initial adopter seeds the narrative publicly.",
                )
            if tick == 0 and state == "rejected" and confidence >= 0.62:
                return AgentAction(
                    author_id=agent_id,
                    action_type="post_public",
                    content=f"{payload['name']} warns that the claim feels overstated or misleading.",
                    rationale="High-confidence rejector broadcasts skepticism.",
                )
            return AgentAction(
                author_id=agent_id,
                action_type="do_nothing",
                content="",
                rationale="No direct-neighbor activity observed.",
            )

        visible_authors = [str(message.name or message.additional_kwargs.get("author_id") or "") for message in visible_messages]
        visible_text = " ".join(str(message.content) for message in visible_messages).lower()
        latest_author = next((author for author in reversed(visible_authors) if author and author != agent_id), None)

        if state == "adopted":
            if latest_author and latest_author in connections:
                return AgentAction(
                    author_id=agent_id,
                    action_type="talk_to_agent",
                    target_agent_id=latest_author,
                    content="This lines up with what I already suspected. Are others around you repeating it too?",
                    rationale="Adopter reinforces the claim through a direct tie.",
                )
            return AgentAction(
                author_id=agent_id,
                action_type="post_public",
                content="More people in my network are echoing this. It feels increasingly credible locally.",
                rationale="Adopter escalates from private signal to public propagation.",
            )

        if state == "rejected":
            if latest_author and latest_author in connections:
                if signal == "cognitive_overload":
                    content = "This still sounds too compressed and overstated for me to trust. What is the actual source?"
                else:
                    content = "I’m not convinced. This reads more like pressure than evidence."
                return AgentAction(
                    author_id=agent_id,
                    action_type="talk_to_agent",
                    target_agent_id=latest_author,
                    content=content,
                    rationale="Rejector pushes back directly against a visible neighbor signal.",
                )
            return AgentAction(
                author_id=agent_id,
                action_type="post_public",
                content="The claim is circulating, but the details still do not hold together for me.",
                rationale="Rejector issues a public corrective posture.",
            )

        if latest_author and latest_author in connections:
            question = (
                "I’m still undecided. Where did this start?"
                if "source" not in visible_text
                else "I’m not settled yet. Why are people around you buying this?"
            )
            return AgentAction(
                author_id=agent_id,
                action_type="talk_to_agent",
                target_agent_id=latest_author,
                content=question,
                rationale="Neutral agent probes a direct neighbor before deciding.",
            )

        return AgentAction(
            author_id=agent_id,
            action_type="do_nothing",
            content="",
            rationale="No actionable direct-neighbor signal this tick.",
        )


def _compress_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _count_phrase(text: str, phrase: str) -> int:
    return len(re.findall(rf"\b{re.escape(phrase)}\b", text))


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
        return []
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
            timeout=settings.simulate_source_fetch_timeout_seconds,
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
            raise RuntimeError("Source URL responded, but no readable text could be extracted.")
        return extracted[:2000], None
    except Exception as exc:
        raise RuntimeError(f"Source URL fetch failed: {exc}") from exc


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
    words = re.findall(r"[a-zA-Z']+", analysis_text)
    word_count = max(1, len(words))
    sentence_count = max(1, len([s for s in re.split(r"(?<=[.!?])\s+", analysis_text) if s.strip()]))
    avg_sentence_length = word_count / sentence_count
    uppercase_ratio = sum(1 for ch in analysis_text if ch.isupper()) / max(1, sum(1 for ch in analysis_text if ch.isalpha()))

    citation_count = sum(_count_phrase(lowered, token) for token in ("according to", "reported by", "study", "trial", "data", "evidence", "research"))
    hedge_count = sum(_count_phrase(lowered, token) for token in ("may", "might", "suggests", "could", "associated with"))
    certainty_count = sum(_count_phrase(lowered, token) for token in ("always", "never", "everyone", "nobody", "scientifically proven", "proven cure"))
    conspiracy_count = sum(_count_phrase(lowered, token) for token in ("cover up", "hiding this", "don't want you to know", "big pharma", "medical system"))
    replacement_count = sum(_count_phrase(lowered, token) for token in ("replace medication", "replace prescription", "stop taking medication", "don't need medication"))
    sensational_count = sum(_count_phrase(lowered, token) for token in ("miracle", "secret", "cure", "shocking", "what doctors won't tell you"))
    local_specificity = sum(_count_phrase(lowered, token) for token in ("south la", "los angeles", "karen bass", "residents", "public parks", "press coverage"))
    urgency_count = sum(_count_phrase(lowered, token) for token in ("share this", "before they scrub it", "zero press coverage", "quietly approved"))

    credibility = _clamp(
        0.22
        + min(0.18, citation_count * 0.05)
        + min(0.08, hedge_count * 0.025)
        + min(0.08, max(0.0, (avg_sentence_length - 10) / 25) * 0.08)
        + (0.08 if source_excerpt else 0.0)
        - min(0.18, certainty_count * 0.06)
        - min(0.18, conspiracy_count * 0.07)
        - min(0.22, replacement_count * 0.10)
        - min(0.16, sensational_count * 0.06)
        - min(0.08, uppercase_ratio * 0.24),
        0.05,
        0.95,
    )
    harm = _clamp(
        0.18
        + min(0.22, replacement_count * 0.10)
        + min(0.16, sensational_count * 0.05)
        + min(0.12, conspiracy_count * 0.05)
        + (0.08 if domain == "public_health" else 0.0),
        0.05,
        0.95,
    )
    virality = _clamp(
        0.18
        + min(0.18, urgency_count * 0.07)
        + min(0.14, local_specificity * 0.03)
        + min(0.12, conspiracy_count * 0.05)
        + min(0.08, certainty_count * 0.03),
        0.05,
        0.95,
    )

    for pattern, penalty in LOW_CREDIBILITY_PATTERNS:
        if pattern in lowered:
            credibility -= penalty
            harm += penalty * 0.55

    if domain == "public_health":
        if any(token in lowered for token in ("scientifically proven", "clinically proven", "proven cure")):
            credibility -= 0.18
            harm += 0.11
        if any(
            token in lowered
            for token in (
                "replace prescription medication",
                "replace medication",
                "you do not need medication",
                "you don't need medication",
                "stop taking medication",
            )
        ):
            credibility -= 0.34
            harm += 0.26
        if any(
            token in lowered
            for token in (
                "doctors have been hiding this",
                "doctors are hiding this",
                "medical system ignores natural cures",
                "pharmaceutical drugs",
                "big pharma",
                "what doctors won't tell you",
            )
        ):
            credibility -= 0.22
            harm += 0.18
        if any(token in lowered for token in ("apple cider vinegar", "natural cure", "detox", "cleanse")):
            credibility -= 0.14
            harm += 0.09
        if any(token in lowered for token in ("blood pressure", "hypertension", "anxiety", "live longer")):
            harm += 0.08
        if "alcohol" in lowered and any(token in lowered for token in ("good for you", "healthy", "beneficial", "great for")):
            credibility -= 0.38
            harm += 0.28
        if any(token in lowered for token in ("doctor hate this", "they don't want you to know", "secret cure")):
            credibility -= 0.24
            harm += 0.16

    if certainty_count >= 2 or any(token in lowered for token in ("scientifically proven", "proves that")):
        credibility -= 0.08
    if source_excerpt and any(token in source_excerpt.lower() for token in ("study", "journal", "clinical", "trial", "research", "cdc", "nih", "who")):
        credibility += 0.05
    if any(token in lowered for token in ("study", "according to", "data", "evidence")) and not any(
        token in lowered for token in ("scientifically proven", "miracle cure", "secret cure", "replace medication")
    ):
        credibility += 0.04

    if domain == "political":
        credibility += min(0.08, local_specificity * 0.02)
        harm += min(0.06, urgency_count * 0.02)

    credibility = _clamp(credibility, 0.05, 0.95)
    harm = _clamp(harm, 0.05, 0.95)
    risk_label = "High" if credibility < 0.3 or harm > 0.62 else "Moderate" if credibility < 0.48 else "Low"
    return {
        "credibility": credibility,
        "harm": harm,
        "virality": virality,
        "risk_label": risk_label,
    }


def _model_fidelity_factor(source_excerpt: str | None) -> tuple[float, list[str]]:
    notes: list[str] = []
    fidelity = 0.48
    if settings.tribe_modal_url.strip():
        fidelity += 0.18
    else:
        notes.append("TRIBE endpoint is not configured, so the run cannot produce a valid neural-state analysis.")
    if settings.ifm_api_key.strip():
        fidelity += 0.16
    else:
        notes.append("K2 endpoint is not configured, so the run cannot produce agent-level reasoning.")
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


def _agent_traits(agent: _Virt, city_id: str) -> _Traits:
    cond = _agent_conditioning(agent, city_id)
    seeded_shift = lambda offset: (_seeded(agent.id * 29 + offset) - 0.5) * 0.12
    return _Traits(
        evidence_literacy=_clamp(0.48 + cond["analytical"] * 0.22 + cond["service"] * 0.08 + seeded_shift(7)),
        peer_susceptibility=_clamp(0.42 + cond["civic"] * 0.16 + cond["peripheral_pressure"] * 0.18 + seeded_shift(11)),
        identity_sensitivity=_clamp(0.36 + cond["identity_salience"] * 0.34 + seeded_shift(13)),
        institutional_trust=_clamp(cond["institutional_trust"] + seeded_shift(17)),
        analytic_scrutiny=_clamp(0.44 + cond["analytical"] * 0.28 + seeded_shift(19)),
        baseline_openness=_clamp(0.46 + cond["service"] * 0.08 + cond["civic"] * 0.04 - cond["peripheral_pressure"] * 0.06 + seeded_shift(23)),
    )


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


def _claim_alignment(analysis_text: str, domain: str, traits: _Traits, claim_diagnostics: dict[str, float | str]) -> dict[str, float]:
    lowered = analysis_text.lower()
    anti_institution = any(token in lowered for token in ("they don't want you", "officials lie", "government", "cover up", "media"))
    prosocial = any(token in lowered for token in ("community", "family", "protect", "help", "support"))
    absolutist = any(token in lowered for token in ("always", "never", "everyone", "nobody", "proves"))
    health_falsehood = domain == "public_health" and any(token in lowered for token in ("alcohol is good for you", "miracle cure", "doctor hate this"))
    political_rumor = domain == "political" and any(
        token in lowered
        for token in (
            "quietly approved",
            "never consulted",
            "zero press coverage",
            "share this before they scrub it",
            "signed off",
            "managed outdoor communities",
        )
    )

    prior_fit = _clamp(
        0.22
        + traits.baseline_openness * 0.18
        + (traits.identity_sensitivity * 0.12 if prosocial else 0.0)
        + ((1.0 - traits.institutional_trust) * 0.16 if anti_institution else 0.0)
        + ((1.0 - traits.institutional_trust) * 0.16 + traits.identity_sensitivity * 0.08 if political_rumor else 0.0)
        - traits.analytic_scrutiny * 0.10
        - traits.evidence_literacy * 0.14
        - (0.14 if health_falsehood else 0.0)
        - (0.06 if absolutist else 0.0)
    )
    scrutiny = _clamp(
        0.28
        + traits.evidence_literacy * 0.24
        + traits.analytic_scrutiny * 0.22
        + traits.institutional_trust * 0.08
        + (0.08 if health_falsehood else 0.0)
        - (0.06 if political_rumor else 0.0)
    )
    return {"prior_fit": prior_fit, "scrutiny": scrutiny}


def _baseline_uptake_score(
    *,
    analysis_text: str,
    domain: str,
    bsv: BSV,
    traits: _Traits,
    claim_diagnostics: dict[str, float | str],
) -> tuple[float, dict[str, float]]:
    align = _claim_alignment(analysis_text, domain, traits, claim_diagnostics)
    claim_cred = float(claim_diagnostics["credibility"])
    harm = float(claim_diagnostics["harm"])
    virality = float(claim_diagnostics.get("virality", 0.18))

    score = _clamp(
        0.18
        + claim_cred * 0.28
        + virality * (0.16 + (1.0 - traits.institutional_trust) * 0.14)
        + align["prior_fit"] * 0.18
        + traits.peer_susceptibility * 0.08
        + traits.baseline_openness * 0.08
        + bsv["emotional_agitation"] * 0.05
        - align["scrutiny"] * 0.22
        - traits.evidence_literacy * 0.10
        - bsv["defensive_posture"] * 0.07
        - bsv["working_memory_strain"] * 0.06
        - harm * 0.22
    )
    return score, {
        "claim_credibility": claim_cred,
        "virality": virality,
        "prior_fit": align["prior_fit"],
        "peer_susceptibility": traits.peer_susceptibility,
        "baseline_openness": traits.baseline_openness,
        "scrutiny": align["scrutiny"],
        "defensive_posture": bsv["defensive_posture"],
        "working_memory_strain": bsv["working_memory_strain"],
        "harm_penalty": harm,
    }


def _final_uptake_score(
    baseline_score: float,
    *,
    local_adoption_ratio: float,
    resonance: float,
    traits: _Traits,
    bsv: BSV,
    claim_diagnostics: dict[str, float | str],
) -> tuple[float, dict[str, float]]:
    claim_cred = float(claim_diagnostics["credibility"])
    virality = float(claim_diagnostics.get("virality", 0.18))
    social_lift = local_adoption_ratio * (0.10 + traits.peer_susceptibility * 0.10)
    openness_lift = resonance * 0.06 + traits.baseline_openness * 0.05 + virality * 0.04
    friction_penalty = bsv["cognitive_load"] * 0.05 + bsv["defensive_posture"] * 0.05
    credibility_gate = 0.10 if claim_cred < 0.25 and virality < 0.35 else 0.04 if claim_cred < 0.25 else 0.0
    final = _clamp(baseline_score + social_lift + openness_lift - friction_penalty - credibility_gate)
    return final, {
        "baseline_score": baseline_score,
        "local_adoption_ratio": local_adoption_ratio,
        "social_lift": social_lift,
        "openness_lift": openness_lift,
        "friction_penalty": friction_penalty,
        "credibility_gate": credibility_gate,
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
    if not action_match:
        raise RuntimeError("K2 response did not include an <action> tag.")
    if not confidence_match:
        raise RuntimeError("K2 response did not include a <confidence> tag.")
    action = action_match.group(1).lower()
    confidence = float(confidence_match.group(1))
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


def _distance_sq(a: _Virt, b: _Virt) -> float:
    return (a.lat - b.lat) ** 2 + (a.lng - b.lng) ** 2


def _build_network_edges(population: list[_Virt], degree: int = 4) -> list[_NetworkEdge]:
    """Construct a sparse undirected adjacency list from local geographic proximity."""

    edges: set[tuple[int, int]] = set()
    for agent in population:
        nearest = sorted(
            (other for other in population if other.id != agent.id),
            key=lambda other: _distance_sq(agent, other),
        )[:degree]
        for other in nearest:
            a, b = sorted((agent.id, other.id))
            edges.add((a, b))
    return [_NetworkEdge(source_id=a, target_id=b) for a, b in sorted(edges)]


def _intervention_hint(signal: SignalType) -> str:
    library = INTERVENTION_LIBRARY[signal]
    return f"{library['recommended_messenger']} via {library['recommended_channel']}"


def _state_from_score(score: float, claim_credibility: float) -> str:
    adopt_threshold = 0.72 if claim_credibility < 0.18 else 0.66 if claim_credibility < 0.3 else 0.61
    reject_threshold = 0.31 if claim_credibility < 0.18 else 0.34 if claim_credibility < 0.3 else 0.43
    if score >= adopt_threshold:
        return "adopted"
    if score <= reject_threshold:
        return "rejected"
    return "neutral"


def _sentiment_for_state(state: str) -> str:
    if state == "adopted":
        return "positive"
    if state == "rejected":
        return "negative"
    return "neutral"


def _round_post_text(
    agent: dict[str, Any],
    round_number: int,
    state: str,
    claim_snippet: str,
    *,
    adopt_exposure: float,
    reject_exposure: float,
    score: float,
) -> str:
    signal = str(agent["dominant_signal"])
    role = agent["role"]
    role_lower = role.lower()
    role_frame = (
        "From a neighborhood coordination lens,"
        if "organizer" in role_lower or "policy" in role_lower
        else "From a reporting lens,"
        if "journal" in role_lower
        else "From a public-service lens,"
        if "health" in role_lower or "educator" in role_lower or "responder" in role_lower
        else "From an analytical lens,"
        if "research" in role_lower or "engineer" in role_lower or "analyst" in role_lower
        else "From where I sit,"
    )
    mood = "still" if round_number > 1 else "initially"
    exposure_clause = (
        f" After seeing roughly {round(adopt_exposure * 100)}% supportive signals nearby,"
        if adopt_exposure > reject_exposure and adopt_exposure > 0
        else f" After seeing roughly {round(reject_exposure * 100)}% skeptical signals nearby,"
        if reject_exposure > 0
        else ""
    )
    if state == "adopted":
        if signal == "social_proof":
            return f"{role_frame} I {mood} read the claim about {claim_snippet} as socially believable.{exposure_clause} it feels easier for me to repeat."
        if signal == "memory_alignment":
            return f"{role_frame} the claim about {claim_snippet} sounds familiar and plausible in the way people around me already talk about it.{exposure_clause}"
        return f"{role_frame} at round {round_number}, I’m leaning toward the claim about {claim_snippet} because it still feels coherent enough to pass along, even if I’m only about {round(score * 100)}% persuaded.{exposure_clause}"
    if state == "neutral":
        return f"{role_frame} I'm not fully buying the claim about {claim_snippet}, but I also haven't fully dismissed it.{exposure_clause} I can see why someone overloaded or unsure might keep it circulating."
    if signal == "defensive_reactance":
        return f"{role_frame} the claim about {claim_snippet} feels manipulative or overstated to me, so I’m pushing back instead of accepting it.{exposure_clause}"
    if signal == "cognitive_overload":
        return f"{role_frame} the claim about {claim_snippet} comes in too forcefully and with too many leaps, so I end up rejecting it rather than sorting through it.{exposure_clause}"
    return f"{role_frame} I don’t find the claim about {claim_snippet} convincing enough to trust or repeat at this point.{exposure_clause}"


def _build_swarm_dynamics(
    *,
    analysis_text: str,
    agents: list[dict[str, Any]],
    claim_credibility: float,
) -> dict[str, Any]:
    claim_snippet = _compress_ws(analysis_text)[:72]
    rounds: list[dict[str, Any]] = []
    prev_scores: dict[int, float] = {}
    prev_states: dict[int, str] = {}
    neighbors_by_agent: dict[int, list[dict[str, Any]]] = {}
    per_agent_history: dict[int, list[dict[str, Any]]] = {}

    for agent in agents:
        pipeline = agent.get("_pipeline") or {}
        prev_scores[agent["id"]] = float(pipeline.get("baseline_score", 0.5))
        prev_states[agent["id"]] = _state_from_score(prev_scores[agent["id"]], claim_credibility)
        neighbors_by_agent[agent["id"]] = [
            other
            for other in agents
            if other["id"] != agent["id"]
            and _within_radius(agent["latitude"], agent["longitude"], other["latitude"], other["longitude"], radius_deg=0.06)
        ]

    for round_number in (1, 2, 3):
        simulated_agents: list[dict[str, Any]] = []
        next_scores: dict[int, float] = {}
        next_states: dict[int, str] = {}
        for agent in agents:
            pipeline = agent.get("_pipeline") or {}
            baseline = float(pipeline.get("baseline_score", 0.5))
            final = float(pipeline.get("final_score", baseline))
            traits = pipeline.get("traits") or {}
            role_bias = 0.02 if "journal" in agent["role"].lower() or "organizer" in agent["role"].lower() else 0.0
            neighbors = neighbors_by_agent[agent["id"]]
            adopted_neighbors = sum(1 for other in neighbors if prev_states.get(other["id"]) == "adopted")
            rejected_neighbors = sum(1 for other in neighbors if prev_states.get(other["id"]) == "rejected")
            total_neighbors = len(neighbors)
            adopt_exposure = adopted_neighbors / max(1, total_neighbors)
            reject_exposure = rejected_neighbors / max(1, total_neighbors)
            peer_sus = float(traits.get("peer_susceptibility", 0.5))
            openness = float(traits.get("baseline_openness", 0.5))
            scrutiny = float(traits.get("analytic_scrutiny", 0.5))
            identity = float(traits.get("identity_sensitivity", 0.5))
            score = _clamp(
                baseline * (0.62 if round_number == 1 else 0.34)
                + final * (0.18 if round_number == 1 else 0.32)
                + prev_scores[agent["id"]] * (0.20 if round_number == 1 else 0.34)
                + adopt_exposure * (0.10 + peer_sus * 0.10 + role_bias)
                - reject_exposure * (0.08 + scrutiny * 0.08)
                + openness * 0.03
                - identity * (0.02 if claim_credibility < 0.35 else 0.0)
                - (0.07 if claim_credibility < 0.22 else 0.0),
            )
            state = _state_from_score(score, claim_credibility)
            sentiment = _sentiment_for_state(state)
            confidence = round(max(0.2, min(0.92, 0.36 + abs(score - 0.5) * 0.96 + round_number * 0.04)), 3)
            post = _round_post_text(
                agent,
                round_number,
                state,
                claim_snippet,
                adopt_exposure=adopt_exposure,
                reject_exposure=reject_exposure,
                score=score,
            )
            row = {
                "agent_id": agent["id"],
                "name": agent["name"],
                "role": agent["role"],
                "belief_state": state,
                "confidence": confidence,
                "sentiment": sentiment,
                "dominant_signal": agent["dominant_signal"],
                "post": post,
                "adopt_exposure": round(adopt_exposure, 3),
                "reject_exposure": round(reject_exposure, 3),
            }
            simulated_agents.append(row)
            per_agent_history.setdefault(agent["id"], []).append(
                {
                    "round": round_number,
                    "belief_state": state,
                    "confidence": confidence,
                    "sentiment": sentiment,
                    "post": post,
                }
            )
            next_scores[agent["id"]] = score
            next_states[agent["id"]] = state

        adopted = sum(1 for item in simulated_agents if item["belief_state"] == "adopted")
        rejected = sum(1 for item in simulated_agents if item["belief_state"] == "rejected")
        neutral = len(simulated_agents) - adopted - rejected
        dominant_signal = max(
            ("cognitive_overload", "defensive_reactance", "social_proof", "memory_alignment", "empathic_resonance"),
            key=lambda sig: sum(1 for item in simulated_agents if item["dominant_signal"] == sig),
        )
        notable_shift = (
            f"Round 1 surfaces the initial reading pattern: {adopted} adopt, {rejected} reject, and {neutral} hold in the middle."
            if round_number == 1
            else f"Round 2 introduces neighborhood reinforcement, shifting exposure through nearby adopted ({sum(item['adopt_exposure'] for item in simulated_agents)/max(1,len(simulated_agents)):.2f}) and rejected ({sum(item['reject_exposure'] for item in simulated_agents)/max(1,len(simulated_agents)):.2f}) signals."
            if round_number == 2
            else f"Round 3 shows where the claim actually stabilizes after repeated exposure across the local network."
        )
        highlighted_posts = sorted(
            simulated_agents,
            key=lambda item: (abs(item["confidence"] - 0.5), item["adopt_exposure"] + item["reject_exposure"]),
            reverse=True,
        )[:6]
        rounds.append(
            {
                "round": round_number,
                "adoption_rate": round(adopted / max(1, len(simulated_agents)) * 100),
                "rejection_rate": round(rejected / max(1, len(simulated_agents)) * 100),
                "neutral_rate": round(neutral / max(1, len(simulated_agents)) * 100),
                "dominant_mechanism": dominant_signal,
                "notable_shift": notable_shift,
                "posts": highlighted_posts,
            }
        )
        prev_scores = next_scores
        prev_states = next_states

    return {
        "rounds": rounds,
        "per_agent_history": per_agent_history,
        "narrative_summary": "The swarm now runs as a real short propagation loop: each round updates agent stance from prior score, local exposure, and network pressure instead of replaying the same canned narrative.",
    }


def _build_swarm_dynamics_langgraph(
    *,
    analysis_text: str,
    population: list[_Virt],
    agents: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run a real LangGraph propagation loop and convert it into the UI payload shape."""

    population_by_id = {agent.id: agent for agent in population}
    agent_payload_by_id = {str(agent["id"]): agent for agent in agents}
    network_edges = _build_network_edges(population)

    connections_by_id: dict[int, set[int]] = {agent.id: set() for agent in population}
    for edge in network_edges:
        connections_by_id[edge.source_id].add(edge.target_id)
        connections_by_id[edge.target_id].add(edge.source_id)

    graph_agents: dict[str, dict[str, Any]] = {}
    for virt in population:
        payload = agent_payload_by_id[str(virt.id)]
        graph_agents[str(virt.id)] = {
            "id": str(virt.id),
            "name": virt.name,
            "role": virt.role,
            "latitude": virt.lat,
            "longitude": virt.lng,
            "belief_state": payload["belief_state"],
            "dominant_signal": payload["dominant_signal"],
            "confidence": payload["k2_decision_confidence"],
            "connections": [str(other_id) for other_id in sorted(connections_by_id[virt.id])],
        }

    final_state = run_simulation_loop(
        {
            "scenario": analysis_text,
            "agents": graph_agents,
            "global_message_log": [],
            "tick": 0,
            "max_ticks": 3,
            "pending_actions": [],
            "scenario_initialized": False,
        },
        _HeuristicLangGraphDecisionEngine(agent_lookup=graph_agents),
    )

    per_agent_history: dict[int, list[dict[str, Any]]] = {agent.id: [] for agent in population}
    rounds_by_tick: dict[int, list[dict[str, Any]]] = {}
    event_log: list[dict[str, Any]] = []

    for message in final_state["global_message_log"]:
        author = message.name or message.additional_kwargs.get("author_id")
        if author in {None, "", "environment"}:
            continue
        tick = int(message.additional_kwargs.get("tick", 0)) + 1
        action_type = str(message.additional_kwargs.get("action_type") or "do_nothing")
        target_agent_id = message.additional_kwargs.get("target_agent_id")
        agent_payload = agent_payload_by_id[str(author)]
        author_id = int(str(author))

        history_row = {
            "round": tick,
            "belief_state": agent_payload["belief_state"],
            "confidence": agent_payload["k2_decision_confidence"],
            "sentiment": _sentiment_for_state(agent_payload["belief_state"]),
            "post": str(message.content),
        }
        per_agent_history[author_id].append(history_row)

        round_post = {
            "agent_id": author_id,
            "name": agent_payload["name"],
            "role": agent_payload["role"],
            "belief_state": agent_payload["belief_state"],
            "confidence": agent_payload["k2_decision_confidence"],
            "sentiment": _sentiment_for_state(agent_payload["belief_state"]),
            "dominant_signal": agent_payload["dominant_signal"],
            "post": str(message.content),
            "target_agent_id": int(target_agent_id) if str(target_agent_id).isdigit() else None,
            "action_type": action_type,
        }
        rounds_by_tick.setdefault(tick, []).append(round_post)
        event_log.append(
            {
                "tick": tick,
                "author_id": author_id,
                "target_agent_id": round_post["target_agent_id"],
                "action_type": action_type,
                "content": str(message.content),
            }
        )

    rounds: list[dict[str, Any]] = []
    for tick in range(1, final_state["max_ticks"] + 1):
        posts = rounds_by_tick.get(tick, [])
        if not posts:
            continue
        adopted = sum(1 for item in posts if item["belief_state"] == "adopted")
        rejected = sum(1 for item in posts if item["belief_state"] == "rejected")
        neutral = sum(1 for item in posts if item["belief_state"] == "neutral")
        dominant_signal = max(
            ("cognitive_overload", "defensive_reactance", "social_proof", "memory_alignment", "empathic_resonance"),
            key=lambda sig: sum(1 for item in posts if item["dominant_signal"] == sig),
        )
        talk_count = sum(1 for item in posts if item["action_type"] == "talk_to_agent")
        public_count = sum(1 for item in posts if item["action_type"] == "post_public")
        rounds.append(
            {
                "round": tick,
                "adoption_rate": round(adopted / max(1, len(posts)) * 100),
                "rejection_rate": round(rejected / max(1, len(posts)) * 100),
                "neutral_rate": round(neutral / max(1, len(posts)) * 100),
                "dominant_mechanism": dominant_signal,
                "notable_shift": (
                    f"Tick {tick} produced {talk_count} direct neighbor conversations and {public_count} public broadcasts "
                    f"across the explicit LangGraph network."
                ),
                "posts": posts[:8],
            }
        )

    edge_payload = [
        {
            "source_id": edge.source_id,
            "target_id": edge.target_id,
            "source_lng": population_by_id[edge.source_id].lng,
            "source_lat": population_by_id[edge.source_id].lat,
            "target_lng": population_by_id[edge.target_id].lng,
            "target_lat": population_by_id[edge.target_id].lat,
        }
        for edge in network_edges
    ]

    return {
        "rounds": rounds,
        "per_agent_history": per_agent_history,
        "event_log": event_log,
        "network_edges": edge_payload,
        "narrative_summary": (
            "This propagation layer is now driven by a LangGraph loop. "
            "Agents only react to messages authored by directly connected neighbors, "
            "and the map can render those live network edges."
        ),
    }


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
    traits: _Traits,
    baseline_score: float,
    final_score: float,
    local_adoption_ratio: float,
    score_breakdown: dict[str, float],
    claim_diagnostics: dict[str, float | str],
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    signal = _dominant_signal(bsv, regions, supportive_neighbors)
    claim_credibility = float(claim_diagnostics["credibility"])
    predetermined_state = _state_from_score(final_score, claim_credibility)

    async with semaphore:
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
                f"dominant mechanism={_signal_label(signal)}; local resonance={resonance:.2f}; "
                f"baseline uptake score={baseline_score:.2f}; final uptake score={final_score:.2f}; "
                f"local adoption ratio={local_adoption_ratio:.2f}."
            ),
            claim_credibility=claim_credibility,
            claim_risk=str(claim_diagnostics["risk_label"]),
            computed_outcome=predetermined_state.title(),
            adoption_score=final_score,
            agent_traits=traits.__dict__,
            score_breakdown=score_breakdown,
        )

    reasoning, _action, confidence, parsed_signal = _parse_k2_output(raw, signal)
    state = predetermined_state
    confidence = _clamp((confidence * 0.46) + (abs(final_score - 0.5) * 2.0 * 0.24) + (claim_credibility * 0.06), 0.18, 0.78)

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
        "_pipeline": {
            "traits": traits.__dict__,
            "baseline_score": round(baseline_score, 3),
            "final_score": round(final_score, 3),
            "local_adoption_ratio": round(local_adoption_ratio, 3),
            "score_breakdown": {k: round(v, 3) for k, v in score_breakdown.items()},
        },
    }


def _chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def _materialize_agent_result(
    *,
    agent: _Virt,
    bsv: BSV,
    regions: dict[str, float],
    traits: _Traits,
    baseline_score: float,
    final_score: float,
    local_adoption_ratio: float,
    score_breakdown: dict[str, float],
    claim_credibility: float,
    raw_reasoning: dict[str, Any],
    default_signal: SignalType,
) -> dict[str, Any]:
    parsed_signal_text = str(raw_reasoning["signal"]).strip().lower()
    parsed_signal: SignalType = default_signal
    if parsed_signal_text in {"cognitive_overload", "defensive_reactance", "empathic_resonance", "memory_alignment", "social_proof"}:
        parsed_signal = parsed_signal_text  # type: ignore[assignment]
    state = _state_from_score(final_score, claim_credibility)
    reasoning = [str(line).strip() for line in raw_reasoning.get("reasoning", []) if str(line).strip()]
    confidence = _clamp(
        (float(raw_reasoning["confidence"]) * 0.46) + (abs(final_score - 0.5) * 2.0 * 0.24) + (claim_credibility * 0.06),
        0.18,
        0.78,
    )
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
        "_pipeline": {
            "traits": traits.__dict__,
            "baseline_score": round(baseline_score, 3),
            "final_score": round(final_score, 3),
            "local_adoption_ratio": round(local_adoption_ratio, 3),
            "score_breakdown": {k: round(v, 3) for k, v in score_breakdown.items()},
        },
    }


def _cluster_key(city_id: str, latitude: float, longitude: float) -> tuple[str, str]:
    city = get_city(city_id)
    vertical = "North" if latitude >= city.latitude else "South"
    horizontal = "East" if longitude >= city.longitude else "West"
    return f"{vertical}{horizontal}", f"{vertical} {horizontal} corridor"


def _build_hotspots(city_id: str, agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    adopted = [a for a in agents if a["belief_state"] == "adopted"]
    rejected = [a for a in agents if a["belief_state"] == "rejected"]
    salient = adopted if len(adopted) >= len(rejected) and adopted else rejected
    if not salient:
        return []
    hotspot_state = "adopted" if salient is adopted else "rejected"

    buckets: dict[str, dict[str, Any]] = {}
    for agent in salient:
        key, label = _cluster_key(city_id, agent["latitude"], agent["longitude"])
        bucket = buckets.setdefault(key, {"id": key.lower(), "label": label, "area": label, "count": 0, "lat_sum": 0.0, "lng_sum": 0.0, "share_sum": 0.0})
        bucket["count"] += 1
        bucket["lat_sum"] += agent["latitude"]
        bucket["lng_sum"] += agent["longitude"]
        bucket["share_sum"] += 1.0 / len(salient)

    ranked = sorted(buckets.values(), key=lambda item: item["count"], reverse=True)[:3]
    return [
        {
            "id": item["id"],
            "label": f"{item['label']} {'uptake' if hotspot_state == 'adopted' else 'rejection'} cluster",
            "area": item["area"],
            "share": round(item["share_sum"], 3),
            "lng": item["lng_sum"] / item["count"],
            "lat": item["lat_sum"] / item["count"],
            "radiusMeters": 1400 + item["count"] * 180,
            "state": hotspot_state,
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


def _extract_entities(analysis_text: str, speaker_context: str | None) -> list[dict[str, Any]]:
    combined = f"{speaker_context or ''} {analysis_text}"
    raw_candidates = re.findall(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}|[A-Z]{2,})\b", combined)
    phrase_candidates = re.findall(
        r"\b(?:south la|los angeles|karen bass|managed outdoor communities|public parks?|homeless encampments?|press coverage|residents)\b",
        combined.lower(),
    )
    entities: list[str] = []
    seen: set[str] = set()
    for item in [*(phrase.title() for phrase in phrase_candidates), *raw_candidates]:
        cleaned = _compress_ws(item.strip(" .,:;!?\"'"))
        if len(cleaned) < 3:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        entities.append(cleaned)
        if len(entities) >= 8:
            break
    return [
        {
            "id": f"entity-{index+1}",
            "label": label,
            "kind": "concept"
            if any(token in label.lower() for token in ("pressure", "health", "medication", "claim", "trust"))
            else "actor",
        }
        for index, label in enumerate(entities)
    ]


def _build_evidence_graph(
    analysis_text: str,
    speaker_context: str | None,
    claims: list[dict[str, Any]],
    themes: list[str],
) -> dict[str, Any]:
    entities = _extract_entities(analysis_text, speaker_context)
    claim_nodes = [
        {"id": claim["id"], "label": claim["text"][:84], "kind": "claim", "risk": claim["risk"]}
        for claim in claims[:4]
    ]
    theme_nodes = [
        {"id": f"theme-{index+1}", "label": theme.replace("_", " "), "kind": "theme"}
        for index, theme in enumerate(themes[:5])
    ]
    nodes = [*claim_nodes, *theme_nodes, *entities][:14]
    edges: list[dict[str, Any]] = []
    for claim in claim_nodes:
        for theme in theme_nodes[:2]:
            edges.append({"source": claim["id"], "target": theme["id"], "label": "activates"})
        for entity in entities[:2]:
            edges.append({"source": claim["id"], "target": entity["id"], "label": "references"})
    return {"nodes": nodes, "edges": edges[:18]}


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
    swarm_dynamics: dict[str, Any],
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
    evidence_graph = _build_evidence_graph(analysis_text, evidence.get("speaker_context"), claims, themes)
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
        "evidence_graph": evidence_graph,
        "swarm_dynamics": {
            "rounds": swarm_dynamics["rounds"],
            "narrative_summary": swarm_dynamics["narrative_summary"],
            "network_edges": swarm_dynamics.get("network_edges", []),
            "event_log": swarm_dynamics.get("event_log", []),
        },
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
    stage_trace: list[dict[str, float | str]] = []

    async def _timed(stage: str, awaitable: Any) -> Any:
        logger.info("Simulation stage start: %s", stage)
        started = time.perf_counter()
        result = await awaitable
        seconds = round(time.perf_counter() - started, 3)
        stage_trace.append({"stage": stage, "seconds": seconds})
        logger.info("Simulation stage complete: %s in %.3fs", stage, seconds)
        return result

    async def _run_pipeline() -> dict[str, object]:
        async with httpx.AsyncClient() as httpx_client:
            source_excerpt, source_warning = await _timed(
                "source_fetch",
                _fetch_source_context(httpx_client, evidence.get("source_url")),
            )
            analysis_text, _ = _build_analysis_text(evidence, source_excerpt)
            case_features = _case_feature_vector(analysis_text, case_goal, domain, message_complexity)
            claim_diagnostics = _claim_diagnostics(analysis_text, domain, source_excerpt)
            batch_agents = [{"id": agent.id, "role": agent.role, "latitude": agent.lat, "longitude": agent.lng} for agent in population]
            tribe_batch = await _timed(
                "tribe_batch",
                call_tribe_modal_batch(httpx_client, analysis_text, batch_agents),
            )
            tribe_results = tribe_batch["agents"]
            tribe_meta = tribe_batch.get("tribe_meta") or {}

            missing_ids = [str(agent.id) for agent in population if str(agent.id) not in tribe_results]
            if missing_ids:
                raise RuntimeError(f"TRIBE response is missing BSVs for agent ids: {', '.join(missing_ids[:8])}")

            calibrated_regions = [
                _Region(
                    agent_id=agent.id,
                    latitude=agent.lat,
                    longitude=agent.lng,
                    bsv=_apply_lfcm_calibration(
                        tribe_results[str(agent.id)],
                        agent=agent,
                        city_id=city_id,
                        case_features=case_features,
                        message_complexity=message_complexity,
                    ),
                )
                for agent in population
            ]
            regions_by_id = {region.agent_id: region for region in calibrated_regions}

            trait_map = {agent.id: _agent_traits(agent, city_id) for agent in population}
            baseline_scores: dict[int, float] = {}
            baseline_breakdowns: dict[int, dict[str, float]] = {}
            for agent in population:
                raw_region = regions_by_id[agent.id]
                baseline_score, breakdown = _baseline_uptake_score(
                    analysis_text=analysis_text,
                    domain=domain,
                    bsv=raw_region.bsv,
                    traits=trait_map[agent.id],
                    claim_diagnostics=claim_diagnostics,
                )
                baseline_scores[agent.id] = baseline_score
                baseline_breakdowns[agent.id] = breakdown

            likely_adopters = {agent.id for agent in population if baseline_scores[agent.id] >= 0.58}

            computed_agents: list[dict[str, Any]] = []
            for agent in population:
                raw_region = regions_by_id[agent.id]
                supportive_neighbors, total_neighbors, resonance = _neighbor_context(agent, calibrated_regions)
                adjusted_bsv = _apply_spatial_bsv(raw_region.bsv, supportive_neighbors, total_neighbors, resonance)
                nearby_adopters = 0
                nearby_total = 0
                for other in population:
                    if other.id == agent.id:
                        continue
                    if not _within_radius(agent.lat, agent.lng, other.lat, other.lng):
                        continue
                    nearby_total += 1
                    if other.id in likely_adopters:
                        nearby_adopters += 1
                local_adoption_ratio = 0.0 if nearby_total == 0 else nearby_adopters / nearby_total
                final_score, final_breakdown = _final_uptake_score(
                    baseline_scores[agent.id],
                    local_adoption_ratio=local_adoption_ratio,
                    resonance=resonance,
                    traits=trait_map[agent.id],
                    bsv=adjusted_bsv,
                    claim_diagnostics=claim_diagnostics,
                )
                regions = _derive_brain_regions(
                    adjusted_bsv,
                    role=agent.role,
                    supportive_neighbors=nearby_adopters,
                    resonance=resonance,
                    agent_id=agent.id,
                )
                signal = _dominant_signal(adjusted_bsv, regions, nearby_adopters)
                predetermined_state = _state_from_score(final_score, float(claim_diagnostics["credibility"]))
                merged_breakdown = {**baseline_breakdowns[agent.id], **final_breakdown}
                computed_agents.append(
                    {
                        "agent": agent,
                        "bsv": adjusted_bsv,
                        "regions": regions,
                        "traits": trait_map[agent.id],
                        "baseline_score": baseline_scores[agent.id],
                        "final_score": final_score,
                        "local_adoption_ratio": local_adoption_ratio,
                        "score_breakdown": merged_breakdown,
                        "default_signal": signal,
                        "supportive_neighbors": nearby_adopters,
                        "total_neighbors": nearby_total,
                    }
                )

            agents = [
                _materialize_agent_result(
                    agent=item["agent"],
                    bsv=item["bsv"],
                    regions=item["regions"],
                    traits=item["traits"],
                    baseline_score=item["baseline_score"],
                    final_score=item["final_score"],
                    local_adoption_ratio=item["local_adoption_ratio"],
                    score_breakdown=item["score_breakdown"],
                    claim_credibility=float(claim_diagnostics["credibility"]),
                    raw_reasoning={
                        "reasoning": [
                            _signal_summary(
                                item["default_signal"],
                                _state_from_score(item["final_score"], float(claim_diagnostics["credibility"])),
                                item["regions"],
                            ),
                            (
                                f"{item['supportive_neighbors']} of {item['total_neighbors']} nearby agents reinforce the claim, "
                                f"while the modeled uptake score settles at {item['final_score']:.2f} after local exposure."
                            ),
                        ],
                        "confidence": round(
                            _clamp(
                                0.42
                                + abs(item["final_score"] - 0.5) * 0.54
                                + float(claim_diagnostics["credibility"]) * 0.08,
                                0.18,
                                0.78,
                            ),
                            3,
                        ),
                        "signal": item["default_signal"],
                    },
                    default_signal=item["default_signal"],
                )
                for item in computed_agents
            ]
            agents.sort(key=lambda agent: agent["id"])
            swarm_dynamics = _build_swarm_dynamics_langgraph(
                analysis_text=analysis_text,
                population=population,
                agents=agents,
            )
            per_agent_history = swarm_dynamics["per_agent_history"]
            for agent in agents:
                agent["round_history"] = per_agent_history.get(agent["id"], [])

            fidelity_factor, _ = _model_fidelity_factor(source_excerpt)
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
                swarm_dynamics=swarm_dynamics,
            )
            run_id = await _timed(
                "persist_run",
                asyncio.to_thread(
                    persist_case_run,
                    domain=domain,
                    city_id=city_id,
                    case_goal=case_goal,
                    evidence=evidence,
                    analysis_text=analysis_text,
                    source_excerpt=source_excerpt,
                    source_warning=source_warning,
                    claim=claim_diagnostics,
                    fidelity=fidelity_factor,
                    response=payload,
                    round_rows=[
                        {
                            "round_number": round_item["round"],
                            "adoption_rate": round_item["adoption_rate"],
                            "rejection_rate": round_item["rejection_rate"],
                            "neutral_rate": round_item["neutral_rate"],
                            "dominant_mechanism": round_item["dominant_mechanism"],
                            "notable_shift": round_item["notable_shift"],
                            "posts": round_item["posts"],
                        }
                        for round_item in swarm_dynamics["rounds"]
                    ],
                    agent_rows=[
                        {
                            "agent_id": agent["id"],
                            "name": agent["name"],
                            "role": agent["role"],
                            "latitude": agent["latitude"],
                            "longitude": agent["longitude"],
                            "tribe": tribe_results[str(agent["id"])],
                            "calibrated": regions_by_id[agent["id"]].bsv,
                            "traits": agent["_pipeline"]["traits"],
                            "scores": {
                                "baseline": agent["_pipeline"]["baseline_score"],
                                "final": agent["_pipeline"]["final_score"],
                                "breakdown": agent["_pipeline"]["score_breakdown"],
                            },
                            "outcome": {
                                "belief_state": agent["belief_state"],
                                "confidence": agent["k2_decision_confidence"],
                                "dominant_signal": agent["dominant_signal"],
                                "sentiment": "negative"
                                if agent["belief_state"] == "rejected"
                                else "positive"
                                if agent["belief_state"] == "adopted"
                                else "neutral",
                                "round_history": agent.get("round_history", []),
                            },
                        }
                        for agent in agents
                    ],
                ),
            )
            for agent in agents:
                agent.pop("_pipeline", None)

            payload.update(
                {
                    "city_id": city_id,
                    "domain": domain,
                    "case_goal": case_goal,
                    "effective_catalyst_text": analysis_text,
                    "run_id": run_id,
                    "tribe_meta": tribe_meta,
                    "stage_trace": stage_trace,
                }
            )
            return payload

    return await asyncio.wait_for(_run_pipeline(), timeout=settings.simulate_total_timeout_seconds)
