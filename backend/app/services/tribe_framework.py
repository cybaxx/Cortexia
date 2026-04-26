"""Local adapter for the vendored `tribe_neural` framework.

This module treats the framework as Cortexia's primary TRIBE processing engine.
It runs one stimulus-level neural pass, derives structured region/composite data,
and maps those outputs into the BSV fields consumed by the existing swarm model.

Per-agent personalization: ROI summary statistics (peak, mean, auc, etc.) are
copied and scaled from demographics + role, then composites are recomputed so
BSV and downstream composite biases stay consistent with the same math as the
neural pipeline.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import math
import os
from functools import lru_cache
from typing import Any, TypedDict

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_FLOAT_STAT_KEYS = frozenset({"peak", "mean", "auc", "rise_slope", "cv", "decay_slope"})


class FrameworkBSV(TypedDict):
    cognitive_load: float
    emotional_agitation: float
    defensive_posture: float
    working_memory_strain: float


class FrameworkBatchResult(TypedDict):
    agents: dict[str, FrameworkBSV]
    tribe_meta: dict[str, Any]


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def _ensure_runtime_env() -> None:
    if not settings.hf_token:
        raise RuntimeError(
            "HF_TOKEN is required for TRIBE framework mode. Export HF_TOKEN or add it to backend/.env."
        )
    os.environ.setdefault("HF_TOKEN", settings.hf_token)
    os.environ.setdefault("TRIBE_DATA_DIR", settings.tribe_data_dir)


@lru_cache(maxsize=1)
def _load_resources_cached() -> Any:
    _ensure_runtime_env()
    try:
        from tribe_neural.init_resources import load_resources
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "TRIBE framework dependencies are not installed. Run backend/scripts/setup_tribe_framework.sh first."
        ) from exc

    logger.info("Loading vendored tribe_neural resources from %s", settings.tribe_data_dir)
    return load_resources()


def _demographic_modulators(demographics: Any) -> dict[str, float]:
    """Map Cortexia demographic fields to 0–1 scalars (aligned with swarm conditioning)."""
    demo = demographics if isinstance(demographics, dict) else {}
    education_support = {
        "High school": 0.12,
        "Some college": 0.24,
        "Associate": 0.34,
        "Bachelor's": 0.48,
        "Master's": 0.6,
        "Professional/Doctoral": 0.7,
    }.get(str(demo.get("education_level") or ""), 0.3)
    economic_strain = {
        "Upper middle income": 0.12,
        "Middle income": 0.26,
        "Lower middle income": 0.48,
        "Economically strained": 0.72,
    }.get(str(demo.get("income_band") or ""), 0.4)
    housing_flux = {
        "Homeowner": 0.12,
        "Stable renter": 0.28,
        "Multigenerational household": 0.34,
        "Housing insecure": 0.7,
    }.get(str(demo.get("housing_status") or ""), 0.3)
    language_bridge = {
        "English-dominant": 0.1,
        "Bilingual English-Spanish": 0.44,
        "English plus household language": 0.3,
        "Multilingual household": 0.56,
    }.get(str(demo.get("language_profile") or ""), 0.2)
    community_embeddedness = {
        "Recent arrival": 0.14,
        "Established resident": 0.42,
        "Long-term resident": 0.66,
        "Deeply rooted local": 0.84,
    }.get(str(demo.get("community_tenure") or ""), 0.4)
    caregiving_pressure = {
        "Low caregiving load": 0.12,
        "Shared caregiving": 0.36,
        "Primary caregiver": 0.68,
    }.get(str(demo.get("caregiving_load") or ""), 0.2)
    media_velocity = {
        "Local-news heavy": 0.2,
        "Group-chat heavy": 0.58,
        "Public-feed heavy": 0.66,
        "Mixed verification habit": 0.32,
    }.get(str(demo.get("digital_media_habit") or ""), 0.3)
    age_index = {
        "18-24": 0.32,
        "25-34": 0.46,
        "35-44": 0.56,
        "45-54": 0.62,
        "55-64": 0.66,
        "65+": 0.6,
    }.get(str(demo.get("age_band") or ""), 0.5)
    age_years = demo.get("age_years")
    if isinstance(age_years, (int, float)):
        age_index = _clamp(float(age_years) / 85.0, 0.12, 0.92)
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


def _roi_scale_factors(d: dict[str, float], agent: dict[str, Any]) -> dict[str, float]:
    """Per-ROI multipliers (~0.78–1.28) from demographics and role."""

    def clip(m: float) -> float:
        return _clamp(m, 0.78, 1.28)

    es = d["economic_strain"]
    edu = d["education_support"]
    lang = d["language_bridge"]
    cp = d["caregiving_pressure"]
    mv = d["media_velocity"]
    emb = d["community_embeddedness"]
    hf = d["housing_flux"]
    age = d["age_index"]

    fear_m = 1.0 + 0.20 * es + 0.10 * hf + 0.10 * cp - 0.08 * edu + 0.06 * mv
    reward_m = 1.0 - 0.12 * es + 0.10 * emb + 0.04 * max(0.0, 0.55 - age)
    deliberation_m = 1.0 + 0.22 * (edu - 0.38) + 0.06 * max(0.0, age - 0.52)
    social_m = 1.0 + 0.12 * emb + 0.10 * mv - 0.06 * es
    action_m = 1.0 + 0.08 * mv + 0.06 * es + 0.05 * cp
    attention_m = 1.0 + 0.20 * lang + 0.12 * es + 0.10 * cp + 0.06 * mv

    role = str(agent.get("role") or "").lower()
    if any(token in role for token in ("analyst", "engineer", "research")):
        deliberation_m += 0.08
        attention_m += 0.05
        fear_m -= 0.06
    if any(token in role for token in ("health", "educator", "responder")):
        deliberation_m += 0.04
        social_m += 0.05
    if any(token in role for token in ("journal", "organizer", "policy")):
        social_m += 0.06
        attention_m += 0.03

    return {
        "fear_salience": clip(fear_m),
        "reward_limbic": clip(reward_m),
        "deliberation": clip(deliberation_m),
        "social_default": clip(social_m),
        "action_motor": clip(action_m),
        "attention": clip(attention_m),
    }


def _scale_roi_stat_dict(roi_stats: dict[str, Any], factor: float) -> dict[str, Any]:
    scaled = dict(roi_stats)
    for key in _FLOAT_STAT_KEYS:
        if key in scaled and isinstance(scaled[key], (int, float)):
            scaled[key] = float(scaled[key]) * factor
    return scaled


def _copy_roi_stats(stats: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(stats)


def _modulate_roi_stats(stats: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
    d = _demographic_modulators(agent.get("demographics"))
    factors = _roi_scale_factors(d, agent)
    out: dict[str, Any] = {}
    for roi_name, roi_block in stats.items():
        if not isinstance(roi_block, dict):
            out[roi_name] = roi_block
            continue
        factor = float(factors.get(str(roi_name), 1.0))
        out[str(roi_name)] = _scale_roi_stat_dict(roi_block, factor)
    return out


def _derive_bsv(stats: dict[str, dict[str, float]], composites: dict[str, float]) -> FrameworkBSV:
    fear = stats["fear_salience"]
    deliberation = stats["deliberation"]
    attention = stats.get("attention", {})

    cognitive_load = _clamp(
        _sigmoid(
            1.35 * float(attention.get("auc", 0.0))
            + 0.95 * float(deliberation.get("auc", 0.0))
            + 0.45 * float(fear.get("cv", 0.0))
            - 1.2
        )
    )
    emotional_agitation = _clamp(
        _sigmoid(
            1.2 * float(composites.get("arousal", 0.0))
            - 0.8 * float(composites.get("valence", 0.0))
            + 0.55 * float(fear.get("peak", 0.0))
            - 1.0
        )
    )
    defensive_posture = _clamp(
        _sigmoid(
            1.3 * float(fear.get("auc", 0.0))
            + 0.9 * max(0.0, -float(composites.get("dominance", 0.0)))
            + 0.65 * max(0.0, -float(composites.get("regulation", 0.0)))
            - 1.1
        )
    )
    working_memory_strain = _clamp(
        _sigmoid(
            0.9 * float(deliberation.get("peak", 0.0))
            + 1.0 * float(attention.get("auc", 0.0))
            + 0.55 * float(deliberation.get("cv", 0.0))
            - 1.15
        )
    )

    return {
        "cognitive_load": cognitive_load,
        "emotional_agitation": emotional_agitation,
        "defensive_posture": defensive_posture,
        "working_memory_strain": working_memory_strain,
    }


def _round_bsv(bsv: FrameworkBSV) -> FrameworkBSV:
    return {
        "cognitive_load": round(float(bsv["cognitive_load"]), 6),
        "emotional_agitation": round(float(bsv["emotional_agitation"]), 6),
        "defensive_posture": round(float(bsv["defensive_posture"]), 6),
        "working_memory_strain": round(float(bsv["working_memory_strain"]), 6),
    }


def _pipeline_once(text: str) -> dict[str, Any]:
    resources = _load_resources_cached()

    from tribe_neural.steps.step1_tribe import run_tribe
    from tribe_neural.steps.step2_roi import extract_all
    from tribe_neural.steps.step3_stats import extract_stats
    from tribe_neural.steps.step4_connectivity import compute_connectivity
    from tribe_neural.steps.step5_composites import compute_composites
    from tribe_neural.steps.step6_format import format_output

    preds = run_tribe(text, resources.model)
    if preds.shape[0] > 4:
        preds = preds[:-2]

    roi_ts = extract_all(preds, resources.masks, resources.weight_maps, resources.signatures)
    stats = {name: extract_stats(ts) for name, ts in roi_ts.items()}
    connectivity = compute_connectivity(roi_ts)
    composites = compute_composites(stats, connectivity)
    formatted = format_output(stats, connectivity, composites, roi_ts)
    bsv = _round_bsv(_derive_bsv(stats, composites))

    return {
        "bsv": bsv,
        "formatted_state": formatted,
        "roi_stats": stats,
        "connectivity": connectivity,
        "composites": composites,
        "pred_shape": [int(preds.shape[0]), int(preds.shape[1])],
        "signal_confidence": round(float(composites.get("confidence", 0.0)), 4),
        "dominant_roi": max(stats, key=lambda key: float(stats[key].get("peak", 0.0))),
        "data_dir": settings.tribe_data_dir,
    }


async def run_framework_batch(catalyst_text: str, agents: list[dict[str, Any]]) -> FrameworkBatchResult:
    text = catalyst_text.strip()
    if not text:
        raise RuntimeError("TRIBE framework requires non-empty catalyst text.")
    if not agents:
        raise RuntimeError("TRIBE framework batch requires at least one agent.")

    from tribe_neural.steps.step5_composites import compute_composites

    result = await asyncio.to_thread(_pipeline_once, text)
    stats_baseline = result["roi_stats"]
    connectivity = result["connectivity"]
    default_dominant = result["dominant_roi"]

    by_agent: dict[str, FrameworkBSV] = {}
    per_agent: dict[str, Any] = {}

    for agent in agents:
        mod_stats = _modulate_roi_stats(_copy_roi_stats(stats_baseline), agent)
        comp_i = compute_composites(mod_stats, connectivity)
        raw_bsv = _derive_bsv(mod_stats, comp_i)
        aid = str(agent["id"])
        by_agent[aid] = _round_bsv(raw_bsv)

        roi_dicts = [k for k in mod_stats if isinstance(mod_stats.get(k), dict)]
        dominant = default_dominant
        if roi_dicts:
            dominant = max(roi_dicts, key=lambda k: float(mod_stats[k].get("peak", 0.0)))

        per_agent[aid] = {
            "composites": comp_i,
            "dominant_roi": dominant,
            "signal_confidence": round(float(comp_i.get("confidence", 0.0)), 4),
        }

    return {
        "agents": by_agent,
        "tribe_meta": {
            "provider": "tribe_neural_framework",
            "model_id": "facebook/tribev2",
            "derivation_version": "tribe_neural_roi_stats_v1_demographics",
            "input_mode": "text_path",
            "pred_shape": result["pred_shape"],
            "signal_confidence": result["signal_confidence"],
            "dominant_roi": result["dominant_roi"],
            "composites": result["composites"],
            "roi_stats": result["roi_stats"],
            "connectivity": result["connectivity"],
            "formatted_state": result["formatted_state"],
            "data_dir": result["data_dir"],
            "baseline_bsv": result["bsv"],
            "per_agent": per_agent,
            "surface_scope": "stimulus_baseline",
        },
    }