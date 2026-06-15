"""Live research and final-step action-center synthesis.

Supports three provider tiers:
1. Tavily + Firecrawl (paid APIs) — when keys are configured
2. Local web (DuckDuckGo + trafilatura) — free, no API keys needed
3. Simulation-only fallback — when no web access is available
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from app.city_presets import get_city
from app.config import get_settings
from app.services.ai_clients import call_k2_action_center
from app.services.local_research import (
    build_fallback_patterns,
    extract_page_content,
    search_web,
)

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass(frozen=True)
class ProviderStatus:
    enabled: bool
    mode: str
    detail: str


def action_center_provider_status() -> dict[str, dict[str, str | bool]]:
    has_paid_search = bool(settings.tavily_api_key.strip())
    has_paid_extract = bool(settings.firecrawl_api_key.strip())
    local_web_enabled = not has_paid_search  # auto-enable when no paid API

    return {
        "tavily": _provider(
            enabled=has_paid_search,
            mode="live-search" if has_paid_search else "disabled",
            detail="Broad web search for current evidence (paid API)."
            if has_paid_search
            else "Set TAVILY_API_KEY to enable premium search.",
        ),
        "firecrawl": _provider(
            enabled=has_paid_extract,
            mode="structured-extract" if has_paid_extract else "disabled",
            detail="Structured extraction from selected URLs (paid API)."
            if has_paid_extract
            else "Set FIRECRAWL_API_KEY to enable premium extraction.",
        ),
        "local_web": _provider(
            enabled=local_web_enabled,
            mode="active" if local_web_enabled else "disabled",
            detail="Free DuckDuckGo search + trafilatura content extraction — no API key needed."
            if local_web_enabled
            else "Disabled because paid search is active.",
        ),
        "k2": _provider(
            enabled=bool(settings.ifm_api_key.strip() and settings.ifm_api_url.strip()),
            mode="synthesis" if settings.ifm_api_key.strip() and settings.ifm_api_url.strip() else "disabled",
            detail="Operational synthesis and action planning."
            if settings.ifm_api_key.strip() and settings.ifm_api_url.strip()
            else "Set IFM_API_KEY to enable final-step synthesis.",
        ),
        "browser_use": _provider(
            enabled=True,
            mode="operator-assisted",
            detail="Recommended for manual verification of high-value dynamic pages surfaced by the dossier.",
        ),
    }


def _provider(*, enabled: bool, mode: str, detail: str) -> dict[str, str | bool]:
    return {"enabled": enabled, "mode": mode, "detail": detail}


async def build_action_center_research(
    httpx_client: httpx.AsyncClient,
    *,
    domain: str,
    city_id: str,
    case_goal: str,
    scenario: str,
    spread_risk: str | None = None,
    key_finding: str | None = None,
    dominant_pathway: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    city = get_city(city_id)
    provider_status = action_center_provider_status()
    queries = _build_queries(
        domain=domain,
        city_label=city.label,
        scenario=scenario,
        case_goal=case_goal,
    )

    search_results: list[dict[str, Any]] = []
    if settings.tavily_api_key.strip():
        search_results = await _run_tavily(httpx_client, queries)
    else:
        search_results = await search_web(httpx_client, queries)

    extracted_patterns: list[dict[str, Any]] = []
    if settings.firecrawl_api_key.strip() and search_results:
        extracted_patterns = await _run_firecrawl(httpx_client, search_results, city_label=city.label)
    elif search_results:
        extracted_patterns = await _extract_local(httpx_client, search_results)

    if not extracted_patterns:
        extracted_patterns = build_fallback_patterns(search_results)

    synthesis_input = {
        "domain": domain,
        "city": city.label,
        "case_goal": case_goal,
        "scenario": scenario[:1800],
        "spread_risk": spread_risk or "unknown",
        "key_finding": key_finding or "",
        "dominant_pathway": dominant_pathway or "",
        "operator_notes": (notes or "")[:1200],
        "queries": queries,
        "provider_status": provider_status,
        "live_sources": [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "domain": item.get("domain", urlparse(item.get("url", "")).netloc),
                "snippet": item.get("snippet", ""),
                "raw_excerpt": item.get("raw_excerpt", item.get("snippet", "")),
            }
            for item in search_results[: settings.action_center_max_sources]
        ],
        "extracted_patterns": extracted_patterns[: settings.action_center_max_sources],
    }

    synthesis = await _synthesize_action_center(httpx_client, synthesis_input)

    return {
        "provider_status": provider_status,
        "queries": queries,
        "sources": search_results[: settings.action_center_max_sources],
        "extracted_patterns": extracted_patterns[: settings.action_center_max_sources],
        "brief": {
            "headline": synthesis["headline"],
            "executive_summary": synthesis["executive_summary"],
            "decision_window": synthesis["decision_window"],
            "urgency": synthesis["urgency"],
            "confidence_note": synthesis["confidence_note"],
        },
        "recommended_actions": synthesis["recommended_actions"],
        "monitoring_queries": synthesis["monitoring_queries"],
        "source_briefings": synthesis["source_briefings"],
        "browser_verification_queue": synthesis["browser_verification_queue"],
    }


def _build_queries(*, domain: str, city_label: str, scenario: str, case_goal: str) -> list[str]:
    compact = " ".join(scenario.split())
    seed = compact[:220]
    domain_label = domain.replace("_", " ")
    return [
        f"{seed} {city_label}",
        f"{domain_label} misinformation {city_label} {seed}",
        f"{case_goal[:160]} {city_label} narrative response",
    ]


async def _run_tavily(httpx_client: httpx.AsyncClient, queries: list[str]) -> list[dict[str, Any]]:
    seen_urls: set[str] = set()
    merged: list[dict[str, Any]] = []
    headers = {
        "Authorization": f"Bearer {settings.tavily_api_key}",
        "Content-Type": "application/json",
    }

    for query in queries:
        try:
            response = await httpx_client.post(
                "https://api.tavily.com/search",
                headers=headers,
                json={
                    "query": query,
                    "topic": "general",
                    "max_results": min(5, settings.action_center_max_sources),
                    "include_raw_content": "markdown",
                    "include_answer": False,
                    "include_favicon": True,
                },
                timeout=settings.action_center_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning("Tavily search failed for query %r: %s", query, exc)
            continue

        for item in payload.get("results") or []:
            url = str(item.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            merged.append(
                {
                    "title": str(item.get("title") or _hostname(url)),
                    "url": url,
                    "domain": _hostname(url),
                    "snippet": str(item.get("content") or "")[:420],
                    "raw_excerpt": str(item.get("raw_content") or "")[:1200],
                    "favicon": item.get("favicon"),
                    "score": float(item.get("score") or 0.0),
                }
            )

    return merged[: settings.action_center_max_sources]


async def _run_firecrawl(
    httpx_client: httpx.AsyncClient,
    tavily_results: list[dict[str, Any]],
    *,
    city_label: str,
) -> list[dict[str, Any]]:
    urls = [item["url"] for item in tavily_results[: min(4, len(tavily_results))]]
    if not urls:
        return []

    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "claim": {"type": "string"},
                        "risk_level": {"type": "string"},
                        "geography": {"type": "string"},
                        "why_it_matters": {"type": "string"},
                        "evidence": {"type": "string"},
                    },
                    "required": ["url", "claim", "risk_level", "why_it_matters"],
                },
            }
        },
        "required": ["items"],
    }
    try:
        response = await httpx_client.post(
            "https://api.firecrawl.dev/v2/extract",
            headers={
                "Authorization": f"Bearer {settings.firecrawl_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "urls": urls,
                "prompt": (
                    f"Extract the main claim or narrative from each page, the local geography relevance to {city_label}, "
                    "why the page matters for a misinformation or narrative-spread review, and a concise evidence note."
                ),
                "schema": schema,
            },
            timeout=settings.action_center_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        logger.warning("Firecrawl extraction failed: %s", exc)
        return []

    data = payload.get("data") or {}
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "url": str(item.get("url") or ""),
                "claim": str(item.get("claim") or ""),
                "risk_level": str(item.get("risk_level") or "Moderate"),
                "geography": str(item.get("geography") or ""),
                "why_it_matters": str(item.get("why_it_matters") or ""),
                "evidence": str(item.get("evidence") or ""),
            }
        )
    return out


async def _extract_local(
    httpx_client: httpx.AsyncClient,
    search_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract page content from search results using trafilatura (free, no API)."""
    out: list[dict[str, Any]] = []
    for item in search_results[: min(4, len(search_results))]:
        url = item.get("url", "")
        if not url:
            continue
        content = await extract_page_content(httpx_client, url)
        snippet = item.get("snippet", "")
        out.append({
            "url": url,
            "claim": _first_sentence(content) if content else snippet[:220],
            "risk_level": "Moderate",
            "geography": item.get("domain", urlparse(url).netloc),
            "why_it_matters": (
                content[:300] if content
                else f"Could not extract full content from {urlparse(url).netloc}. Using search snippet as fallback."
            ),
            "evidence": content[:600] if content else snippet[:300],
        })
    return out


def _first_sentence(text: str) -> str:
    """Extract the first meaningful sentence from extracted text."""
    cleaned = text.strip()
    for delim in (". ", ".\n", "! ", "?\n", "\n\n"):
        idx = cleaned.find(delim)
        if idx > 20:
            return cleaned[: idx + 1].strip()
    return cleaned[:300]


def _fallback_patterns_from_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in results:
        snippet = str(item.get("snippet") or item.get("raw_excerpt") or "").strip()
        if not snippet:
            continue
        out.append(
            {
                "url": item["url"],
                "claim": snippet[:220],
                "risk_level": "Moderate",
                "geography": item.get("domain") or "",
                "why_it_matters": f"Surface match from {item.get('domain')}.",
                "evidence": snippet[:300],
            }
        )
    return out[: settings.action_center_max_sources]


async def _synthesize_action_center(httpx_client: httpx.AsyncClient, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        result = await call_k2_action_center(httpx_client, payload=payload)
        if isinstance(result, dict):
            return {
                "headline": str(result.get("headline") or "Action Center brief"),
                "executive_summary": str(result.get("executive_summary") or ""),
                "decision_window": str(result.get("decision_window") or "Next 24-72 hours"),
                "urgency": str(result.get("urgency") or "medium").lower(),
                "confidence_note": str(result.get("confidence_note") or ""),
                "recommended_actions": _normalize_actions(result.get("recommended_actions")),
                "monitoring_queries": _normalize_strings(result.get("monitoring_queries")),
                "source_briefings": _normalize_source_briefings(result.get("source_briefings")),
                "browser_verification_queue": _normalize_browser_queue(result.get("browser_verification_queue")),
            }
    except Exception as exc:
        logger.warning("Action Center K2 synthesis failed, using heuristic fallback: %s", exc)

    spread_risk = str(payload.get("spread_risk") or "Moderate")
    key_finding = str(payload.get("key_finding") or "The simulation shows a narrative that deserves monitoring.")
    dominant_pathway = str(payload.get("dominant_pathway") or "social proof")
    case_goal = str(payload.get("case_goal") or "").strip()
    live_sources = payload.get("live_sources") or []
    return {
        "headline": f"{spread_risk} risk scenario in {payload.get('city')}",
        "executive_summary": (
            f"Goal: {case_goal}. {key_finding}"
            if case_goal
            else key_finding
        ),
        "decision_window": "Next 24-72 hours",
        "urgency": "high" if spread_risk.lower() == "high" else "medium",
        "confidence_note": (
            "Live research providers are limited or unavailable, so this brief leans more heavily on the simulation output."
            if not live_sources
            else "This brief combines the simulation with a lightweight live-source pass."
        ),
        "recommended_actions": [
            {
                "title": "Prepare first-response messaging",
                "owner": "Comms lead",
                "audience": "High-risk segments",
                "timeline": "Today",
                "action": (
                    f"Draft one plain-language response aligned to the dominant pathway: {dominant_pathway}. "
                    f"Shape it to the stated goal: {case_goal}."
                    if case_goal
                    else f"Draft one plain-language response aligned to the dominant pathway: {dominant_pathway}."
                ),
                "why_now": "The simulation shows this is the clearest first intervention lever for the stated objective." if case_goal else "The simulation shows this is the clearest first intervention lever.",
            },
            {
                "title": "Monitor local amplification",
                "owner": "Research or trust team",
                "audience": payload.get("city") or "target city",
                "timeline": "Next 24 hours",
                "action": "Track whether the scenario is appearing in local news, forums, or advocacy channels.",
                "why_now": "Early detection matters more than late-stage rebuttal, especially if the team needs to act on the intake goal quickly." if case_goal else "Early detection matters more than late-stage rebuttal.",
            },
        ],
        "monitoring_queries": _build_queries(
            domain=str(payload.get("domain") or "general"),
            city_label=str(payload.get("city") or "target region"),
            scenario=str(payload.get("scenario") or ""),
            case_goal=str(payload.get("case_goal") or ""),
        ),
        "source_briefings": [
            {
                "url": item.get("url", ""),
                "why_it_matters": f"Matched the scenario search on {item.get('domain')}.",
                "credibility_note": "Needs human review."
            }
            for item in live_sources[:3]
        ],
        "browser_verification_queue": [
            {
                "url": item.get("url", ""),
                "reason": "High-value source for manual verification.",
                "check_for": "Specific local claims, dates, and whether the page is being updated."
            }
            for item in live_sources[:3]
        ],
    }


def _normalize_actions(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "title": str(item.get("title") or ""),
                "owner": str(item.get("owner") or ""),
                "audience": str(item.get("audience") or ""),
                "timeline": str(item.get("timeline") or ""),
                "action": str(item.get("action") or ""),
                "why_now": str(item.get("why_now") or ""),
            }
        )
    return out


def _normalize_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_source_briefings(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "url": str(item.get("url") or ""),
                "why_it_matters": str(item.get("why_it_matters") or ""),
                "credibility_note": str(item.get("credibility_note") or ""),
            }
        )
    return out


def _normalize_browser_queue(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "url": str(item.get("url") or ""),
                "reason": str(item.get("reason") or ""),
                "check_for": str(item.get("check_for") or ""),
            }
        )
    return out


def _hostname(url: str) -> str:
    try:
        parsed = urlparse(url)
        return parsed.netloc or url
    except Exception:
        return url
