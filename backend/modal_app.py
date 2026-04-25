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

Copy the **HTTPS** URL for `TribeExtractor.extract_batch_bsv` (label `extract-batch-bsv`)
and put it in the orchestrator’s env as `TRIBE_MODAL_URL` (e.g. in `backend/.env`).

## Dev / smoke-test without a full deploy

    modal serve modal_app.py

Hot-reloads; prints a URL. **POST JSON** body:
`{"catalyst_text": "hello", "agents": [{"id": 0, "role": "test", "latitude": 34.0, "longitude": -118.0}]}`.

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
from typing import Any

import modal
from fastapi import FastAPI
from pydantic import BaseModel

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = modal.App("cortexia-tribe-v2")
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch",
    "transformers",
    "numpy",
    "fastapi",
    "pydantic",
)

class AgentData(BaseModel):
    id: int
    role: str
    latitude: float
    longitude: float

class BatchRequest(BaseModel):
    catalyst_text: str
    agents: list[AgentData]


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
    @modal.fastapi_endpoint(method="POST", label="extract-batch-bsv")
    async def extract_batch_bsv(self, request: BatchRequest) -> dict[str, Any]:
        """Simulate audio/text → fMRI tensor → 4D Biological State Vector via conditional mapping."""
        h = int(hashlib.sha256(request.catalyst_text.encode("utf-8")).hexdigest()[:8], 16)
        rng = random.Random(h)
        
        # Base translation for the text
        base_cl = 0.3 + 0.65 * rng.random()
        base_ea = 0.2 + 0.7 * rng.random()
        base_dp = 0.25 + 0.7 * rng.random()
        base_ws = 0.2 + 0.75 * rng.random()

        results = {}
        for a in request.agents:
            agent_rng = random.Random(h + a.id)
            # Conditional mapping (simulate LFCM): Adjust based on role
            role_mod_dp = 0.1 if "Civil" in a.role or "Worker" in a.role else 0.0
            role_mod_cl = 0.15 if "Analyst" in a.role or "Engineer" in a.role else 0.0

            bsv = {
                "cognitive_load": max(0.0, min(1.0, round(base_cl + role_mod_cl + 0.1 * (agent_rng.random() - 0.5), 2))),
                "emotional_agitation": max(0.0, min(1.0, round(base_ea + 0.15 * (agent_rng.random() - 0.5), 2))),
                "defensive_posture": max(0.0, min(1.0, round(base_dp + role_mod_dp + 0.2 * (agent_rng.random() - 0.5), 2))),
                "working_memory_strain": max(0.0, min(1.0, round(base_ws + 0.1 * (agent_rng.random() - 0.5), 2))),
            }
            results[str(a.id)] = bsv
        
        return {"agents": results}
