"""
Modal deployment for Cortexia's vendored TRIBE framework.

This service runs the `tribe_neural` pipeline on Modal GPU infrastructure and
returns a stimulus-level BSV plus richer neural metadata for Cortexia.

It is intended to replace local heavy neuro installs on macOS.
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import Any

import modal
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

APP_NAME = "cortexia-tribe-framework"
CACHE_DIR = "/cache/tribe_data"
REMOTE_BACKEND_SRC = "/root/backend_src"
LLAMA_REPO_ID = "meta-llama/Llama-3.2-3B"
TRIBE_REPO_ID = "facebook/tribev2"


def _load_hf_token() -> str:
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
    if token:
        return token

    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("HF_TOKEN="):
                return line.split("=", 1)[1].strip()
            if line.startswith("HUGGINGFACE_TOKEN="):
                return line.split("=", 1)[1].strip()
    return ""


HF_TOKEN_VALUE = _load_hf_token()
deploy_secrets: list[modal.Secret] = []
if HF_TOKEN_VALUE:
    deploy_secrets.append(modal.Secret.from_dict({"HF_TOKEN": HF_TOKEN_VALUE}))

app = modal.App(APP_NAME)
cache_volume = modal.Volume.from_name("cortexia-tribe-framework-cache", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg", "espeak-ng")
    .pip_install(
        "fastapi[standard]==0.115.12",
        "numpy==2.2.6",
        "pandas==2.2.3",
        "scipy==1.15.3",
        "torch==2.6.0",
        "torchvision==0.21.0",
        "transformers==4.46.1",
        "tokenizers==0.20.3",
        "huggingface_hub==0.26.2",
        "nibabel==5.3.2",
        "nilearn==0.10.4",
        "nimare==0.5.5",
        "edge-tts==7.2.8",
        "matplotlib==3.10.0",
        "pyarrow==18.1.0",
        "mne==1.12.1",
        "mne_bids==0.18.0",
        "pyprep==0.6.0",
        "torchmetrics==1.6.1",
        "x_transformers==1.27.20",
        "moviepy==2.1.2",
        "gtts==2.5.4",
        "spacy==3.8.2",
        "soundfile==0.12.1",
        "Levenshtein==0.26.1",
        "julius==0.2.7",
        "einops==0.8.0",
        "exca==0.5.22",
        "neuralset==0.0.2",
        "neuraltrain==0.0.2",
        "polars==1.40.1",
        "ujson==5.12.0",
        "tqdm==4.67.3",
        "scikit-learn==1.8.0",
    )
    .run_commands("python -m pip install --no-deps git+https://github.com/facebookresearch/tribev2.git")
    .add_local_python_source("tribe_neural", copy=True)
)


class AgentData(BaseModel):
    id: int
    role: str
    latitude: float
    longitude: float


class BatchRequest(BaseModel):
    catalyst_text: str = Field(min_length=3)
    agents: list[AgentData] = Field(min_length=1)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def _derive_bsv(stats: dict[str, dict[str, float]], composites: dict[str, float]) -> dict[str, float]:
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
        "cognitive_load": round(cognitive_load, 6),
        "emotional_agitation": round(emotional_agitation, 6),
        "defensive_posture": round(defensive_posture, 6),
        "working_memory_strain": round(working_memory_strain, 6),
    }


@app.cls(
    gpu="A10G",
    image=image,
    volumes={CACHE_DIR: cache_volume},
    secrets=deploy_secrets,
    scaledown_window=300,
    timeout=60 * 20,
)
class TribeFrameworkService:
    @modal.enter()
    def load_resources(self) -> None:
        hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")
        if not hf_token:
            raise RuntimeError("HF_TOKEN is required inside the Modal container.")

        os.environ["HF_TOKEN"] = hf_token
        os.environ["HUGGINGFACE_TOKEN"] = hf_token
        os.environ["HUGGINGFACE_HUB_TOKEN"] = hf_token
        os.environ.setdefault("TRIBE_DATA_DIR", CACHE_DIR)
        os.environ.setdefault("HF_HOME", f"{CACHE_DIR}/hf_home")
        os.environ.setdefault("HUGGINGFACE_HUB_CACHE", f"{CACHE_DIR}/hf_home/hub")

        try:
            from huggingface_hub import login, model_info, snapshot_download

            login(token=hf_token, add_to_git_credential=False)
            logger.info("Authenticated with Hugging Face hub inside Modal container")
            model_info(LLAMA_REPO_ID, token=hf_token)
            logger.info("Verified access to gated repo %s", LLAMA_REPO_ID)
            snapshot_download(
                repo_id=LLAMA_REPO_ID,
                token=hf_token,
                cache_dir=os.environ["HUGGINGFACE_HUB_CACHE"],
                local_files_only=False,
                resume_download=True,
            )
            logger.info("Warm-cached %s into %s", LLAMA_REPO_ID, os.environ["HUGGINGFACE_HUB_CACHE"])
            snapshot_download(
                repo_id=TRIBE_REPO_ID,
                token=hf_token,
                cache_dir=os.environ["HUGGINGFACE_HUB_CACHE"],
                local_files_only=False,
                resume_download=True,
            )
            logger.info("Warm-cached %s into %s", TRIBE_REPO_ID, os.environ["HUGGINGFACE_HUB_CACHE"])
        except Exception as exc:
            raise RuntimeError(
                f"Hugging Face preflight failed for {LLAMA_REPO_ID}. "
                "The token must belong to an account with approved access."
            ) from exc

        from tribe_neural.init_resources import load_resources

        logger.info("Loading tribe_neural resources into %s", CACHE_DIR)
        self.resources = load_resources()
        logger.info("tribe_neural resources loaded")

    def _run_pipeline(self, text: str) -> dict[str, Any]:
        from tribe_neural.steps.step1_tribe import run_tribe
        from tribe_neural.steps.step2_roi import extract_all
        from tribe_neural.steps.step3_stats import extract_stats
        from tribe_neural.steps.step4_connectivity import compute_connectivity
        from tribe_neural.steps.step5_composites import compute_composites
        from tribe_neural.steps.step6_format import format_output

        preds = run_tribe(text, self.resources.model)
        if preds.shape[0] > 4:
            preds = preds[:-2]

        roi_ts = extract_all(
            preds,
            self.resources.masks,
            self.resources.weight_maps,
            self.resources.signatures,
        )
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
            "dominant_roi": max(stats, key=lambda key: float(stats[key].get("peak", 0.0))),
            "signal_confidence": round(float(composites.get("confidence", 0.0)), 4),
        }

    @modal.fastapi_endpoint(method="POST", label="extract-batch-bsv-framework")
    async def extract_batch_bsv(self, request: BatchRequest) -> dict[str, Any]:
        text = request.catalyst_text.strip()
        if not text:
            raise ValueError("catalyst_text must not be empty.")

        result = self._run_pipeline(text)
        base_bsv = result["bsv"]
        agents = {str(agent.id): dict(base_bsv) for agent in request.agents}

        return {
            "agents": agents,
            "tribe_meta": {
                "provider": "tribe_neural_framework_modal",
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
                "data_dir": CACHE_DIR,
            },
        }
