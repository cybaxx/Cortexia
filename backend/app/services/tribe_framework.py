"""Local adapter for the vendored `tribe_neural` framework.

This module treats the framework as Cortexia's primary TRIBE processing engine.
It runs one stimulus-level neural pass, derives structured region/composite data,
and maps those outputs into the BSV fields consumed by the existing swarm model.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
from functools import lru_cache
from typing import Any, TypedDict

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


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


def _derive_bsv(stats: dict[str, dict[str, float]], composites: dict[str, float]) -> FrameworkBSV:
    fear = stats["fear_salience"]
    deliberation = stats["deliberation"]
    attention = stats.get("attention", {})
    reward = stats["reward_limbic"]

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
        "cognitive_load": round(cognitive_load, 6),
        "emotional_agitation": round(emotional_agitation, 6),
        "defensive_posture": round(defensive_posture, 6),
        "working_memory_strain": round(working_memory_strain, 6),
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
    bsv = _derive_bsv(stats, composites)

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

    result = await asyncio.to_thread(_pipeline_once, text)
    base_bsv = result["bsv"]
    by_agent = {str(agent["id"]): dict(base_bsv) for agent in agents}

    return {
        "agents": by_agent,
        "tribe_meta": {
            "provider": "tribe_neural_framework",
            "model_id": "facebook/tribev2",
            "derivation_version": "tribe_neural_composites_v1",
            "input_mode": "text_path",
            "pred_shape": result["pred_shape"],
            "signal_confidence": result["signal_confidence"],
            "dominant_roi": result["dominant_roi"],
            "composites": result["composites"],
            "roi_stats": result["roi_stats"],
            "connectivity": result["connectivity"],
            "formatted_state": result["formatted_state"],
            "data_dir": result["data_dir"],
        },
    }
