# Cortexia

Predictive information epidemiology — stress-test a claim against a synthetic, geo-mapped population using neural state modeling, LLM agent reasoning, and multi-round swarm simulation.

---

## Quick start

### Prerequisites

- **Python 3.11 or 3.12** + **Node.js 18+**
- **Hugging Face token** ([free](https://huggingface.co/settings/tokens)) — for one-time Llama 3.2 model download
- **Mapbox token** ([free tier](https://account.mapbox.com/)) — for basemap tiles (optional: renders without it)

### 1. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash scripts/setup_tribe_framework.sh
cp .env.example .env
# Edit .env: add HF_TOKEN, adjust settings
uvicorn app.main:app --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env
# Add VITE_MAPBOX_TOKEN (optional)
npm run dev
```

Open **http://localhost:5173**. Enter evidence text (12+ chars), pick a city and domain, click **Simulate**. Pipeline takes 3–8 minutes.

### cURL alternative

```bash
curl -X POST http://127.0.0.1:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "Political Campaign",
    "city_id": "los-angeles-ca",
    "case_goal": "Assess spread risk",
    "message_complexity": 0.6,
    "evidence": {
      "text_input": "The city quietly approved a plan to convert 3 public parks into homeless encampments without consulting residents.",
      "speaker_context": "A neighborhood Facebook post claims city hall is hiding the plan."
    }
  }'
```

---

## How it works

```
Evidence → TRIBE neural pipeline (6 steps) → per-agent brain state vectors
                                                    ↓
                                          LFCM calibration (demographics × geography)
                                                    ↓
                               Uptake scoring + LLM reasoning traces
                                                    ↓
                              LangGraph multi-agent swarm (3+ rounds)
                                                    ↓
                           SQLite persistence → JSON → React dashboard
```

### The 11-stage pipeline

| Stage | Description |
|-------|-------------|
| 1. Population | Synthetic agents with demographics, roles, geo-coordinates |
| 2. Evidence | Source text → analysis → claim diagnostics |
| 3. TRIBE neural | 6-step: cortical predictions → ROI timeseries → 11 stats → 7 connectivities → 8 composites → narrative |
| 4. LFCM calibration | Maps BSV through role, demographics, political lean |
| 5. Region derivation | PFC, Amygdala, Insula, Hippocampus, ACC, TPJ |
| 6. Uptake scoring | Baseline + final (adopted / rejected / neutral) |
| 7. Agent reasoning | LLM (K2 or Ollama) — per-agent explanation traces |
| 8. Swarm propagation | LangGraph multi-agent, 3+ rounds, cyber exposure |
| 9. Workspace assembly | Spread model, mechanisms, intervention playbook |
| 10. Persistence | SQLite (5 tables) |
| 11. Response | JSON → frontend dashboard (map, brain viz, interventions) |

---

## Run entirely locally (no external APIs)

| Component | Local fallback | Config |
|-----------|---------------|--------|
| TRIBE neural | Runs locally by default | `TRIBE_RUNTIME_MODE=framework` |
| Agent reasoning | Ollama (`llama3.2` or `llama3.1:8b`) | `IFM_API_KEY=ollama` |
| Swarm decisions | Heuristic engine (automatic) | No config needed |
| Action Center | Simulation-only data (automatic) | No config needed |
| Map basemap | Dark basemap renders without token | Mapbox token optional |

```bash
ollama pull llama3.2    # 2 GB, fast
# or
ollama pull llama3.1:8b # 4.9 GB, better quality
```

Then in `backend/.env`:

```env
IFM_API_KEY=ollama
IFM_API_URL=http://localhost:11434/v1/chat/completions
IFM_K2_MODEL=llama3.2:latest
```

---

## Configuration

### Backend (`backend/.env`)

| Key | Default | Description |
|-----|---------|-------------|
| `TRIBE_RUNTIME_MODE` | `framework` | `framework` (local) or `modal` (remote GPU) |
| `TRIBE_DEVICE` | auto | `mps`, `cuda`, or `cpu` |
| `HF_TOKEN` | *required* | Hugging Face token for model access |
| `simulate_population_size` | `72` | Agents per simulation (24–220) |
| `simulate_total_timeout_seconds` | `180` | Pipeline timeout (max 900) |
| `simulate_tribe_timeout_seconds` | `120` | TRIBE batch timeout |
| `simulate_k2_timeout_seconds` | `90` | Per-agent LLM timeout |
| `simulate_k2_concurrency` | `10` | Concurrent LLM calls (1–32) |
| `IFM_API_KEY` | `""` | LLM API key (use `ollama` for local) |
| `IFM_API_URL` | `https://api.k2think.ai/v1/chat/completions` | LLM endpoint |
| `IFM_K2_MODEL` | `MBZUAI-IFM/K2-Think-v2` | Model name |

### Frontend (`frontend/.env`)

| Key | Description |
|-----|-------------|
| `VITE_MAPBOX_TOKEN` | Mapbox token for basemap tiles (optional) |
| `VITE_API_BASE_URL` | Backend URL (default: `http://127.0.0.1:8000`) |

---

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/simulate` | Run a full case simulation |
| `POST` | `/api/transcribe` | Transcribe audio evidence |
| `GET` | `/api/runs/recent` | List recent simulation runs |
| `GET` | `/api/runs/{id}` | Load a persisted run |
| `GET` | `/api/runs/{id}/agents/{agent_id}/profile` | Agent profile |
| `GET` | `/api/runs/{id}/agents/{agent_id}/conversation` | Agent chat history |
| `POST` | `/api/runs/{id}/agents/{agent_id}/conversation` | Send message to agent |
| `GET` | `/api/populations/{city_id}/agents` | List synthetic population |
| `GET` | `/api/action-center/status` | Research provider config |
| `POST` | `/api/action-center/research` | Run web research dossier |
| `GET` | `/api/audio/{filename}` | Serve TTS audio files |

---

## Project structure

```
Cortexia/
├── backend/
│   ├── app/
│   │   ├── main.py                    FastAPI app, CORS, lifespan
│   │   ├── config.py                  Pydantic settings (22 fields)
│   │   ├── pipeline_store.py          SQLite CRUD
│   │   ├── population_store.py        Agent population persistence
│   │   ├── political_geography.py     Partisan lean + GeoJSON
│   │   ├── city_presets.py            City land zones + coordinates
│   │   └── services/
│   │       ├── api_simulation.py       Core orchestrator (~4700 lines)
│   │       ├── tribe_framework.py      TRIBE adapter + demographic modulation
│   │       ├── langgraph_multi_agent_sim.py  LangGraph swarm
│   │       ├── ai_clients.py           K2 / Ollama / TTS / STT clients
│   │       ├── action_center.py        Live research provider
│   │       ├── local_research.py       DuckDuckGo + trafilatura
│   │       ├── shared_math.py          clamp(), sigmoid()
│   │       └── vector_store.py         ChromaDB indexing
│   ├── tribe_neural/                  Vendored 6-step TRIBE pipeline
│   ├── tests/                          pytest (27 test cases)
│   ├── scripts/                        Setup, batch, export utilities
│   └── examples/                       Example JSON payloads
├── frontend/
│   ├── src/
│   │   ├── pages/                     Index, NotFound
│   │   ├── components/cortex/          Dashboard, MapView, BrainViz, etc.
│   │   ├── components/ui/             shadcn/ui (Radix-based)
│   │   ├── store/cortex.ts            Zustand state
│   │   ├── lib/api/simulate.ts        API client
│   │   ├── types/simulation.ts        TypeScript types
│   │   └── test/                      Vitest (26 store tests)
│   ├── vite.config.ts                 Vite config (port 5173, proxy)
│   └── tailwind.config.ts
└── docs/
    ├── ARCHITECTURE.md                 System design + data flow
    ├── TROUBLESHOOTING.md             Common issues
    └── ACTION_PLAN.md                  Technical debt tracker
```

---

## Testing

```bash
# Backend
cd backend && source .venv/bin/activate
pytest tests/                    # 27 test cases

# Frontend
cd frontend
npm run test                     # 26 store tests
npm run lint                     # ESLint
```

---

## Platform support

| Platform | GPU | Notes |
|----------|-----|-------|
| macOS Apple Silicon (M1–M4) | MPS | 16 GB RAM minimum |
| macOS Intel | CPU | ~2–3× slower |
| Linux (NVIDIA) | CUDA | Best performance |
| Linux (CPU) | CPU | ~2–3× slower |
| Windows (WSL2) | CPU | Untested |

---

## Relationship to upstream projects

This is a fork of **[yajat009/Cortexia](https://github.com/yajat009/Cortexia)** (winning HackTech 2026 project), stabilized for local-first operation on consumer hardware. Key changes: configurable timeouts, Ollama support, MPS GPU concurrency protection, comprehensive tests, and documented configuration.

Cortexia builds on **[Facebook Research's TRIBE v2](https://github.com/facebookresearch/tribev2)**, which predicts cortical surface activations from text using Llama 3.2-3B. Cortexia adds: 6 brain-ROI extraction with 11 stats each, 8 psychometric composites, 4D Biological State Vectors per agent, demographic modulation, LangGraph swarm simulation, LLM reasoning traces, SQLite persistence, and a React dashboard with Mapbox GL + Deck.gl.
