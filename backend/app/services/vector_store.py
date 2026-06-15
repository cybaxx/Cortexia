"""
Lightweight vector database for semantic search over simulations, agents, and interventions.

Uses ChromaDB (SQLite-backed, no server) with Ollama's nomic-embed-text for embeddings.
Falls back gracefully to empty results if ChromaDB or Ollama are unavailable.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
VECTOR_DB_DIR = BACKEND_DIR / "vector_db"
EMBED_MODEL = "nomic-embed-text:latest"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"

# ── Lazy init ──────────────────────────────────────────────────────

_client: chromadb.ClientAPI | None = None
_available: bool | None = None  # True if both ChromaDB and Ollama are working


def _get_client() -> chromadb.ClientAPI | None:
    global _client, _available
    if _available is False:
        return None
    if _client is not None:
        return _client
    try:
        VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(VECTOR_DB_DIR),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        # Quick smoke test
        _ = _client.get_or_create_collection("health_check")
        _client.delete_collection("health_check")
        _available = True
        logger.info("Vector store ready at %s", VECTOR_DB_DIR)
        return _client
    except Exception as exc:
        _available = False
        _client = None
        logger.warning("Vector store unavailable: %s", exc)
        return None


def is_available() -> bool:
    _get_client()
    return _available is True


# ── Embedding ──────────────────────────────────────────────────────

def _normalize(vec: list[float]) -> list[float]:
    """L2-normalize a vector to unit length."""
    norm = math.sqrt(sum(v * v for v in vec))
    if norm < 1e-10:
        return vec
    return [v / norm for v in vec]


def _embed(text: str) -> list[float] | None:
    """Call Ollama's nomic-embed-text to get a 768-dim normalized embedding."""
    import httpx
    try:
        r = httpx.post(
            OLLAMA_EMBED_URL,
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=15.0,
        )
        r.raise_for_status()
        emb = r.json().get("embedding")
        if emb:
            return _normalize(emb)
        return None
    except Exception as exc:
        logger.debug("Embedding failed: %s", exc)
        return None


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts. Returns empty embeddings for failures."""
    results: list[list[float]] = []
    for text in texts:
        emb = _embed(text)
        results.append(emb if emb else [])
    return results


# ── Collections ────────────────────────────────────────────────────

def _get_collection(name: str):
    client = _get_client()
    if client is None:
        return None
    return client.get_or_create_collection(name)


# ── Run indexing ───────────────────────────────────────────────────

def index_run(
    run_id: int,
    case_goal: str,
    analysis_text: str,
    domain: str,
    city_id: str,
    risk_level: str | None,
    adoption_rate: float | None,
) -> bool:
    """Index a simulation run for semantic search."""
    doc = f"{case_goal}. {analysis_text}. Domain: {domain}. City: {city_id}."
    emb = _embed(doc[:2000])
    if emb is None:
        return False

    col = _get_collection("cortexia_runs")
    if col is None:
        return False

    try:
        col.upsert(
            ids=[str(run_id)],
            embeddings=[emb],
            documents=[doc],
            metadatas=[{
                "run_id": run_id,
                "domain": domain,
                "city_id": city_id,
                "risk_level": risk_level or "",
                "adoption_rate": adoption_rate or 0.0,
            }],
        )
        logger.debug("Indexed run #%d in vector store", run_id)
        return True
    except Exception as exc:
        logger.warning("Failed to index run #%d: %s", run_id, exc)
        return False


def search_runs(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Semantic search over indexed simulation runs."""
    emb = _embed(query)
    if emb is None:
        return []

    col = _get_collection("cortexia_runs")
    if col is None:
        return []

    try:
        results = col.query(query_embeddings=[emb], n_results=min(limit, 25))
        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        out: list[dict[str, Any]] = []
        ids = results["ids"][0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i in range(len(ids)):
            meta = metas[i] if i < len(metas) else {}
            dist = distances[i] if i < len(distances) else 2.0
            # L2 on unit vectors: 0 = identical, 2 = opposite. Convert to 0-1 similarity.
            similarity = max(0.0, min(1.0, 1.0 - dist / 2.0))
            out.append({
                "run_id": int(meta.get("run_id", ids[i])),
                "domain": meta.get("domain", ""),
                "city_id": meta.get("city_id", ""),
                "risk_level": meta.get("risk_level", ""),
                "similarity": round(similarity, 3),
                "snippet": (docs[i] if i < len(docs) else "")[:200],
            })
        return out
    except Exception as exc:
        logger.warning("Vector search failed: %s", exc)
        return []


def index_agent(
    run_id: int,
    agent: dict[str, Any],
) -> bool:
    """Index a single agent for cross-run similarity search."""
    name = agent.get("name", "")
    role = agent.get("role", "")
    bsv = agent.get("tribe_neurological_metrics") or {}
    regions = agent.get("brain_regions") or {}
    demog = agent.get("demographics") or {}
    traits = (agent.get("_pipeline") or {}).get("traits") or {}
    outcome = f"state={agent.get('belief_state','?')} conf={agent.get('k2_decision_confidence',0):.2f}"

    doc = (
        f"Agent {name}, {role}. "
        f"BSV: cog={bsv.get('cognitive_load',0):.2f} emo={bsv.get('emotional_friction',0):.2f} "
        f"def={bsv.get('defensive_activation',0):.2f} wm={bsv.get('working_memory_strain',0):.2f}. "
        f"Brain: {', '.join(f'{k}={v:.2f}' for k,v in regions.items())}. "
        f"Demographics: {demog.get('summary','')}. "
        f"Traits: {', '.join(f'{k}={v:.2f}' for k,v in traits.items())}. "
        f"Outcome: {outcome}."
    )
    emb = _embed(doc[:2000])
    if emb is None:
        return False

    col = _get_collection("cortexia_agents")
    if col is None:
        return False

    agent_id = agent.get("id", 0)
    uid = f"{run_id}_{agent_id}"

    try:
        col.upsert(
            ids=[uid],
            embeddings=[emb],
            documents=[doc],
            metadatas=[{
                "run_id": run_id,
                "agent_id": agent_id,
                "name": name,
                "role": role,
                "belief_state": agent.get("belief_state", ""),
                "confidence": agent.get("k2_decision_confidence", 0.0),
            }],
        )
        return True
    except Exception as exc:
        logger.debug("Failed to index agent %s: %s", uid, exc)
        return False


def search_similar_agents(
    query_text: str,
    k: int = 5,
    exclude_run_id: int | None = None,
) -> list[dict[str, Any]]:
    """Find similar agents from past runs given a text profile."""
    emb = _embed(query_text)
    if emb is None:
        return []

    col = _get_collection("cortexia_agents")
    if col is None:
        return []

    try:
        results = col.query(query_embeddings=[emb], n_results=min(k + 5, 25))
        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        out: list[dict[str, Any]] = []
        ids = results["ids"][0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i in range(len(ids)):
            meta = metas[i] if i < len(metas) else {}
            if exclude_run_id and int(meta.get("run_id", 0)) == exclude_run_id:
                continue
            dist = distances[i] if i < len(distances) else 2.0
            # L2 on unit vectors: 0 = identical, 2 = opposite. Convert to 0-1 similarity.
            similarity = max(0.0, min(1.0, 1.0 - dist / 2.0))
            out.append({
                "agent_id": int(meta.get("agent_id", 0)),
                "run_id": int(meta.get("run_id", 0)),
                "name": meta.get("name", ""),
                "role": meta.get("role", ""),
                "belief_state": meta.get("belief_state", ""),
                "confidence": meta.get("confidence", 0.0),
                "similarity": round(similarity, 3),
            })
            if len(out) >= k:
                break
        return out
    except Exception as exc:
        logger.debug("Agent similarity search failed: %s", exc)
        return []


def index_all_existing_runs() -> int:
    """Index all existing persisted runs at startup."""
    if not is_available():
        return 0

    from app.pipeline_store import list_recent_runs, fetch_case_run
    runs = list_recent_runs(limit=100)
    indexed = 0

    for run in runs:
        rid = run["id"]
        try:
            record = fetch_case_run(rid)
            if not record:
                continue
            response = record.get("response") or record
            cs = response.get("case_summary", {})
            sm = response.get("spread_model", {})
            ok = index_run(
                run_id=rid,
                case_goal=run.get("case_goal", ""),
                analysis_text=record.get("analysis_text", ""),
                domain=run.get("domain", ""),
                city_id=run.get("city_id", ""),
                risk_level=sm.get("spread_risk") or cs.get("spread_risk"),
                adoption_rate=float(sm.get("belief_adoption_rate", 0)),
            )
            if ok:
                indexed += 1
        except Exception:
            pass

    logger.info("Indexed %d existing runs into vector store", indexed)
    return indexed
