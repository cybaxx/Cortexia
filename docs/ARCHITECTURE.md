# Architecture

## System overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Vite)                      │
│  SimulationDashboard → MapView · BrainViz · AgentVoiceWorkspace    │
│  Port 5173 · Proxies /api → Backend                               │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP (JSON)
┌──────────────────────────────▼──────────────────────────────────────┐
│                      BACKEND (FastAPI :8000)                        │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Simulation Pipeline (api_simulation.py)         │   │
│  │                                                              │   │
│  │  Evidence → TRIBE Neural → LFCM Calibration → Scoring       │   │
│  │     ↓                                                   ↓    │   │
│  │  Agent Reasoning (K2/Ollama) → LangGraph Swarm → Persist   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐   │
│  │ TRIBE Neural │  │  AI Clients   │  │   Action Center        │   │
│  │ (vendored)   │  │ K2 / Ollama  │  │ Tavily / DDG / local   │   │
│  │ 6-step pipe  │  │ ElevenLabs / │  │                        │   │
│  │              │  │ Edge TTS     │  │                        │   │
│  └──────────────┘  └──────────────┘  └────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              SQLite (cortexia.db)                             │  │
│  │  case_runs · agent_outcomes · conversations · rounds         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Data flow: POST /api/simulate

```
1. Population Generation
   _build_virtual_population(city_id, count)
   → Fetches or creates synthetic agents with demographics, roles, geo-coords

2. Evidence Processing
   source_fetch → analysis_text assembly → claim diagnostics
   → credibility, harm, virality scores

3. TRIBE Neural Pipeline (6 steps)
   tribe_batch → run_framework_batch()
   Step 1: Llama 3.2 → cortical predictions (n_TRs × 20484)
   Step 2: ROI timeseries (6 regions via Schaefer atlas)
   Step 3: 11 statistics per ROI
   Step 4: 7 pairwise correlations
   Step 5: 8 composite psychometric scores
   Step 6: Human-readable neural state string
   → Per-agent demographic modulation + BSV derivation

4. LFCM Calibration
   _apply_lfcm_calibration()
   → Maps BSV through role, demographics, political lean, case features

5. Neural Region Derivation
   _derive_brain_regions() → PFC, Amygdala, Insula, Hippocampus, ACC, TPJ

6. Uptake Scoring
   _baseline_uptake_score() → claim alignment + BSV + traits
   _final_uptake_score() → baseline + spatial neighbor effects
   → adopted / rejected / neutral per agent

7. Agent Reasoning
   K2/Ollama batch reasoning → per-agent explanation traces
   Falls back to deterministic reasoning if LLM unavailable

8. Swarm Propagation (LangGraph)
   3 ticks: first read → network update → settled position
   Hybrid engine: LLM for top 5 key actors, heuristic for rest
   Cyber exposure: public posts jump geography to random agents
   → per-agent round history with 15+ fields per round

9. Workspace Assembly
   _build_workspace_payload()
   → spread_model, mechanisms, intervention_playbook,
     evidence_trace, evidence_graph, swarm_dynamics,
     hotspots, macro_result, summary

10. Persistence
    persist_case_run() → SQLite (case_runs, agent_outcomes, rounds)

11. Response
    Full SimulateResponse JSON → frontend renders dashboard
```

## Key modules

| Module | Purpose |
|--------|---------|
| `app/main.py` | FastAPI app, 12 endpoints, CORS, lifespan |
| `app/config.py` | pydantic-settings, 22 configurable fields |
| `app/services/api_simulation.py` | Core simulation orchestrator (4589 lines) |
| `app/services/tribe_framework.py` | Local TRIBE adapter with demographic modulation |
| `app/services/langgraph_multi_agent_sim.py` | LangGraph swarm state machine |
| `app/services/ai_clients.py` | External AI integrations (K2, Ollama, TTS, STT) |
| `app/services/action_center.py` | Live research (Tavily / DuckDuckGo / fallback) |
| `app/services/local_research.py` | DuckDuckGo search + trafilatura extraction |
| `app/services/shared_math.py` | clamp(), sigmoid() — shared across modules |
| `app/pipeline_store.py` | SQLite CRUD (5 tables) |
| `app/population_store.py` | Agent persistence per city |
| `app/political_geography.py` | Partisan lean lookup + GeoJSON export |
| `app/city_presets.py` | City land zones and coordinates |
| `tribe_neural/` | Vendored 6-step TRIBE pipeline |

## Frontend component tree

```
App.tsx
 └─ Index.tsx (screen: 'landing' | 'dashboard')
      ├─ ProductLanding.tsx
      └─ SimulationDashboard.tsx (stage: 'evidence' | 'spread' | 'interventions')
           ├─ Evidence form (step 1)
           ├─ Simulation Map (step 2)
           │   ├─ MapView.tsx (Mapbox GL + Deck.gl)
           │   │   └─ Agent markers, network edges, hotspots, political zones
           │   ├─ AgentVoiceWorkspace.tsx
           │   │   └─ BrainViz.tsx → Brain3D.tsx (Three.js)
           │   └─ "Why It Spread" panel
           └─ Action Center (step 3)
                └─ Export + research briefs
```

## State management (Zustand)

```
useCortexStore
├─ screen: 'landing' | 'dashboard'
├─ stage: 'evidence' | 'spread' | 'interventions'
├─ status: 'idle' | 'running' | 'ready' | 'error'
├─ latestResponse: SimulateResponse | null
├─ agentSimulationById: Record<number, AgentSimulationPayload>
├─ caseSummary, spreadModel, mechanisms, interventionPlaybook
├─ evidenceTrace, evidenceGraph, swarmDynamics
└─ Actions: runSimulation(), openRun(), exportCase(), setEvidenceField()
```

## Database schema

```sql
case_runs (
  id, created_at, domain, city_id, case_goal,
  evidence_json, analysis_text, source_excerpt, source_warning,
  claim_json, fidelity, response_json
)

agent_outcomes (
  run_id, agent_id, name, role, latitude, longitude,
  demographics_json, spread_notes,
  tribe_json, calibrated_json, traits_json, score_json, outcome_json
)

agent_conversations (
  run_id, agent_id, role, message, audio_filename, created_at
)

simulation_rounds (
  run_id, round_number, adoption_rate, rejection_rate, neutral_rate,
  dominant_mechanism, notable_shift, posts_json
)

agents (
  id, city_id, name, role, latitude, longitude,
  age_band, age_years, education_level, income_band, housing_status,
  language_profile, community_tenure, caregiving_load, digital_media_habit,
  demographics_json
)
```
