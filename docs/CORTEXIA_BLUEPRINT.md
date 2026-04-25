# Cortexia: Project Blueprint and Architecture Guidelines

This document is the canonical reference for **what Cortexia is**, **how data should flow**, and **how to extend the codebase**. Implementation in this repository may lag the target architecture in places; see **§6 Current implementation map**.

---

## 1. Core Identity and Vision

Cortexia is an advanced **predictive modeling engine for information epidemiology**.

- **What it is:** A zero-shot cognitive simulation platform that stress-tests messaging (policy, PR, campaigns) against a **synthetic, geographically mapped population**.
- **What it is NOT:** A generic LLM wrapper, a sentiment analysis tool, or a copywriting assistant. There are no polls or questionnaires in the product framing.
- **The goal:** Map how an idea propagates through demographic networks, estimate localized **cognitive friction** and **belief resistance** before a message is deployed in the real world.

---

## 2. Tech Stack

| Layer | Technology |
|--------|------------|
| **Frontend** | React + TypeScript, Vite, Tailwind CSS, Mapbox / Deck.gl (this repo; Lovable or Next.js is acceptable in other forks) |
| **Backend** | FastAPI (Python), SQLite (runtime) with a path to Postgres for simulation history at scale |
| **Distributed compute** | **Modal** for highly concurrent agent simulations and TRIBE-style extraction (see `modal_app.py`) |
| **External AI** | **K2 Think API** (logical reasoning: adopt / reject, reasoning trace), **Tribe** (neurological benchmark: BSV / cognitive load / friction metrics) |

**Separation of concerns**

- **React** handles UI, client state, and visualization only.
- **FastAPI** handles HTTP routing, persistence, orchestration, and returns shaped JSON to the client.
- **Modal** (target) runs heavy, parallel per-agent or batch work without blocking the API process.

---

## 3. UI/UX Rules

- **Aesthetic:** Dark-themed, enterprise-grade dashboard.
- **Colors:** Dark backgrounds, **at most three** pastel-leaning accent colors.
- **Prohibited:** No emojis in the UI or source strings. No hackathon or one-off event branding in product copy.
- **Layout**
  - **Left:** Dynamic catalyst input (raw text, optional URL) and city / targeting parameters.
  - **Center:** Interactive geographic network map (nodes = synthetic agents; color by propagation outcome).
  - **No** bottom navigation or status bar consuming map space.
  - **Node inspection:** Modal or panel with Tribe-oriented brain visualization and K2 reasoning trace.

---

## 4. Data Pipeline (Canonical, Chronological)

Features should be designed to fit this flow end to end.

### Step 1: Injection (frontend to backend)

- User supplies the **catalyst** (message text) and **target city** (or equivalent targeting parameters).
- The client sends **`POST /api/simulate`** with a JSON body. Conceptually: `catalyst_text`, `target_city` (in this repo the field is `city_id`; see §6).

### Step 2: Orchestration (FastAPI, optional Modal dispatch)

- FastAPI **accepts** the payload, **persists** a simulation record when history is required, and **orchestrates** the run.
- **Target architecture:** Return quickly to the client and **dispatch** a Modal job (queue / webhook) so the main server is not CPU-bound.
- **Current note:** The reference implementation may run a synchronous or in-process worker for development; production should move long runs to Modal.

### Step 3: Simulation runtime (Modal and APIs)

- **Target:** Modal runs a concurrent Python job: build the geographic **network of agents** for the selected city’s priors.
- For each agent (or batch), the runtime coordinates:
  1. **K2 Think:** Agent profile + catalyst, producing adopt / reject (or equivalent) and a **logical reasoning trace**.
  2. **Tribe:** Input derived from the interaction / catalyst, producing **neurological / BSV** metrics (cognitive load, defensive activation, and related fields).

**Resilience:** All external calls (K2, Tribe, Modal) must have timeouts, retries where appropriate, and clear degradation paths (structured errors, not silent failure).

### Step 4: Aggregation and response (back to the client)

- Results are **aggregated** into a single **PropagationReport-shaped** response: per-node outcomes, summary statistics, and fields required by the report panel.
- FastAPI returns JSON to the frontend. If using async jobs, the client may poll or subscribe (WebSocket) until the run is complete; the **same** final payload shape applies.

### Step 5: Visualization (frontend)

- The **map** updates: node color encodes K2 (or derived) **adopt / reject / neutral** state.
- **Agent inspection** shows Tribe metrics on a brain-style graphic and the **K2 reasoning trace** as text for that node.

---

## 5. Development Rules

1. **Reference this pipeline** to decide where new code belongs (client vs API vs Modal vs external API client).
2. **Preserve boundaries:** UI does not implement business rules that belong in the orchestrator; the API does not own Deck.gl or Mapbox logic.
3. **Production quality:** Type hints in Python, typed contracts for API payloads, error handling and timeouts for K2, Tribe, and Modal.

---

## 6. Current implementation map (this repository)

This section ties the blueprint to the code as it exists today; update it when the architecture moves toward full Modal job dispatch and DB logging of every run.

| Blueprint concept | Code / file |
|-------------------|-------------|
| `POST /api/simulate` | `backend/app/main.py` `SimulateIn` (`catalyst_text`, `city_id`, `source_url`, `use_case`, `message_complexity`) |
| `target_city` | Implemented as `city_id` (presets in `backend/app/city_presets.py`, `frontend/src/data/cities.ts`) |
| K2 Think client | `backend/app/services/ai_clients.py` `call_k2_think` (K2 base URL and model in `app.config`) |
| Tribe (BSV) | `call_tribe_modal` in `ai_clients.py`; Modal app in `modal_app.py` |
| Per-agent HTTP simulation bundle | `backend/app/services/api_simulation.py` `run_simulation_http` |
| Frontend inject + map + inspection | `SimulationInputPanel`, `MapView`, `AgentInspectionModal`; state + `postSimulate` in `frontend/src/lib/api/simulate.ts` and `store/cortex.ts` |
| WebSocket (optional broadcast) | `backend/app/main.py` `/api/simulation/ws` |
| **Gap vs target** | Full simulation may still run **in-process** on FastAPI for `/api/simulate` instead of a non-blocking Modal fan-out; DB logging of every `POST /api/simulate` is not yet mandatory in the handler |

---

## 7. Changelog

- **2026-04-25:** Initial blueprint committed as project documentation.
