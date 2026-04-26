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
from app.services.ai_clients import BSV, call_k2_batch_think, call_k2_explanation_only, call_k2_timeline_batch, call_tribe_modal_batch
from app.services.langgraph_multi_agent_sim import AgentAction, run_simulation_loop, HybridLangGraphDecisionEngine, make_chat_openai_decision_engine

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

ROI_DISPLAY_LABELS: dict[str, str] = {
    "fear_salience": "Threat and fear response",
    "reward_limbic": "Reward and opportunity detection",
    "deliberation": "Analytical thinking and rational control",
    "social_default": "Awareness of others and social pressure",
    "attention": "Uncertainty and vigilance",
    "action_motor": "Urge to act",
}

CONNECTIVITY_DISPLAY_LABELS: dict[str, str] = {
    "fear_social": "Fear ↔ social awareness",
    "fear_deliberation": "Fear ↔ analytical thinking",
    "fear_reward": "Fear ↔ reward detection",
    "reward_delib": "Reward ↔ analytical thinking",
    "reward_social": "Reward ↔ social awareness",
    "action_fear": "Action urge ↔ fear",
    "action_reward": "Action urge ↔ reward",
}


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
class _Demographics:
    age_band: str
    age_years: int
    education_level: str
    income_band: str
    housing_status: str
    language_profile: str
    community_tenure: str
    caregiving_load: str
    digital_media_habit: str


@dataclass(frozen=True)
class _Virt:
    id: int
    name: str
    role: str
    lat: float
    lng: float
    demographics: _Demographics


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
    weight: float
    compatibility: float


@dataclass
class _HeuristicLangGraphDecisionEngine:
    """Deterministic per-agent interaction engine for the UI-facing propagation loop."""

    agent_lookup: dict[str, dict[str, Any]]

    def _variant(self, agent_id: str, tick: int, options: list[str]) -> str:
        idx = int((_seeded(int(agent_id) * 31 + tick * 17) * len(options)) % max(1, len(options)))
        return options[idx]

    def _role_voice(self, role: str) -> str:
        lowered = role.lower()
        if any(token in lowered for token in ("journal",)):
            return "reporting"
        if any(token in lowered for token in ("policy", "organizer")):
            return "civic"
        if any(token in lowered for token in ("analyst", "engineer", "research")):
            return "evidence"
        if any(token in lowered for token in ("health", "educator", "responder")):
            return "public_service"
        if any(token in lowered for token in ("small business", "operations")):
            return "practical"
        return "general"

    def _traits(self, payload: dict[str, Any]) -> dict[str, float]:
        raw = payload.get("traits") or {}
        return {key: float(value) for key, value in raw.items() if isinstance(value, (int, float))}

    def _demographics(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw = payload.get("demographics") or {}
        return raw if isinstance(raw, dict) else {}

    def _connection_profile(self, agent_profile: dict[str, Any], other_id: str | None) -> dict[str, Any]:
        profiles = agent_profile.get("connection_profiles") or {}
        if other_id is None:
            return {}
        profile = profiles.get(str(other_id)) or {}
        return profile if isinstance(profile, dict) else {}

    def _neighbor_weight(self, agent_profile: dict[str, Any], other_id: str | None) -> float:
        return _clamp(float(self._connection_profile(agent_profile, other_id).get("weight", 0.42)), 0.2, 1.0)

    def _neighbor_role(self, agent_profile: dict[str, Any], other_id: str | None) -> str:
        return str(self._connection_profile(agent_profile, other_id).get("role") or "")

    def _role_requirement(self, payload: dict[str, Any], latest_neighbor_role: str | None = None) -> str:
        traits = self._traits(payload)
        demographics = self._demographics(payload)
        evidence_literacy = traits.get("evidence_literacy", 0.5)
        institutional_trust = traits.get("institutional_trust", 0.5)
        role = str(payload.get("role") or "").lower()
        neighbor_role = (latest_neighbor_role or "").lower()
        media_habit = str(demographics.get("digital_media_habit") or "").lower()
        caregiving_load = str(demographics.get("caregiving_load") or "").lower()
        if evidence_literacy >= 0.62:
            return "a source chain I can verify"
        if "group-chat" in media_habit or "public-feed" in media_habit:
            return "something stronger than a forwarded version"
        if "primary caregiver" in caregiving_load:
            return "something concrete enough to act on without second-guessing"
        if any(token in role for token in ("policy", "organizer", "analyst")) or any(
            token in neighbor_role for token in ("policy", "journal", "analyst")
        ):
            return "a traceable public record"
        if any(token in role for token in ("health", "educator", "responder")):
            return "trusted guidance I could act on"
        if institutional_trust >= 0.58:
            return "documentation that would exist if this were real"
        return "evidence that does more than repeat the claim"

    def _role_context_clause(self, payload: dict[str, Any], latest_neighbor_name: str | None, latest_neighbor_role: str | None) -> str:
        role = str(payload.get("role") or "").lower()
        demographics = self._demographics(payload)
        neighbor = latest_neighbor_name or "someone nearby"
        tenure = str(demographics.get("community_tenure") or "").lower()
        if any(token in role for token in ("policy", "organizer", "analyst")):
            return f"a city-scale claim like this should leave a public trail, and {neighbor} still has not shown one"
        if any(token in role for token in ("health", "educator", "responder")):
            return f"nothing in what {neighbor} passed along reaches the threshold for something I could responsibly repeat"
        if any(token in role for token in ("engineer", "research", "journal")):
            return f"{neighbor} is adding circulation, not verification"
        if "deeply rooted" in tenure or "long-term" in tenure:
            return f"the story still does not match what someone with long neighborhood memory would expect to see"
        if latest_neighbor_role:
            return f"hearing it through a {latest_neighbor_role.lower()} still does not make it sturdier"
        return "the message keeps expanding without getting more concrete"

    def _focus_area(self, payload: dict[str, Any]) -> str:
        role = str(payload.get("role") or "").lower()
        demographics = self._demographics(payload)
        if any(token in role for token in ("policy", "analyst", "journal", "organizer")):
            return "public record"
        if any(token in role for token in ("health", "educator", "responder")):
            return "actionability"
        if any(token in role for token in ("engineer", "research")):
            return "verification chain"
        if str(demographics.get("digital_media_habit") or "").lower() == "group-chat heavy":
            return "forwarded provenance"
        return "local plausibility"

    def _personal_anchor(self, payload: dict[str, Any]) -> str:
        demographics = self._demographics(payload)
        tenure = str(demographics.get("community_tenure") or "").lower()
        media_habit = str(demographics.get("digital_media_habit") or "").lower()
        age_band = str(demographics.get("age_band") or "").lower()
        caregiving_load = str(demographics.get("caregiving_load") or "").lower()
        language_profile = str(demographics.get("language_profile") or "").lower()
        cues: list[str] = []
        if "group-chat" in media_habit:
            cues.append("group-chat circulation alone is not enough for me to trust it")
        elif "public-feed" in media_habit:
            cues.append("feed velocity is outpacing the underlying proof")
        elif "local-news" in media_habit:
            cues.append("if this were solid, I would expect it to echo through more than neighborhood chatter")
        elif "mixed" in media_habit:
            cues.append("cross-checking across channels still is not giving this a firmer backbone")

        if "long-term" in tenure or "deeply rooted" in tenure:
            cues.append("my read is shaped by long neighborhood memory, and this still does not line up")
        elif "established" in tenure:
            cues.append("with some local memory behind me, I still expect cleaner proof than this")
        elif "recent arrival" in tenure:
            cues.append("without deeper local context, I lean harder on verifiable records than repetition")

        if "primary caregiver" in caregiving_load:
            cues.append("anything I pass along has to be actionable enough for real-world decisions")
        elif "shared caregiver" in caregiving_load:
            cues.append("I filter this through whether it would hold up under everyday family decisions")

        if language_profile and language_profile != "english-dominant":
            cues.append("the message still does not translate into a dependable, repeatable fact pattern")
        if age_band in {"18-24", "25-34"}:
            cues.append("I need more than ambient circulation before I would attach my name to it")
        elif age_band in {"55-64", "65+"}:
            cues.append("experience makes me look for durable proof, not just another retelling")

        if not cues:
            return "I still need a clearer factual backbone before I treat it as settled"

        agent_id = int(payload.get("id") or 0)
        first = cues[agent_id % len(cues)]
        if len(cues) == 1:
            return first
        second = cues[(agent_id // 3 + 1) % len(cues)]
        if second == first:
            second = cues[(agent_id + 1) % len(cues)]
        return f"{first}; {second}"

    def _pressure_word(self, state: str, weighted_bias: float, signal: str) -> str:
        if state == "adopted":
            if signal == "social_proof":
                return "normalized"
            return "plausible"
        if state == "neutral":
            return "unresolved"
        if signal == "defensive_reactance":
            return "agenda-driven"
        if weighted_bias >= 0.72:
            return "unsupported"
        return "unverified"

    def _channel_descriptor(self, payload: dict[str, Any], latest_neighbor_role: str | None) -> str:
        demographics = self._demographics(payload)
        habit = str(demographics.get("digital_media_habit") or "").lower()
        if latest_neighbor_role:
            return latest_neighbor_role.lower()
        if "group-chat" in habit:
            return "group chat"
        if "public-feed" in habit:
            return "public feed"
        if "local-news" in habit:
            return "local news"
        return "neighborhood circulation"

    def _compose_agent_statement(
        self,
        payload: dict[str, Any],
        state: str,
        tick: int,
        *,
        latest_neighbor_name: str | None,
        latest_neighbor_role: str | None,
        weighted_bias: float,
        visible_text: str,
        confidence_band: str,
        visible_count: int,
        visible_authors: list[str],
    ) -> str:
        requirement = self._role_requirement(payload, latest_neighbor_role)
        context_clause = self._role_context_clause(payload, latest_neighbor_name, latest_neighbor_role)
        demographics = self._demographics(payload)
        signal = str(payload.get("dominant_signal") or "")
        focus = self._focus_area(payload)
        channel = self._channel_descriptor(payload, latest_neighbor_role)
        anchor = self._pressure_word(state, weighted_bias, signal)
        media_habit = str(demographics.get("digital_media_habit") or "").lower()
        repeat_exposure = max(0, visible_count - len(set(visible_authors)))
        source_mentions = visible_text.count("source")
        evidence_mentions = visible_text.count("evidence")
        record_mentions = visible_text.count("record")
        personal_anchor = self._personal_anchor(payload)
        opener = (
            f"At first pass, the {focus} still looked {anchor}."
            if tick == 0
            else f"After another round through {channel}, the {focus} still looks {anchor}."
        )
        if latest_neighbor_name:
            opener = (
                f"{latest_neighbor_name} pushed the claim into view, but the {focus} still looks {anchor}."
                if tick == 0
                else f"Even after {latest_neighbor_name} circled back, the {focus} still looks {anchor}."
                if tick == 1
                else f"A third pass from {latest_neighbor_name} still leaves the {focus} looking {anchor}."
            )
        middle = (
            f"I still need {requirement}."
            if state != "adopted"
            else f"The message is clearing enough of the {focus} check for me to keep it in play."
        )
        if "group-chat" in media_habit and state != "adopted":
            middle = f"It still behaves more like a forwarded version than something anchored by dependable sourcing."
        if tick >= 2 and confidence_band == "high" and "source" in visible_text and state != "adopted":
            middle = f"More repetition is not fixing the core deficit: there is still no {requirement}."
        elif tick >= 2 and state != "adopted" and (source_mentions + evidence_mentions + record_mentions) == 0:
            middle = f"By this point I would expect at least {requirement}, and the network is still only recirculating the same claim."
        elif tick >= 1 and state != "adopted" and repeat_exposure > 0:
            middle = f"The repetition is rising faster than the verification: I still need {requirement}."
        closer = (
            f"{_upper_first(context_clause)}."
            if state != "adopted"
            else f"The channel fit and local repetition are starting to outweigh my initial hesitation."
        )
        if state != "adopted":
            if tick >= 2 and visible_count >= 2:
                closer = f"{_upper_first(context_clause)}. { _upper_first(personal_anchor) }. The loop is getting louder, but it is not getting sturdier."
            elif tick == 1 and visible_count == 1:
                closer = f"{_upper_first(context_clause)}. { _upper_first(personal_anchor) }. One more retelling still does not move it past my threshold."
            else:
                closer = f"{_upper_first(context_clause)}. { _upper_first(personal_anchor) }."
        return " ".join(part.strip() for part in (opener, middle, closer) if part.strip())

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
        confidence = float(payload.get("confidence", 0.5))
        connections = [str(item) for item in (agent_profile.get("connections") or [])]
        confidence_band = "high" if confidence >= 0.55 else "medium" if confidence >= 0.4 else "low"

        if not visible_messages:
            if tick == 0 and state == "adopted":
                return AgentAction(
                    author_id=agent_id,
                    action_type="post_public",
                    content=self._compose_agent_statement(
                        payload,
                        state,
                        tick,
                        latest_neighbor_name=None,
                        latest_neighbor_role=None,
                        weighted_bias=0.42,
                        visible_text="",
                        confidence_band=confidence_band,
                        visible_count=0,
                        visible_authors=[],
                    ),
                    rationale="Initial adopter seeds the narrative publicly.",
                )
            if tick == 0 and state == "rejected" and confidence >= 0.62:
                return AgentAction(
                    author_id=agent_id,
                    action_type="post_public",
                    content=self._compose_agent_statement(
                        payload,
                        state,
                        tick,
                        latest_neighbor_name=None,
                        latest_neighbor_role=None,
                        weighted_bias=0.42,
                        visible_text="",
                        confidence_band=confidence_band,
                        visible_count=0,
                        visible_authors=[],
                    ),
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
        latest_neighbor_name = (
            self.agent_lookup.get(str(latest_author), {}).get("name")
            if latest_author is not None
            else None
        )
        latest_neighbor_role = self._neighbor_role(agent_profile, latest_author) if latest_author else None
        latest_neighbor_weight = self._neighbor_weight(agent_profile, latest_author) if latest_author else 0.42

        if state == "adopted":
            if latest_author and latest_author in connections:
                return AgentAction(
                    author_id=agent_id,
                    action_type="talk_to_agent",
                    target_agent_id=latest_author,
                    content=self._compose_agent_statement(
                        payload,
                        state,
                        tick,
                        latest_neighbor_name=latest_neighbor_name,
                        latest_neighbor_role=latest_neighbor_role,
                        weighted_bias=latest_neighbor_weight,
                        visible_text=visible_text,
                        confidence_band=confidence_band,
                        visible_count=len(visible_messages),
                        visible_authors=visible_authors,
                    ),
                    rationale="Adopter reinforces the claim through a direct tie.",
                )
            return AgentAction(
                author_id=agent_id,
                action_type="post_public",
                content=self._compose_agent_statement(
                    payload,
                    state,
                    tick,
                    latest_neighbor_name=latest_neighbor_name,
                    latest_neighbor_role=latest_neighbor_role,
                    weighted_bias=latest_neighbor_weight,
                    visible_text=visible_text,
                    confidence_band=confidence_band,
                    visible_count=len(visible_messages),
                    visible_authors=visible_authors,
                ),
                rationale="Adopter escalates from private signal to public propagation.",
            )

        if state == "rejected":
            if latest_author and latest_author in connections:
                content = self._compose_agent_statement(
                    payload,
                    state,
                    tick,
                    latest_neighbor_name=latest_neighbor_name,
                    latest_neighbor_role=latest_neighbor_role,
                    weighted_bias=latest_neighbor_weight,
                    visible_text=visible_text,
                    confidence_band=confidence_band,
                    visible_count=len(visible_messages),
                    visible_authors=visible_authors,
                )
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
                content=self._compose_agent_statement(
                    payload,
                    state,
                    tick,
                    latest_neighbor_name=None,
                    latest_neighbor_role=None,
                    weighted_bias=0.42,
                    visible_text=visible_text,
                    confidence_band=confidence_band,
                    visible_count=len(visible_messages),
                    visible_authors=visible_authors,
                ),
                rationale="Rejector issues a public corrective posture.",
            )

        if latest_author and latest_author in connections:
            question = self._compose_agent_statement(
                payload,
                state,
                tick,
                latest_neighbor_name=latest_neighbor_name,
                latest_neighbor_role=latest_neighbor_role,
                weighted_bias=latest_neighbor_weight,
                visible_text=visible_text,
                confidence_band=confidence_band,
                visible_count=len(visible_messages),
                visible_authors=visible_authors,
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


def _upper_first(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


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


from app.population_store import fetch_population, save_population

def _build_virtual_population(city_id: str, count: int) -> list[_Virt]:
    existing_agents = fetch_population(city_id, count)
    out: list[_Virt] = []

    for item in existing_agents:
        demo_dict = item["demographics"]
        out.append(
            _Virt(
                id=item["id"],
                name=item["name"],
                role=item["role"],
                lat=item["lat"],
                lng=item["lng"],
                demographics=_Demographics(
                    age_band=demo_dict["age_band"],
                    age_years=demo_dict["age_years"],
                    education_level=demo_dict["education_level"],
                    income_band=demo_dict["income_band"],
                    housing_status=demo_dict["housing_status"],
                    language_profile=demo_dict["language_profile"],
                    community_tenure=demo_dict["community_tenure"],
                    caregiving_load=demo_dict["caregiving_load"],
                    digital_media_habit=demo_dict["digital_media_habit"],
                ),
            )
        )

    if len(out) >= count:
        return out

    # Generate missing agents
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

    new_agents_data = []
    start_id = len(out)

    for i in range(start_id, count):
        zone_pick = _seeded(i + 8500)
        zone_idx = next((idx for idx, bound in enumerate(cumulative) if zone_pick <= bound), 0)
        zone = zones[max(0, zone_idx)]
        r1 = _seeded(i + 1)
        r2 = _seeded(i + 1001)
        lng_inset = (zone.lng_max - zone.lng_min) * 0.08
        lat_inset = (zone.lat_max - zone.lat_min) * 0.08
        role = ROLES[i % len(ROLES)]
        lat = zone.lat_min + lat_inset + r2 * max(0.0001, zone.lat_max - zone.lat_min - lat_inset * 2)
        lng = zone.lng_min + lng_inset + r1 * max(0.0001, zone.lng_max - zone.lng_min - lng_inset * 2)
        name = f"{FIRST[i % len(FIRST)]} {LAST[(i * 3) % len(LAST)]}"
        
        demographics = _generate_demographics(
            agent_id=i,
            role=role,
            lat=lat,
            lng=lng,
            city_id=city_id,
        )

        virt = _Virt(
            id=i,
            name=name,
            role=role,
            lat=lat,
            lng=lng,
            demographics=demographics,
        )
        out.append(virt)

        new_agents_data.append({
            "id": virt.id,
            "name": virt.name,
            "role": virt.role,
            "lat": virt.lat,
            "lng": virt.lng,
            "demographics": {
                "age_band": demographics.age_band,
                "age_years": demographics.age_years,
                "education_level": demographics.education_level,
                "income_band": demographics.income_band,
                "housing_status": demographics.housing_status,
                "language_profile": demographics.language_profile,
                "community_tenure": demographics.community_tenure,
                "caregiving_load": demographics.caregiving_load,
                "digital_media_habit": demographics.digital_media_habit,
            }
        })

    if new_agents_data:
        save_population(city_id, new_agents_data)

    return out

def _weighted_pick(seed: float, options: list[tuple[str, float]]) -> str:
    total = max(0.0001, sum(weight for _, weight in options))
    cursor = 0.0
    for label, weight in options:
        cursor += weight / total
        if seed <= cursor:
            return label
    return options[-1][0]


def _age_band_for_role(role: str, agent_id: int) -> tuple[str, int]:
    lowered = role.lower()
    seed = _seeded(agent_id * 19 + 7)
    if any(token in lowered for token in ("policy", "analyst", "research", "operations")):
        band = _weighted_pick(seed, [("25-34", 0.28), ("35-44", 0.34), ("45-54", 0.24), ("55-64", 0.14)])
    elif any(token in lowered for token in ("educator", "health", "journal", "responder")):
        band = _weighted_pick(seed, [("25-34", 0.22), ("35-44", 0.31), ("45-54", 0.29), ("55-64", 0.18)])
    else:
        band = _weighted_pick(seed, [("18-24", 0.14), ("25-34", 0.3), ("35-44", 0.24), ("45-54", 0.18), ("55-64", 0.1), ("65+", 0.04)])
    ranges = {
        "18-24": (18, 24),
        "25-34": (25, 34),
        "35-44": (35, 44),
        "45-54": (45, 54),
        "55-64": (55, 64),
        "65+": (65, 74),
    }
    lo, hi = ranges[band]
    age_years = lo + int(_seeded(agent_id * 23 + 13) * (hi - lo + 1))
    return band, age_years


def _generate_demographics(*, agent_id: int, role: str, lat: float, lng: float, city_id: str) -> _Demographics:
    city = get_city(city_id)
    lat_span = max(0.001, max(zone.lat_max for zone in city.land_zones) - min(zone.lat_min for zone in city.land_zones))
    lng_span = max(0.001, max(zone.lng_max for zone in city.land_zones) - min(zone.lng_min for zone in city.land_zones))
    northness = _clamp((lat - min(zone.lat_min for zone in city.land_zones)) / lat_span)
    eastness = _clamp((lng - min(zone.lng_min for zone in city.land_zones)) / lng_span)
    lowered = role.lower()
    age_band, age_years = _age_band_for_role(role, agent_id)
    education_seed = _seeded(agent_id * 31 + 3)
    if any(token in lowered for token in ("analyst", "research", "engineer", "journal")):
        education = _weighted_pick(education_seed, [("Bachelor's", 0.32), ("Master's", 0.42), ("Professional/Doctoral", 0.18), ("Associate", 0.08)])
    elif any(token in lowered for token in ("policy", "educator", "health")):
        education = _weighted_pick(education_seed, [("Bachelor's", 0.4), ("Master's", 0.26), ("Associate", 0.2), ("Professional/Doctoral", 0.08), ("Some college", 0.06)])
    else:
        education = _weighted_pick(education_seed, [("High school", 0.18), ("Some college", 0.24), ("Associate", 0.18), ("Bachelor's", 0.24), ("Master's", 0.12), ("Professional/Doctoral", 0.04)])

    income_seed = _seeded(agent_id * 37 + 9)
    role_income_bias = 0.12 if any(token in lowered for token in ("engineer", "policy", "research")) else 0.06 if any(token in lowered for token in ("health", "educator", "operations")) else -0.02
    income_position = _clamp(0.18 + eastness * 0.22 + northness * 0.12 + role_income_bias + (income_seed - 0.5) * 0.22)
    if income_position >= 0.72:
        income_band = "Upper middle income"
    elif income_position >= 0.52:
        income_band = "Middle income"
    elif income_position >= 0.34:
        income_band = "Lower middle income"
    else:
        income_band = "Economically strained"

    housing_seed = _seeded(agent_id * 41 + 5)
    if income_band == "Economically strained":
        housing_status = _weighted_pick(housing_seed, [("Stable renter", 0.48), ("Multigenerational household", 0.28), ("Housing insecure", 0.24)])
    elif income_band == "Upper middle income":
        housing_status = _weighted_pick(housing_seed, [("Homeowner", 0.54), ("Stable renter", 0.3), ("Multigenerational household", 0.16)])
    else:
        housing_status = _weighted_pick(housing_seed, [("Stable renter", 0.42), ("Homeowner", 0.34), ("Multigenerational household", 0.18), ("Housing insecure", 0.06)])

    language_profile = _weighted_pick(
        _seeded(agent_id * 43 + 17),
        [
            ("English-dominant", 0.46),
            ("Bilingual English-Spanish", 0.34),
            ("English plus household language", 0.14),
            ("Multilingual household", 0.06),
        ],
    )
    community_tenure = _weighted_pick(
        _seeded(agent_id * 47 + 21),
        [
            ("Recent arrival", 0.14),
            ("Established resident", 0.36),
            ("Long-term resident", 0.34),
            ("Deeply rooted local", 0.16),
        ],
    )
    caregiving_load = _weighted_pick(
        _seeded(agent_id * 53 + 27),
        [
            ("Low caregiving load", 0.42),
            ("Shared caregiving", 0.38),
            ("Primary caregiver", 0.2),
        ],
    )
    digital_media_habit = _weighted_pick(
        _seeded(agent_id * 59 + 31),
        [
            ("Local-news heavy", 0.26),
            ("Group-chat heavy", 0.24),
            ("Public-feed heavy", 0.24),
            ("Mixed verification habit", 0.26),
        ],
    )
    return _Demographics(
        age_band=age_band,
        age_years=age_years,
        education_level=education,
        income_band=income_band,
        housing_status=housing_status,
        language_profile=language_profile,
        community_tenure=community_tenure,
        caregiving_load=caregiving_load,
        digital_media_habit=digital_media_habit,
    )


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


def _demographic_conditioning_vector(demographics: _Demographics) -> dict[str, float]:
    education_support = {
        "High school": 0.12,
        "Some college": 0.24,
        "Associate": 0.34,
        "Bachelor's": 0.48,
        "Master's": 0.6,
        "Professional/Doctoral": 0.7,
    }.get(demographics.education_level, 0.3)
    economic_strain = {
        "Upper middle income": 0.12,
        "Middle income": 0.26,
        "Lower middle income": 0.48,
        "Economically strained": 0.72,
    }.get(demographics.income_band, 0.4)
    housing_flux = {
        "Homeowner": 0.12,
        "Stable renter": 0.28,
        "Multigenerational household": 0.34,
        "Housing insecure": 0.7,
    }.get(demographics.housing_status, 0.3)
    language_bridge = {
        "English-dominant": 0.1,
        "Bilingual English-Spanish": 0.44,
        "English plus household language": 0.3,
        "Multilingual household": 0.56,
    }.get(demographics.language_profile, 0.2)
    community_embeddedness = {
        "Recent arrival": 0.14,
        "Established resident": 0.42,
        "Long-term resident": 0.66,
        "Deeply rooted local": 0.84,
    }.get(demographics.community_tenure, 0.4)
    caregiving_pressure = {
        "Low caregiving load": 0.12,
        "Shared caregiving": 0.36,
        "Primary caregiver": 0.68,
    }.get(demographics.caregiving_load, 0.2)
    media_velocity = {
        "Local-news heavy": 0.2,
        "Group-chat heavy": 0.58,
        "Public-feed heavy": 0.66,
        "Mixed verification habit": 0.32,
    }.get(demographics.digital_media_habit, 0.3)
    age_index = {
        "18-24": 0.32,
        "25-34": 0.46,
        "35-44": 0.56,
        "45-54": 0.62,
        "55-64": 0.66,
        "65+": 0.6,
    }.get(demographics.age_band, 0.5)
    return {
        "education_support": education_support,
        "economic_strain": economic_strain,
        "housing_flux": housing_flux,
        "language_bridge": language_bridge,
        "community_embeddedness": community_embeddedness,
        "caregiving_pressure": caregiving_pressure,
        "media_velocity": media_velocity,
        "age_index": age_index,
    }


def _agent_conditioning(agent: _Virt, city_id: str) -> dict[str, float]:
    role = agent.role.lower()
    city = get_city(city_id)
    northness = _clamp((agent.lat - min(zone.lat_min for zone in city.land_zones)) / max(0.001, max(zone.lat_max for zone in city.land_zones) - min(zone.lat_min for zone in city.land_zones)))
    eastness = _clamp((agent.lng - min(zone.lng_min for zone in city.land_zones)) / max(0.001, max(zone.lng_max for zone in city.land_zones) - min(zone.lng_min for zone in city.land_zones)))
    demographics = _demographic_conditioning_vector(agent.demographics)

    analytical = 1.0 if any(token in role for token in ("analyst", "engineer", "research")) else 0.0
    service = 1.0 if any(token in role for token in ("health", "educator", "responder")) else 0.0
    civic = 1.0 if any(token in role for token in ("policy", "journalist", "organizer")) else 0.0

    return {
        "analytical": analytical,
        "service": service,
        "civic": civic,
        "peripheral_pressure": _clamp(abs(0.5 - northness) * 0.32 + abs(0.5 - eastness) * 0.32 + demographics["housing_flux"] * 0.08),
        "institutional_trust": _clamp(
            0.38
            + service * 0.14
            + civic * 0.08
            - analytical * 0.03
            + demographics["community_embeddedness"] * 0.12
            + demographics["education_support"] * 0.06
            - demographics["economic_strain"] * 0.11
            - demographics["media_velocity"] * 0.04
        ),
        "identity_salience": _clamp(
            0.28
            + civic * 0.18
            + analytical * 0.05
            + demographics["community_embeddedness"] * 0.18
            + demographics["caregiving_pressure"] * 0.08
        ),
        "education_support": demographics["education_support"],
        "economic_strain": demographics["economic_strain"],
        "housing_flux": demographics["housing_flux"],
        "language_bridge": demographics["language_bridge"],
        "community_embeddedness": demographics["community_embeddedness"],
        "caregiving_pressure": demographics["caregiving_pressure"],
        "media_velocity": demographics["media_velocity"],
        "age_index": demographics["age_index"],
    }


def _agent_traits(agent: _Virt, city_id: str) -> _Traits:
    cond = _agent_conditioning(agent, city_id)
    seeded_shift = lambda offset: (_seeded(agent.id * 29 + offset) - 0.5) * 0.12
    return _Traits(
        evidence_literacy=_clamp(
            0.34
            + cond["analytical"] * 0.18
            + cond["service"] * 0.07
            + cond["education_support"] * 0.34
            + (0.06 if agent.demographics.digital_media_habit == "Local-news heavy" else 0.03 if agent.demographics.digital_media_habit == "Mixed verification habit" else -0.02)
            + seeded_shift(7)
        ),
        peer_susceptibility=_clamp(
            0.28
            + cond["civic"] * 0.12
            + cond["peripheral_pressure"] * 0.14
            + cond["language_bridge"] * 0.18
            + cond["media_velocity"] * 0.22
            + seeded_shift(11)
        ),
        identity_sensitivity=_clamp(
            0.28
            + cond["identity_salience"] * 0.26
            + cond["community_embeddedness"] * 0.18
            + cond["caregiving_pressure"] * 0.08
            + seeded_shift(13)
        ),
        institutional_trust=_clamp(cond["institutional_trust"] + seeded_shift(17)),
        analytic_scrutiny=_clamp(
            0.28
            + cond["analytical"] * 0.26
            + cond["education_support"] * 0.24
            + cond["age_index"] * 0.08
            + (0.05 if agent.demographics.digital_media_habit == "Local-news heavy" else -0.03 if agent.demographics.digital_media_habit == "Public-feed heavy" else 0.0)
            + seeded_shift(19)
        ),
        baseline_openness=_clamp(
            0.4
            + cond["service"] * 0.07
            + cond["civic"] * 0.04
            + cond["language_bridge"] * 0.08
            + cond["community_embeddedness"] * 0.05
            - cond["economic_strain"] * 0.07
            - cond["peripheral_pressure"] * 0.05
            + seeded_shift(23)
        ),
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
        + cond["economic_strain"] * 0.05
        + cond["caregiving_pressure"] * 0.04
        - cond["institutional_trust"] * 0.03
        - cond["education_support"] * 0.04
        + (_seeded(agent.id * 17 + 11) - 0.5) * 0.04
    )
    emotional_delta = (
        case_features["threat"] * 0.16
        + case_features["identity"] * 0.08
        + cond["identity_salience"] * 0.06
        + cond["economic_strain"] * 0.04
        + cond["community_embeddedness"] * 0.03
        - case_features["prosocial"] * 0.05
        + (_seeded(agent.id * 17 + 23) - 0.5) * 0.05
    )
    defensive_delta = (
        case_features["threat"] * 0.18
        + case_features["institutional"] * (0.09 - cond["institutional_trust"] * 0.06)
        + case_features["identity"] * cond["identity_salience"] * 0.10
        + complexity * 0.04
        + cond["media_velocity"] * 0.04
        + cond["housing_flux"] * 0.03
        + (_seeded(agent.id * 17 + 37) - 0.5) * 0.05
    )
    memory_delta = (
        case_features["complexity"] * 0.15
        + cond["analytical"] * 0.03
        + cond["caregiving_pressure"] * 0.05
        + cond["age_index"] * 0.03
        - case_features["prosocial"] * 0.04
        - cond["education_support"] * 0.03
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


def _interpret_composite(metric_id: str, value: float) -> str:
    if metric_id == "arousal":
        return "Highly activated" if value >= 0.9 else "Moderately activated" if value >= 0.55 else "Relatively calm"
    if metric_id == "valence":
        return "Negatively valenced" if value <= -0.2 else "Positively valenced" if value >= 0.2 else "Mixed affect"
    if metric_id == "dominance":
        return "Emotion outweighs control" if value <= -0.2 else "Rational control is present" if value >= 0.2 else "Balanced control"
    if metric_id == "approach_avoid":
        return "Avoidance-oriented" if value <= -0.2 else "Approach-oriented" if value >= 0.2 else "No strong directional pull"
    if metric_id == "regulation":
        return "Poor emotional regulation" if value <= -0.15 else "Good emotional regulation" if value >= 0.15 else "Regulation is limited"
    if metric_id == "herding":
        return "Highly socially influenced" if value >= 0.75 else "Moderately socially influenced" if value >= 0.45 else "Relatively independent"
    if metric_id == "confidence":
        return "Strong neural read" if value >= 1.2 else "Moderate neural read" if value >= 0.7 else "Uncertain neural read"
    if metric_id == "reactivity":
        return "Thinking precedes emotion" if value <= -1 else "Emotion precedes thinking" if value >= 1 else "Thought and emotion rise together"
    return "Context-dependent"


def _augment_tribe_meta(tribe_meta: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(tribe_meta, dict) or not tribe_meta:
        return {}

    roi_stats = tribe_meta.get("roi_stats") if isinstance(tribe_meta.get("roi_stats"), dict) else {}
    connectivity = tribe_meta.get("connectivity") if isinstance(tribe_meta.get("connectivity"), dict) else {}
    composites = tribe_meta.get("composites") if isinstance(tribe_meta.get("composites"), dict) else {}

    roi_ranked = sorted(
        (
            {
                "id": roi_id,
                "label": ROI_DISPLAY_LABELS.get(roi_id, roi_id.replace("_", " ").title()),
                "peak": round(float(stats.get("peak", 0.0)), 3),
                "auc": round(float(stats.get("auc", 0.0)), 3),
                "trajectory": str(stats.get("trajectory") or "unknown"),
                "onset_seconds": round(float(stats.get("onset_tr", 0.0)) * 2.0, 1),
                "sustained": bool(stats.get("sustained", False)),
            }
            for roi_id, stats in roi_stats.items()
            if isinstance(stats, dict)
        ),
        key=lambda item: item["peak"] * (1.0 + item["auc"]) ** 0.5,
        reverse=True,
    )
    weakest_ranked = list(reversed(roi_ranked))

    processing_sequence = sorted(
        (
            {
                "id": roi_id,
                "label": ROI_DISPLAY_LABELS.get(roi_id, roi_id.replace("_", " ").title()),
                "onset_seconds": round(float(stats.get("onset_tr", 0.0)) * 2.0, 1),
            }
            for roi_id, stats in roi_stats.items()
            if isinstance(stats, dict)
        ),
        key=lambda item: item["onset_seconds"],
    )

    strongest_link = None
    if connectivity:
        ranked_links = sorted(
            (
                {
                    "id": pair_id,
                    "label": CONNECTIVITY_DISPLAY_LABELS.get(pair_id, pair_id.replace("_", " ").title()),
                    "r": round(float(values.get("r", 0.0)), 3),
                    "p": round(float(values.get("p", 1.0)), 4),
                }
                for pair_id, values in connectivity.items()
                if isinstance(values, dict)
            ),
            key=lambda item: abs(item["r"]),
            reverse=True,
        )
        strongest_link = ranked_links[0] if ranked_links else None

    composite_order = [
        ("arousal", "Arousal"),
        ("valence", "Valence"),
        ("dominance", "Dominance"),
        ("approach_avoid", "Approach / avoid"),
        ("regulation", "Regulation"),
        ("herding", "Herding"),
        ("reactivity", "Reactivity"),
        ("confidence", "Read confidence"),
    ]
    composite_highlights = [
        {
            "id": comp_id,
            "label": label,
            "value": round(float(composites.get(comp_id, 0.0)), 3),
            "interpretation": _interpret_composite(comp_id, float(composites.get(comp_id, 0.0))),
        }
        for comp_id, label in composite_order
        if comp_id in composites
    ]

    narrative_flags: list[str] = []
    if float(composites.get("arousal", 0.0)) >= 0.85:
        narrative_flags.append("The stimulus is strongly activating, so agents start closer to vigilance than calm.")
    if float(composites.get("herding", 0.0)) >= 0.6:
        narrative_flags.append("Social default activity is elevated, so messenger fit and local repetition should matter more.")
    if float(composites.get("regulation", 0.0)) <= -0.1:
        narrative_flags.append("Regulation is weak, so contradictions are more likely to collapse into rejection than careful evaluation.")
    if float(composites.get("approach_avoid", 0.0)) <= -0.2:
        narrative_flags.append("The global stance tilts toward avoidance, which makes spread harder unless peer lift is unusually strong.")
    if float(composites.get("reactivity", 0.0)) <= -1.0:
        narrative_flags.append("Analytical processing activates before emotion, which favors verification over impulsive uptake.")

    surface_summary = {
        "dominant_response": roi_ranked[0] if roi_ranked else None,
        "weakest_response": weakest_ranked[0] if weakest_ranked else None,
        "processing_sequence": processing_sequence[:6],
        "strongest_link": strongest_link,
        "composite_highlights": composite_highlights,
        "narrative_flags": narrative_flags[:4],
    }

    enriched = dict(tribe_meta)
    enriched["surface_summary"] = surface_summary
    enriched["segments_preview"] = roi_ranked[:4]
    enriched["segment_count"] = len(roi_ranked)
    per_agent = tribe_meta.get("per_agent")
    if isinstance(per_agent, dict) and per_agent:
        enriched["per_agent_count"] = len(per_agent)
        enriched["tribe_personalization_note"] = (
            "surface_summary uses the shared stimulus baseline; per_agent.composites "
            "are demographics-conditioned and drive per-agent BSV and herding/approach/regulation/reactivity biases."
        )
    return enriched


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


def _role_social_style(role: str) -> str:
    lowered = role.lower()
    if any(token in lowered for token in ("analyst", "engineer", "research")):
        return "analytical"
    if any(token in lowered for token in ("educator", "healthcare", "first responder")):
        return "public_service"
    if any(token in lowered for token in ("organizer", "policy", "journalist")):
        return "civic"
    if any(token in lowered for token in ("small business", "operations")):
        return "pragmatic"
    return "general"


def _role_compatibility(a_role: str, b_role: str) -> float:
    a_style = _role_social_style(a_role)
    b_style = _role_social_style(b_role)
    if a_style == b_style:
        return 0.92
    paired_styles = {a_style, b_style}
    if paired_styles in (
        {"civic", "public_service"},
        {"civic", "pragmatic"},
        {"analytical", "public_service"},
        {"analytical", "civic"},
    ):
        return 0.74
    if paired_styles in (
        {"general", "civic"},
        {"general", "public_service"},
        {"general", "pragmatic"},
        {"general", "analytical"},
    ):
        return 0.66
    return 0.54


def _network_edge_weight(a: _Virt, b: _Virt) -> tuple[float, float]:
    distance = math.sqrt(_distance_sq(a, b))
    distance_score = _clamp(1.0 - distance / 0.115, 0.25, 1.0)
    compatibility = _role_compatibility(a.role, b.role)
    shared_cohort_bonus = 0.06 if _role_cohort(a.role) == _role_cohort(b.role) else 0.0
    weight = _clamp(distance_score * 0.58 + compatibility * 0.36 + shared_cohort_bonus, 0.25, 0.98)
    return weight, compatibility


def _build_network_edges(population: list[_Virt], degree: int = 4) -> list[_NetworkEdge]:
    """Construct a sparse undirected adjacency list from local geographic proximity."""

    edges: dict[tuple[int, int], tuple[float, float]] = {}
    for agent in population:
        nearest = sorted(
            (other for other in population if other.id != agent.id),
            key=lambda other: _distance_sq(agent, other),
        )[:degree]
        for other in nearest:
            a, b = sorted((agent.id, other.id))
            weight, compatibility = _network_edge_weight(agent, other)
            prior = edges.get((a, b))
            if prior is None or weight > prior[0]:
                edges[(a, b)] = (weight, compatibility)
    return [
        _NetworkEdge(source_id=a, target_id=b, weight=weight, compatibility=compatibility)
        for (a, b), (weight, compatibility) in sorted(edges.items())
    ]


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


def _state_from_context(
    *,
    score: float,
    claim_credibility: float,
    traits: _Traits | dict[str, Any] | None = None,
    signal: SignalType | str | None = None,
    supportive_context: float = 0.0,
    messenger_alignment: float = 0.0,
) -> str:
    adopt_threshold = 0.72 if claim_credibility < 0.18 else 0.66 if claim_credibility < 0.3 else 0.61
    reject_threshold = 0.31 if claim_credibility < 0.18 else 0.34 if claim_credibility < 0.3 else 0.43

    if traits is not None:
        if isinstance(traits, _Traits):
            evidence_literacy = float(traits.evidence_literacy)
            peer_susceptibility = float(traits.peer_susceptibility)
            institutional_trust = float(traits.institutional_trust)
            analytic_scrutiny = float(traits.analytic_scrutiny)
            baseline_openness = float(traits.baseline_openness)
        else:
            evidence_literacy = float(traits.get("evidence_literacy", 0.5))
            peer_susceptibility = float(traits.get("peer_susceptibility", 0.5))
            institutional_trust = float(traits.get("institutional_trust", 0.5))
            analytic_scrutiny = float(traits.get("analytic_scrutiny", 0.5))
            baseline_openness = float(traits.get("baseline_openness", 0.5))

        adopt_threshold += analytic_scrutiny * 0.045 + evidence_literacy * 0.03
        adopt_threshold -= peer_susceptibility * 0.04 + baseline_openness * 0.05
        adopt_threshold -= (1.0 - institutional_trust) * 0.018

        reject_threshold += analytic_scrutiny * 0.02 + evidence_literacy * 0.018
        reject_threshold -= peer_susceptibility * 0.028 + baseline_openness * 0.035
        reject_threshold -= (1.0 - institutional_trust) * 0.018

    supportive_lift = supportive_context * 0.05 + messenger_alignment * 0.06
    adopt_threshold -= supportive_lift
    reject_threshold -= supportive_lift * 0.82

    if signal == "social_proof":
        adopt_threshold -= 0.022 + messenger_alignment * 0.01
        reject_threshold -= 0.016
    elif signal == "empathic_resonance":
        adopt_threshold -= 0.014
        reject_threshold -= 0.01
    elif signal == "memory_alignment":
        adopt_threshold -= 0.01
    elif signal == "cognitive_overload":
        adopt_threshold += 0.014
        reject_threshold += 0.006
    elif signal == "defensive_reactance":
        adopt_threshold += 0.02
        reject_threshold += 0.008

    adopt_threshold = _clamp(adopt_threshold, 0.48, 0.82)
    reject_threshold = _clamp(reject_threshold, 0.18, adopt_threshold - 0.08)

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


def _round_phase_label(round_number: int, action_type: str | None, target_agent_id: int | None) -> str:
    mode = "direct exchange" if action_type == "talk_to_agent" and target_agent_id is not None else "public circulation"
    stage = "first read" if round_number == 1 else "network update" if round_number == 2 else "settled position"
    return f"{stage} · {mode}"


def _round_trigger_label(
    *,
    authored_post: dict[str, Any] | None,
    weighted_support: float,
    weighted_pushback: float,
    total_visible: int,
) -> str:
    if authored_post and authored_post.get("target_agent_id") is not None:
        return f"direct tie · push {weighted_pushback:.2f} · support {weighted_support:.2f}"
    if total_visible == 0:
        return "no local signal"
    if weighted_support > weighted_pushback:
        return f"support-led circulation · {weighted_support:.2f}"
    if weighted_pushback > weighted_support:
        return f"pushback-led circulation · {weighted_pushback:.2f}"
    return f"mixed neighborhood signal · {total_visible} visible"


def _change_summary(
    *,
    state: str,
    score: float,
    previous_score: float,
    supportive_ratio: float,
    skeptical_ratio: float,
    messenger_alignment: float,
) -> str:
    delta = score - previous_score
    movement = "flat" if abs(delta) < 0.015 else "up" if delta > 0 else "down"
    dominant = "support" if supportive_ratio > skeptical_ratio else "pushback" if skeptical_ratio > supportive_ratio else "balance"
    return (
        f"score {previous_score:.2f} → {score:.2f}; movement {movement}; "
        f"support {supportive_ratio:.2f}; pushback {skeptical_ratio:.2f}; fit {messenger_alignment:.2f}; "
        f"state {state}; dominant pressure {dominant}."
    )


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
    claim_credibility: float,
) -> dict[str, Any]:
    """Run a real LangGraph propagation loop and convert it into the UI payload shape."""

    population_by_id = {agent.id: agent for agent in population}
    agent_payload_by_id = {str(agent["id"]): agent for agent in agents}
    network_edges = _build_network_edges(population)

    connections_by_id: dict[int, set[int]] = {agent.id: set() for agent in population}
    connection_profiles_by_id: dict[int, dict[str, dict[str, Any]]] = {agent.id: {} for agent in population}
    for edge in network_edges:
        connections_by_id[edge.source_id].add(edge.target_id)
        connections_by_id[edge.target_id].add(edge.source_id)
        source_role = population_by_id[edge.source_id].role
        target_role = population_by_id[edge.target_id].role
        connection_profiles_by_id[edge.source_id][str(edge.target_id)] = {
            "weight": round(edge.weight, 3),
            "compatibility": round(edge.compatibility, 3),
            "role": target_role,
            "cohort": _role_cohort(target_role),
        }
        connection_profiles_by_id[edge.target_id][str(edge.source_id)] = {
            "weight": round(edge.weight, 3),
            "compatibility": round(edge.compatibility, 3),
            "role": source_role,
            "cohort": _role_cohort(source_role),
        }

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
            "traits": (payload.get("_pipeline") or {}).get("traits", {}),
            "conditioning": (payload.get("_pipeline") or {}).get("conditioning", {}),
            "demographics": payload.get("demographics", {}),
            "baseline_score": float((payload.get("_pipeline") or {}).get("baseline_score", 0.5)),
            "target_score": float((payload.get("_pipeline") or {}).get("final_score", 0.5)),
            "connections": [str(other_id) for other_id in sorted(connections_by_id[virt.id])],
            "connection_profiles": connection_profiles_by_id[virt.id],
        }

    sorted_by_degree = sorted(
        graph_agents.keys(),
        key=lambda aid: len(graph_agents[aid]["connections"]),
        reverse=True
    )
    key_actor_ids = set(sorted_by_degree[:5])

    base_engine = _HeuristicLangGraphDecisionEngine(agent_lookup=graph_agents)
    
    try:
        import logging
        llm_engine = make_chat_openai_decision_engine(
            model=settings.ifm_k2_model,
            api_key=settings.ifm_api_key or "mock",
            base_url=settings.ifm_api_url,
        )
        engine = HybridLangGraphDecisionEngine(
            base_engine=base_engine,
            llm_engine=llm_engine,
            key_actor_ids=key_actor_ids,
        )
    except Exception as e:
        logger.warning("Failed to initialize LangChain LLM engine for Hybrid orchestration. Falling back to heuristic engine. %s", e)
        engine = base_engine

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
        engine,
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
    prev_scores: dict[int, float] = {}
    prev_states: dict[int, str] = {}
    for agent in population:
        payload = agent_payload_by_id[str(agent.id)]
        pipeline = payload.get("_pipeline") or {}
        baseline_score = float(pipeline.get("baseline_score", 0.5))
        prev_scores[agent.id] = baseline_score
        prev_states[agent.id] = _state_from_score(baseline_score, claim_credibility)

    for tick in range(1, final_state["max_ticks"] + 1):
        posts = rounds_by_tick.get(tick, [])
        next_scores: dict[int, float] = {}
        next_states: dict[int, str] = {}
        enriched_posts: list[dict[str, Any]] = []

        for virt in population:
            profile = graph_agents[str(virt.id)]
            traits = profile.get("traits") or {}
            peer_susceptibility = float(traits.get("peer_susceptibility", 0.5))
            scrutiny = float(traits.get("analytic_scrutiny", 0.5))
            openness = float(traits.get("baseline_openness", 0.5))
            identity_sensitivity = float(traits.get("identity_sensitivity", 0.5))
            baseline_score = float(profile.get("baseline_score", 0.5))
            target_score = float(profile.get("target_score", baseline_score))
            direct_neighbors = {int(other_id) for other_id in profile.get("connections", []) if str(other_id).isdigit()}
            connection_profiles = profile.get("connection_profiles") or {}
            visible = [
                post
                for post in posts
                if post["agent_id"] in direct_neighbors
                and (post["action_type"] == "post_public" or post["target_agent_id"] == virt.id)
            ]

            supportive_weight = 0.0
            skeptical_weight = 0.0
            neutral_weight = 0.0
            direct_support = False
            direct_pushback = False
            strongest_neighbor_weight = 0.0
            aligned_messenger_weight = 0.0
            for post in visible:
                neighbor_profile = connection_profiles.get(str(post["agent_id"])) or {}
                tie_weight = _clamp(float(neighbor_profile.get("weight", 0.42)), 0.2, 1.0)
                compatibility = _clamp(float(neighbor_profile.get("compatibility", 0.55)), 0.2, 1.0)
                directed_bonus = 1.18 if post["target_agent_id"] == virt.id else 1.0
                action_bonus = 1.08 if post["action_type"] == "talk_to_agent" else 1.0
                influence = tie_weight * (0.72 + compatibility * 0.38) * directed_bonus * action_bonus
                strongest_neighbor_weight = max(strongest_neighbor_weight, influence)
                if compatibility >= 0.74:
                    aligned_messenger_weight += influence
                prior_state = prev_states.get(post["agent_id"])
                if prior_state == "adopted":
                    supportive_weight += influence
                    if post["target_agent_id"] == virt.id:
                        direct_support = True
                elif prior_state == "rejected":
                    skeptical_weight += influence
                    if post["target_agent_id"] == virt.id:
                        direct_pushback = True
                else:
                    neutral_weight += influence

            total_visible = len(visible)
            total_weight = max(0.001, supportive_weight + skeptical_weight + neutral_weight)
            supportive_ratio = supportive_weight / total_weight
            skeptical_ratio = skeptical_weight / total_weight
            neutral_ratio = neutral_weight / total_weight
            messenger_alignment = aligned_messenger_weight / total_weight

            score = _clamp(
                prev_scores[virt.id] * 0.39
                + baseline_score * 0.14
                + target_score * 0.22
                + supportive_ratio * (0.085 + peer_susceptibility * 0.12 + messenger_alignment * 0.11)
                - skeptical_ratio * (0.045 + scrutiny * 0.095 + messenger_alignment * 0.04)
                - neutral_ratio * 0.018
                + openness * 0.038
                - identity_sensitivity * (0.022 if claim_credibility < 0.3 else 0.0)
                + messenger_alignment * 0.028
                + strongest_neighbor_weight * (0.018 if supportive_weight > skeptical_weight else -0.012)
                + (0.04 + messenger_alignment * 0.04 if direct_support else 0.0)
                - (0.028 + messenger_alignment * 0.028 if direct_pushback else 0.0)
            )
            state = _state_from_context(
                score=score,
                claim_credibility=claim_credibility,
                traits=traits,
                signal=agent_payload["dominant_signal"],
                supportive_context=supportive_ratio,
                messenger_alignment=messenger_alignment,
            )
            confidence = round(
                _clamp(
                    0.32
                    + abs(score - 0.5) * 0.92
                    + min(0.08, total_visible * 0.015)
                    + strongest_neighbor_weight * 0.05
                    + (0.03 if direct_support or direct_pushback else 0.0),
                    0.2,
                    0.92,
                ),
                3,
            )

            authored_post = next((post for post in posts if post["agent_id"] == virt.id), None)
            agent_payload = agent_payload_by_id[str(virt.id)]
            history_row = {
                "round": tick,
                "phase_label": _round_phase_label(
                    tick,
                    authored_post["action_type"] if authored_post else None,
                    authored_post["target_agent_id"] if authored_post else None,
                ),
                "belief_state": state,
                "confidence": confidence,
                "confidence_delta": round(confidence - per_agent_history[virt.id][-1]["confidence"], 3)
                if per_agent_history[virt.id]
                else round(confidence - float(profile.get("confidence", 0.5)), 3),
                "sentiment": _sentiment_for_state(state),
                "post": authored_post["post"] if authored_post else "[no outward action]",
                "trigger": _round_trigger_label(
                    authored_post=authored_post,
                    weighted_support=supportive_weight,
                    weighted_pushback=skeptical_weight,
                    total_visible=total_visible,
                ),
                "change_summary": _change_summary(
                    state=state,
                    score=score,
                    previous_score=prev_scores[virt.id],
                    supportive_ratio=supportive_ratio,
                    skeptical_ratio=skeptical_ratio,
                    messenger_alignment=messenger_alignment,
                ),
                # Shares (0–1) match the support/pushback numbers embedded in change_summary.
                "supportive_pressure": round(supportive_ratio, 3),
                "skeptical_pressure": round(skeptical_ratio, 3),
                "support_influence": round(supportive_weight, 3),
                "pushback_influence": round(skeptical_weight, 3),
                "messenger_alignment": round(messenger_alignment, 3),
            }
            per_agent_history[virt.id].append(history_row)

            if authored_post:
                enriched_posts.append(
                    {
                        **authored_post,
                        "belief_state": state,
                        "confidence": confidence,
                        "sentiment": _sentiment_for_state(state),
                        "dominant_signal": agent_payload["dominant_signal"],
                        "weighted_support": round(supportive_weight, 3),
                        "weighted_pushback": round(skeptical_weight, 3),
                    }
                )

            next_scores[virt.id] = score
            next_states[virt.id] = state

        adopted = sum(1 for state in next_states.values() if state == "adopted")
        rejected = sum(1 for state in next_states.values() if state == "rejected")
        neutral = len(next_states) - adopted - rejected
        dominant_signal = max(
            ("cognitive_overload", "defensive_reactance", "social_proof", "memory_alignment", "empathic_resonance"),
            key=lambda sig: sum(
                1
                for agent_id, agent_state in next_states.items()
                if agent_state in {"adopted", "rejected", "neutral"} and agent_payload_by_id[str(agent_id)]["dominant_signal"] == sig
            ),
        )
        talk_count = sum(1 for item in posts if item["action_type"] == "talk_to_agent")
        public_count = sum(1 for item in posts if item["action_type"] == "post_public")
        rounds.append(
            {
                "round": tick,
                "adoption_rate": round(adopted / max(1, len(population)) * 100),
                "rejection_rate": round(rejected / max(1, len(population)) * 100),
                "neutral_rate": round(neutral / max(1, len(population)) * 100),
                "dominant_mechanism": dominant_signal,
                "notable_shift": (
                    f"Tick {tick} produced {talk_count} direct neighbor conversations and {public_count} public broadcasts, "
                    f"with tie-weighted messenger influence determining whether support or pushback carried more force."
                ),
                "posts": enriched_posts[:8],
            }
        )
        prev_scores = next_scores
        prev_states = next_states

    edge_payload = [
        {
            "source_id": edge.source_id,
            "target_id": edge.target_id,
            "source_lng": population_by_id[edge.source_id].lng,
            "source_lat": population_by_id[edge.source_id].lat,
            "target_lng": population_by_id[edge.target_id].lng,
            "target_lat": population_by_id[edge.target_id].lat,
            "weight": round(edge.weight, 3),
            "compatibility": round(edge.compatibility, 3),
        }
        for edge in network_edges
    ]

    return {
        "rounds": rounds,
        "per_agent_history": per_agent_history,
        "event_log": event_log,
        "network_edges": edge_payload,
        "narrative_summary": (
            "This propagation layer is driven by a LangGraph loop with per-tick stance updates. "
            "Agents react only to messages authored by directly connected neighbors, and those neighbors now carry "
            "different influence weights based on tie strength, role compatibility, and whether the exchange is direct or ambient."
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
    conditioning: dict[str, float],
    baseline_score: float,
    final_score: float,
    local_adoption_ratio: float,
    score_breakdown: dict[str, float],
    claim_diagnostics: dict[str, float | str],
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    signal = _dominant_signal(bsv, regions, supportive_neighbors)
    claim_credibility = float(claim_diagnostics["credibility"])
    predetermined_state = _state_from_context(
        score=final_score,
        claim_credibility=claim_credibility,
        traits=traits,
        signal=signal,
        supportive_context=local_adoption_ratio,
        messenger_alignment=max(0.0, resonance * 0.65),
    )
    role_lens = _role_reasoning_lens(agent.role)
    primary_decision_anchor = _primary_decision_anchor(
        traits=traits,
        claim_diagnostics=claim_diagnostics,
        score_breakdown=score_breakdown,
    )
    social_context_label = _social_context_label(
        supportive_neighbors,
        total_neighbors,
        local_adoption_ratio,
    )

    state = predetermined_state
    parsed_signal = signal
    confidence = _clamp(0.42 + (abs(final_score - 0.5) * 0.54) + (claim_credibility * 0.08), 0.18, 0.78)
    async with semaphore:
        reasoning = await call_k2_explanation_only(
            httpx_client,
            agent_name=agent.name,
            agent_role=agent.role,
            role_lens=role_lens,
            scenario=analysis_text,
            case_goal=case_goal,
            precomputed_outcome=state.title(),
            dominant_signal=signal,
            social_context_label=social_context_label,
            primary_decision_anchor=primary_decision_anchor,
            traits={
                "evidence_literacy": round(float(traits.evidence_literacy), 3),
                "peer_susceptibility": round(float(traits.peer_susceptibility), 3),
                "identity_sensitivity": round(float(traits.identity_sensitivity), 3),
                "institutional_trust": round(float(traits.institutional_trust), 3),
                "analytic_scrutiny": round(float(traits.analytic_scrutiny), 3),
                "baseline_openness": round(float(traits.baseline_openness), 3),
                "demographic_summary": _demographic_profile_summary(agent.demographics),
            },
            demographics={
                "age_band": agent.demographics.age_band,
                "age_years": agent.demographics.age_years,
                "education_level": agent.demographics.education_level,
                "income_band": agent.demographics.income_band,
                "housing_status": agent.demographics.housing_status,
                "language_profile": agent.demographics.language_profile,
                "community_tenure": agent.demographics.community_tenure,
                "caregiving_load": agent.demographics.caregiving_load,
                "digital_media_habit": agent.demographics.digital_media_habit,
            },
            bsv={key: round(float(value), 3) for key, value in bsv.items()},
            score_breakdown={key: round(float(value), 3) for key, value in score_breakdown.items()},
        )

    return {
        "id": agent.id,
        "name": agent.name,
        "role": agent.role,
        "longitude": agent.lng,
        "latitude": agent.lat,
        "demographics": {
            "age_band": agent.demographics.age_band,
            "age_years": agent.demographics.age_years,
            "education_level": agent.demographics.education_level,
            "income_band": agent.demographics.income_band,
            "housing_status": agent.demographics.housing_status,
            "language_profile": agent.demographics.language_profile,
            "community_tenure": agent.demographics.community_tenure,
            "caregiving_load": agent.demographics.caregiving_load,
            "digital_media_habit": agent.demographics.digital_media_habit,
            "summary": _demographic_profile_summary(agent.demographics),
        },
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
            "vulnerability": _demographic_vulnerability(agent.demographics, parsed_signal),
            "cause_of_state": reasoning[0] if reasoning else _signal_summary(parsed_signal, state, regions),
            "best_intervention": _intervention_hint(parsed_signal),
        },
        "_pipeline": {
            "traits": traits.__dict__,
            "conditioning": {k: round(float(v), 3) for k, v in conditioning.items()},
            "baseline_score": round(baseline_score, 3),
            "final_score": round(final_score, 3),
            "local_adoption_ratio": round(local_adoption_ratio, 3),
            "score_breakdown": {k: round(v, 3) for k, v in score_breakdown.items()},
        },
    }


def _fallback_reasoning_payload(
    *,
    item: dict[str, Any],
    claim_credibility: float,
) -> dict[str, Any]:
    state = _state_from_score(item["final_score"], claim_credibility)
    return {
        "reasoning": [
            _signal_summary(
                item["default_signal"],
                state,
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
                + claim_credibility * 0.08,
                0.18,
                0.78,
            ),
            3,
        ),
        "signal": item["default_signal"],
    }


def _role_reasoning_lens(role: str) -> str:
    lowered = role.lower()
    if "journal" in lowered:
        return "source verification and documentation standards"
    if any(token in lowered for token in ("policy", "analyst", "civic")):
        return "institutional process, public records, and governance plausibility"
    if any(token in lowered for token in ("health", "educator", "responder")):
        return "public-service duty, practical harm, and trustworthiness"
    if any(token in lowered for token in ("engineer", "research")):
        return "evidence quality, internal consistency, and analytical scrutiny"
    if any(token in lowered for token in ("organizer", "small business", "operations")):
        return "community impact, practical consequences, and local trust signals"
    return "personal trust, plausibility, and local social proof"


def _demographic_profile_summary(demographics: _Demographics) -> str:
    return (
        f"{demographics.age_band}, {demographics.education_level.lower()}, "
        f"{demographics.housing_status.lower()}, {demographics.language_profile.lower()}"
    )


def _demographic_context_clause(demographics: _Demographics, agent_id: int) -> str:
    clauses = [
        f"They are {demographics.age_band.lower()} with a {demographics.education_level.lower()} background and {demographics.community_tenure.lower()} ties to the area.",
        f"Their context includes {demographics.housing_status.lower()}, {demographics.caregiving_load.lower()}, and a {demographics.digital_media_habit.lower()} information habit.",
        f"They move information through a {demographics.language_profile.lower()} setting, which changes how quickly neighborhood narratives reach them.",
    ]
    return clauses[agent_id % len(clauses)]


def _demographic_vulnerability(demographics: _Demographics, signal: SignalType) -> str:
    bridge = (
        "cross-community circulation"
        if demographics.language_profile in {"Bilingual English-Spanish", "Multilingual household"}
        else "single-channel verification"
    )
    if signal == "cognitive_overload":
        return (
            f"Most sensitive to cognitive overload when {demographics.caregiving_load.lower()} and "
            f"{demographics.digital_media_habit.lower()} compress attention."
        )
    if signal == "social_proof":
        return (
            f"Most sensitive to social proof through {bridge} in a {demographics.community_tenure.lower()} local context."
        )
    if signal == "defensive_reactance":
        return (
            f"Most sensitive to reactance when {demographics.housing_status.lower()} and {demographics.income_band.lower()} conditions raise the stakes of institutional ambiguity."
        )
    if signal == "memory_alignment":
        return (
            f"Most sensitive to familiar-story effects through {demographics.community_tenure.lower()} neighborhood memory."
        )
    return (
        f"Most sensitive to empathic resonance under {demographics.caregiving_load.lower()} and {demographics.language_profile.lower()} community ties."
    )


def _primary_decision_anchor(
    *,
    traits: _Traits,
    claim_diagnostics: dict[str, float | str],
    score_breakdown: dict[str, float],
) -> str:
    if float(traits.analytic_scrutiny) >= 0.64 or float(traits.evidence_literacy) >= 0.66:
        return "high evidence scrutiny"
    if float(traits.peer_susceptibility) >= 0.62:
        return "strong peer-normalization sensitivity"
    if float(traits.identity_sensitivity) >= 0.62:
        return "identity-threat sensitivity"
    if float(traits.institutional_trust) <= 0.34:
        return "low institutional trust"
    if float(score_breakdown.get("prior_fit", 0.0)) <= 0.2:
        return "weak prior fit"
    if float(claim_diagnostics.get("credibility", 0.0)) <= 0.22:
        return "low claim credibility"
    return "cognitive overload under low-trust ambiguity"


def _social_context_label(supportive_neighbors: int, total_neighbors: int, local_adoption_ratio: float) -> str:
    if total_neighbors == 0:
        return "isolated local context with no visible reinforcement"
    if supportive_neighbors == 0:
        return f"zero supportive neighbors out of {total_neighbors}"
    if local_adoption_ratio >= 0.45:
        return f"meaningful peer reinforcement ({supportive_neighbors} of {total_neighbors})"
    return f"limited peer reinforcement ({supportive_neighbors} of {total_neighbors})"


def _role_opening(role: str, role_lens: str, agent_id: int) -> str:
    connector = "evaluates through" if agent_id % 2 == 0 else "filters through"
    return f"As a {role.lower()}, this person {connector} {role_lens}."


def _verification_gap(role: str, domain: str, analysis_text: str, agent_id: int) -> str:
    lowered_role = role.lower()
    if "journal" in lowered_role:
        return "the story still lacks a verifiable source, attributable record, and checkable document trail"
    if any(token in lowered_role for token in ("policy", "analyst", "civic")):
        return "the claim still lacks the vote, hearing, memo, or process footprint that a real action would leave behind"
    if any(token in lowered_role for token in ("health", "educator", "responder")):
        return "the warning still arrives without the kind of vetted guidance or accountable sourcing this role would act on"
    if any(token in lowered_role for token in ("engineer", "research")):
        return "the evidence chain still has too many inference jumps and too few checkable anchors"
    return "the story still asks for belief faster than it provides proof"


def _secondary_driver_phrase(
    *,
    signal: SignalType,
    social_context_label: str,
    primary_decision_anchor: str,
    bsv: BSV,
    score_breakdown: dict[str, float],
    agent_id: int,
) -> str:
    if signal == "cognitive_overload":
        return (
            f"Cognitive load is {bsv['cognitive_load']:.2f} and working-memory strain is {bsv['working_memory_strain']:.2f}, "
            "so unresolved gaps remain unresolved instead of being integrated."
        )
    if signal == "defensive_reactance":
        return (
            f"The message is being processed as agenda-driven, and {primary_decision_anchor} converts uncertainty into active pushback."
        )
    if signal == "social_proof":
        return f"Social context matters here, but {social_context_label} does not create enough local momentum to stabilize the claim."
    if signal == "memory_alignment":
        return "Prior fit stays weak, so the claim does not map cleanly onto anything already trusted enough to repeat."
    return f"There is some openness in the background state, but {social_context_label} and the weak factual footing still keep acceptance from locking in."


def _resolution_phrase(
    *,
    state: str,
    social_context_label: str,
    credibility: float,
    primary_decision_anchor: str,
    gap: str,
    score_breakdown: dict[str, float],
    agent_id: int,
) -> str:
    prior_fit = float(score_breakdown.get("prior_fit", 0.0))
    if state == "adopted":
        return f"That mix of messenger fit, {primary_decision_anchor}, and {social_context_label} is enough to carry the claim into adoption."
    if state == "neutral":
        return "The claim never becomes trustworthy, but it also does not fully collapse, so the result settles into a wait-and-see posture."

    if credibility <= 0.22:
        return f"Credibility at {credibility:.2f} leaves {social_context_label} with too little force to rescue the claim."
    if prior_fit <= 0.2:
        return f"Weak prior fit gives the story nowhere stable to land, so {social_context_label} cannot convert attention into belief."
    return f"Because {gap}, and because {social_context_label} adds too little lift, the claim resolves to rejection."


def _compose_agent_reasoning(
    *,
    agent: _Virt,
    domain: str,
    analysis_text: str,
    signal: SignalType,
    state: str,
    role_lens: str,
    social_context_label: str,
    primary_decision_anchor: str,
    bsv: BSV,
    traits: _Traits,
    score_breakdown: dict[str, float],
    claim_diagnostics: dict[str, float | str],
) -> list[str]:
    opening = _role_opening(agent.role, role_lens, agent.id)
    gap = _verification_gap(agent.role, domain, analysis_text, agent.id)
    demographic_clause = _demographic_context_clause(agent.demographics, agent.id)
    second = _secondary_driver_phrase(
        signal=signal,
        social_context_label=social_context_label,
        primary_decision_anchor=primary_decision_anchor,
        bsv=bsv,
        score_breakdown=score_breakdown,
        agent_id=agent.id,
    )
    credibility = float(claim_diagnostics["credibility"])
    closer = _resolution_phrase(
        state=state,
        social_context_label=social_context_label,
        credibility=credibility,
        primary_decision_anchor=primary_decision_anchor,
        gap=gap,
        score_breakdown=score_breakdown,
        agent_id=agent.id,
    )
    first = (
        f"{opening} {demographic_clause} In this case, {gap}."
        if "In this case" not in opening
        else f"{opening} {demographic_clause} {gap}."
    )
    return [first, second, closer]


def _build_k2_batch_payload_item(
    *,
    analysis_text: str,
    domain: str,
    case_goal: str,
    claim_diagnostics: dict[str, float | str],
    item: dict[str, Any],
) -> dict[str, Any]:
    agent = item["agent"]
    traits: _Traits = item["traits"]
    state = _state_from_score(item["final_score"], float(claim_diagnostics["credibility"]))
    return {
        "id": agent.id,
        "name": agent.name,
        "role": agent.role,
        "role_lens": _role_reasoning_lens(agent.role),
        "domain_context": DOMAIN_CONTEXT.get(domain, domain),
        "scenario": _compress_ws(analysis_text)[:700],
        "case_goal": case_goal,
        "precomputed_outcome": state.title(),
        "dominant_signal_hint": item["default_signal"],
        "primary_decision_anchor": _primary_decision_anchor(
            traits=traits,
            claim_diagnostics=claim_diagnostics,
            score_breakdown=item["score_breakdown"],
        ),
        "claim_credibility": round(float(claim_diagnostics["credibility"]), 3),
        "claim_harm": round(float(claim_diagnostics["harm"]), 3),
        "claim_virality": round(float(claim_diagnostics.get("virality", 0.0)), 3),
        "local_adoption_ratio": round(float(item["local_adoption_ratio"]), 3),
        "supportive_neighbors": int(item["supportive_neighbors"]),
        "total_neighbors": int(item["total_neighbors"]),
        "social_context_label": _social_context_label(
            int(item["supportive_neighbors"]),
            int(item["total_neighbors"]),
            float(item["local_adoption_ratio"]),
        ),
        "baseline_score": round(float(item["baseline_score"]), 3),
        "final_score": round(float(item["final_score"]), 3),
        "traits": {
            "evidence_literacy": round(float(traits.evidence_literacy), 3),
            "peer_susceptibility": round(float(traits.peer_susceptibility), 3),
            "identity_sensitivity": round(float(traits.identity_sensitivity), 3),
            "institutional_trust": round(float(traits.institutional_trust), 3),
            "analytic_scrutiny": round(float(traits.analytic_scrutiny), 3),
            "baseline_openness": round(float(traits.baseline_openness), 3),
        },
        "bsv": {key: round(float(value), 3) for key, value in item["bsv"].items()},
        "brain_regions": {key: round(float(value), 3) for key, value in item["regions"].items()},
        "score_breakdown": {key: round(float(value), 3) for key, value in item["score_breakdown"].items()},
    }


async def _resolve_k2_reasoning_map(
    httpx_client: httpx.AsyncClient,
    *,
    analysis_text: str,
    domain: str,
    case_goal: str,
    claim_diagnostics: dict[str, float | str],
    computed_agents: list[dict[str, Any]],
    chunk_size: int = 8,
) -> dict[int, dict[str, Any]]:
    requests = [
        _build_k2_batch_payload_item(
            analysis_text=analysis_text,
            domain=domain,
            case_goal=case_goal,
            claim_diagnostics=claim_diagnostics,
            item=item,
        )
        for item in computed_agents
    ]
    reasoning_map: dict[int, dict[str, Any]] = {}
    for chunk in _chunked(requests, chunk_size):
        reasoning_map.update(
            await call_k2_batch_think(
                httpx_client,
                agents=chunk,
            )
        )
    return reasoning_map


def _chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def _timeline_prompt_item(agent: dict[str, Any], round_item: dict[str, Any]) -> dict[str, Any]:
    demographics = agent.get("demographics") or {}
    pipeline = agent.get("_pipeline") or {}
    return {
        "agent_id": int(agent["id"]),
        "round": int(round_item["round"]),
        "name": agent["name"],
        "role": agent["role"],
        "belief_state": round_item["belief_state"],
        "confidence": round(float(round_item["confidence"]), 3),
        "confidence_delta": round(float(round_item.get("confidence_delta") or 0.0), 3),
        "dominant_signal": agent["dominant_signal"],
        "demographics": demographics,
        "traits": pipeline.get("traits", {}),
        "conditioning": pipeline.get("conditioning", {}),
        "trigger_metrics": {
            "supportive_pressure": round_item.get("supportive_pressure"),
            "skeptical_pressure": round_item.get("skeptical_pressure"),
            "messenger_alignment": round_item.get("messenger_alignment"),
        },
        "existing_phase_label": round_item.get("phase_label"),
        "existing_trigger": round_item.get("trigger"),
        "existing_post": round_item.get("post"),
        "existing_change_summary": round_item.get("change_summary"),
    }


async def _render_timeline_language(
    httpx_client: httpx.AsyncClient,
    *,
    agents: list[dict[str, Any]],
    chunk_size: int = 12,
) -> dict[tuple[int, int], dict[str, str]]:
    items: list[dict[str, Any]] = []
    for agent in agents:
        for round_item in agent.get("round_history", []):
            items.append(_timeline_prompt_item(agent, round_item))

    rendered: dict[tuple[int, int], dict[str, str]] = {}
    for chunk in _chunked(items, chunk_size):
        rendered.update(await call_k2_timeline_batch(httpx_client, items=chunk))
    return rendered


def _materialize_agent_result(
    *,
    agent: _Virt,
    bsv: BSV,
    regions: dict[str, float],
    traits: _Traits,
    conditioning: dict[str, float],
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
        "demographics": {
            "age_band": agent.demographics.age_band,
            "age_years": agent.demographics.age_years,
            "education_level": agent.demographics.education_level,
            "income_band": agent.demographics.income_band,
            "housing_status": agent.demographics.housing_status,
            "language_profile": agent.demographics.language_profile,
            "community_tenure": agent.demographics.community_tenure,
            "caregiving_load": agent.demographics.caregiving_load,
            "digital_media_habit": agent.demographics.digital_media_habit,
            "summary": _demographic_profile_summary(agent.demographics),
        },
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
            "vulnerability": _demographic_vulnerability(agent.demographics, parsed_signal),
            "cause_of_state": reasoning[0] if reasoning else _signal_summary(parsed_signal, state, regions),
            "best_intervention": _intervention_hint(parsed_signal),
        },
        "_pipeline": {
            "traits": traits.__dict__,
            "conditioning": {k: round(float(v), 3) for k, v in conditioning.items()},
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
    pipeline_started = time.perf_counter()

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
            batch_agents = [
                {
                    "id": agent.id,
                    "role": agent.role,
                    "latitude": agent.lat,
                    "longitude": agent.lng,
                    "demographics": {
                        "age_band": agent.demographics.age_band,
                        "age_years": agent.demographics.age_years,
                        "education_level": agent.demographics.education_level,
                        "income_band": agent.demographics.income_band,
                        "housing_status": agent.demographics.housing_status,
                        "language_profile": agent.demographics.language_profile,
                        "community_tenure": agent.demographics.community_tenure,
                        "caregiving_load": agent.demographics.caregiving_load,
                        "digital_media_habit": agent.demographics.digital_media_habit,
                    },
                }
                for agent in population
            ]
            tribe_batch = await _timed(
                "tribe_batch",
                call_tribe_modal_batch(httpx_client, analysis_text, batch_agents),
            )
            tribe_results = tribe_batch["agents"]
            tribe_meta = _augment_tribe_meta(tribe_batch.get("tribe_meta") or {})
            tribe_composites = tribe_meta.get("composites") if isinstance(tribe_meta.get("composites"), dict) else {}
            baseline_herding = float(tribe_composites.get("herding", 0.0))
            baseline_approach = float(tribe_composites.get("approach_avoid", 0.0))
            baseline_regulation = float(tribe_composites.get("regulation", 0.0))
            baseline_reactivity = float(tribe_composites.get("reactivity", 0.0))
            per_agent_surface = tribe_meta.get("per_agent")
            if not isinstance(per_agent_surface, dict):
                per_agent_surface = {}

            def _agent_composite_biases(agent_id: int) -> tuple[float, float, float, float]:
                entry = per_agent_surface.get(str(agent_id))
                if isinstance(entry, dict) and isinstance(entry.get("composites"), dict):
                    comp = entry["composites"]
                    return (
                        float(comp.get("herding", baseline_herding)),
                        float(comp.get("approach_avoid", baseline_approach)),
                        float(comp.get("regulation", baseline_regulation)),
                        float(comp.get("reactivity", baseline_reactivity)),
                    )
                return baseline_herding, baseline_approach, baseline_regulation, baseline_reactivity

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

            conditioning_map = {agent.id: _agent_conditioning(agent, city_id) for agent in population}
            trait_map = {agent.id: _agent_traits(agent, city_id) for agent in population}
            baseline_scores: dict[int, float] = {}
            baseline_breakdowns: dict[int, dict[str, float]] = {}
            for agent in population:
                raw_region = regions_by_id[agent.id]
                herding_bias, approach_bias, regulation_bias, reactivity_bias = _agent_composite_biases(agent.id)
                baseline_score, breakdown = _baseline_uptake_score(
                    analysis_text=analysis_text,
                    domain=domain,
                    bsv=raw_region.bsv,
                    traits=trait_map[agent.id],
                    claim_diagnostics=claim_diagnostics,
                )
                baseline_score = _clamp(
                    baseline_score
                    + max(0.0, herding_bias - 0.45) * trait_map[agent.id].peer_susceptibility * 0.05
                    + max(0.0, approach_bias) * trait_map[agent.id].baseline_openness * 0.045
                    - max(0.0, -regulation_bias) * trait_map[agent.id].analytic_scrutiny * 0.03
                    + (0.02 if reactivity_bias <= -1.0 else -0.012 if reactivity_bias >= 1.0 else 0.0),
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
                fh, fa, fr, fre = _agent_composite_biases(agent.id)
                final_score = _clamp(
                    final_score
                    + max(0.0, fh - 0.45) * local_adoption_ratio * 0.08
                    + max(0.0, fa) * resonance * 0.05
                    - max(0.0, -fr) * adjusted_bsv["defensive_posture"] * 0.035
                    + (0.018 if fre <= -1.0 else -0.014 if fre >= 1.0 else 0.0),
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
                        "conditioning": conditioning_map[agent.id],
                        "baseline_score": baseline_scores[agent.id],
                        "final_score": final_score,
                        "local_adoption_ratio": local_adoption_ratio,
                        "score_breakdown": merged_breakdown,
                        "default_signal": signal,
                        "supportive_neighbors": nearby_adopters,
                        "total_neighbors": nearby_total,
                        "resonance": resonance,
                    }
                )

            claim_credibility = float(claim_diagnostics["credibility"])
            agents: list[dict[str, Any]]
            if settings.ifm_api_key.strip() and settings.ifm_api_url.strip():
                try:
                    elapsed = time.perf_counter() - pipeline_started
                    remaining_budget = settings.simulate_total_timeout_seconds - elapsed
                    reasoning_timeout = min(30.0, max(0.0, remaining_budget - 28.0))
                    if reasoning_timeout < 5.0:
                        raise TimeoutError(
                            f"Skipping K2 batch reasoning because only {remaining_budget:.2f}s remain in the pipeline budget."
                        )
                    reasoning_map = await _timed(
                        "agent_reasoning",
                        asyncio.wait_for(
                            _resolve_k2_reasoning_map(
                                httpx_client,
                                analysis_text=analysis_text,
                                domain=domain,
                                case_goal=case_goal,
                                claim_diagnostics=claim_diagnostics,
                                computed_agents=computed_agents,
                            ),
                            timeout=reasoning_timeout,
                        ),
                    )
                    agents = [
                        _materialize_agent_result(
                            agent=item["agent"],
                            bsv=item["bsv"],
                            regions=item["regions"],
                            traits=item["traits"],
                            conditioning=item["conditioning"],
                            baseline_score=item["baseline_score"],
                            final_score=item["final_score"],
                            local_adoption_ratio=item["local_adoption_ratio"],
                            score_breakdown=item["score_breakdown"],
                            claim_credibility=claim_credibility,
                            raw_reasoning=reasoning_map.get(
                                item["agent"].id,
                                _fallback_reasoning_payload(item=item, claim_credibility=claim_credibility),
                            ),
                            default_signal=item["default_signal"],
                        )
                        for item in computed_agents
                    ]
                except Exception as exc:
                    logger.exception("Agent reasoning render failed; falling back to local explanatory traces.")
                    stage_trace.append(
                        {
                            "stage": "agent_reasoning",
                            "seconds": 0.0,
                            "status": "fallback",
                            "error": str(exc)[:240],
                        }
                    )
                    agents = [
                        _materialize_agent_result(
                            agent=item["agent"],
                            bsv=item["bsv"],
                            regions=item["regions"],
                            traits=item["traits"],
                            conditioning=item["conditioning"],
                            baseline_score=item["baseline_score"],
                            final_score=item["final_score"],
                            local_adoption_ratio=item["local_adoption_ratio"],
                            score_breakdown=item["score_breakdown"],
                            claim_credibility=claim_credibility,
                            raw_reasoning=_fallback_reasoning_payload(item=item, claim_credibility=claim_credibility),
                            default_signal=item["default_signal"],
                        )
                        for item in computed_agents
                    ]
            else:
                agents = [
                    _materialize_agent_result(
                        agent=item["agent"],
                        bsv=item["bsv"],
                        regions=item["regions"],
                        traits=item["traits"],
                        conditioning=item["conditioning"],
                        baseline_score=item["baseline_score"],
                        final_score=item["final_score"],
                        local_adoption_ratio=item["local_adoption_ratio"],
                        score_breakdown=item["score_breakdown"],
                        claim_credibility=claim_credibility,
                        raw_reasoning=_fallback_reasoning_payload(item=item, claim_credibility=claim_credibility),
                        default_signal=item["default_signal"],
                    )
                    for item in computed_agents
                ]
            agents.sort(key=lambda agent: agent["id"])
            swarm_dynamics = _build_swarm_dynamics_langgraph(
                analysis_text=analysis_text,
                population=population,
                agents=agents,
                claim_credibility=claim_credibility,
            )
            per_agent_history = swarm_dynamics["per_agent_history"]
            for agent in agents:
                agent["round_history"] = per_agent_history.get(agent["id"], [])

            if settings.ifm_api_key.strip() and settings.ifm_api_url.strip():
                try:
                    elapsed = time.perf_counter() - pipeline_started
                    remaining_budget = settings.simulate_total_timeout_seconds - elapsed
                    timeline_timeout = min(24.0, max(0.0, remaining_budget - 12.0))
                    if timeline_timeout < 3.0:
                        raise TimeoutError(
                            f"Skipping timeline language because only {remaining_budget:.2f}s remain in the pipeline budget."
                        )
                    timeline_language = await _timed(
                        "timeline_language",
                        asyncio.wait_for(
                            _render_timeline_language(httpx_client, agents=agents, chunk_size=8),
                            timeout=timeline_timeout,
                        ),
                    )
                    for agent in agents:
                        for round_item in agent.get("round_history", []):
                            rendered = timeline_language.get((int(agent["id"]), int(round_item["round"])))
                            if not rendered:
                                continue
                            round_item["phase_label"] = rendered["phase_label"]
                            round_item["trigger"] = rendered["trigger"]
                            round_item["post"] = rendered["post"]
                            round_item["change_summary"] = rendered["change_summary"]
                except Exception as exc:
                    logger.exception("Timeline language render failed; keeping structural fallback text.")
                    stage_trace.append(
                        {
                            "stage": "timeline_language",
                            "seconds": 0.0,
                            "status": "fallback",
                            "error": str(exc)[:240],
                        }
                    )

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
                            "demographics": agent.get("demographics", {}),
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
