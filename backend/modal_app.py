"""
TRIBE v2 BSV extraction on Modal (serverless A10G).

## One-time: Modal account & CLI (deploy / serve)

You need a Modal account and a **token on this machine** to deploy. This is **not** the
same as HTTP headers your FastAPI app might send later (see “Calling the API”).

1. Install: `pip install modal`
2. Log in: `modal setup`  (or legacy: `modal token new` — store token in `~/.modal.toml`)
3. That token authorizes the **Modal CLI** only (deploy, logs, `modal run`, etc.).

## Deploy to Modal

From this directory (`backend/`):

    modal deploy modal_app.py

Copy the **HTTPS** URL for `TribeExtractor.extract_bsv` (or `extract-bsv` if labeled)
and put it in the orchestrator’s env as `TRIBE_MODAL_URL` (e.g. in `backend/.env`).

## Dev / smoke-test without a full deploy

    modal serve modal_app.py

Hot-reloads; prints a URL you can curl with a multipart `file` field.

## Calling the API (FastAPI / curl)

- **Default** public web endpoints: no `Modal-Key` / `Modal-Secret` headers.
- If you set `requires_proxy_auth=True` on the endpoint in code, you must set
  `TRIBE_MODAL_KEY` and `TRIBE_MODAL_SECRET` in the **orchestrator** env to the same
  id/secret shown in the Modal dashboard (or `modal token new` / workspace token),
  and our `ai_clients.call_tribe_modal` will add the headers for you.

## Real model vs this file

The implementation below is still a **hash-seeded random BSV** (fast for demos). If you
replaced `load_model` / `extract_bsv` with a real TRIBE or HF pipeline, keep it here and
re-deploy with `modal deploy`.
"""

from __future__ import annotations

import hashlib
import logging
import random

import modal
from fastapi import File, UploadFile

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = modal.App("cortexia-tribe-v2")
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch",
    "transformers",
    "numpy",
    "fastapi",
    "python-multipart",
)


@app.cls(gpu="A10G", image=image)
class TribeExtractor:
    """MVP: mock `facebook/tribev2` load, deterministic pseudo-BSV from catalyst bytes."""

    @modal.enter()
    def load_model(self) -> None:
        logger.info("Reserving GPU; mock-loading TRIBE v2 (facebook/tribev2) weights")
        # MVP: no real download — structure mirrors production warm-container load.
        self._model_id = "facebook/tribev2"
        _ = self._model_id  # would reference loaded tensors in full implementation

    # Same FastAPI semantics as legacy @modal.web_endpoint.
    @modal.fastapi_endpoint(method="POST", label="extract-bsv")
    async def extract_bsv(self, file: UploadFile = File(...)) -> dict[str, float]:
        """Simulate audio/text → fMRI tensor → 4D Biological State Vector."""
        raw = await file.read()
        h = int(hashlib.sha256(raw).hexdigest()[:8], 16)
        rng = random.Random(h)
        bsv = {
            "cognitive_load": round(0.3 + 0.65 * rng.random(), 2),
            "emotional_agitation": round(0.2 + 0.7 * rng.random(), 2),
            "defensive_posture": round(0.25 + 0.7 * rng.random(), 2),
            "working_memory_strain": round(0.2 + 0.75 * rng.random(), 2),
        }
        return bsv
