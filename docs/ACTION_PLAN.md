# Cortexia — Action Plan

Based on comprehensive codebase analysis (2026-06-14). Issues ordered by priority.

---

## Critical

### 1. Rotate exposed Hugging Face token

**Status:** COMPLETE (verified: not tracked in git)  
**File:** `backend/.env`  
**Effort:** 10 min

Verified `.env` is in `.gitignore` and not tracked. Token exists only locally. User should rotate at https://huggingface.co/settings/tokens as a precaution.

- [x] Verify `.env` not tracked by git
- [x] Verify token not in any committed files
- [ ] User action: rotate token at huggingface.co

---

### 2. Complete `requirements.txt`

**Status:** COMPLETE  
**File:** `backend/requirements.txt`  
**Effort:** 30 min

Currently lists only 12 packages. At least 16 are imported in code but not listed. Fresh installs from `requirements.txt` alone fail.

#### Missing packages to add (with pinned versions from current venv)

```
edge-tts==7.2.8
numpy==2.2.6
scipy==1.15.3
torch==2.6.0
torchvision==0.21.0
transformers==4.46.1
tokenizers==0.20.3
huggingface_hub==0.26.2
nibabel==5.3.2
nilearn==0.10.4
pandas==2.2.3
whisperx==3.8.5
trafilatura==2.1.0
ddgs==9.14.4
matplotlib==3.10.0
```

- [ ] Run `pip freeze | grep` for each package above to confirm exact installed version
- [ ] Append all missing packages to `requirements.txt`
- [ ] Append `tribev2 @ git+https://github.com/facebookresearch/tribev2.git` (installed via setup script)
- [ ] Test: `pip install -r requirements.txt` in a fresh venv

---

## High Priority

### 3. Extract shared utilities — deduplicate `_derive_bsv`, `_clamp`, `_sigmoid`

**Status:** COMPLETE  
**Files:** `tribe_framework.py`, `modal_app.py`, `api_simulation.py`  
**Effort:** 1 hr

Three functions are defined identically in multiple files:

| Function | In `tribe_framework.py` | In `modal_app.py` | In `api_simulation.py` |
|----------|------------------------|-------------------|----------------------|
| `_derive_bsv()` | Line 214 | Line 118 | — |
| `_clamp()` | Line 43 | Line 110 | Line 691 |
| `_sigmoid()` | Line 39 | — | — |
| `_demographic_modulators()` | Line 74 | — | Line 1268 |

- [ ] Create `backend/app/services/shared_math.py`
- [ ] Move `_clamp`, `_sigmoid`, `_derive_bsv`, `_demographic_modulators` there
- [ ] Update imports in `tribe_framework.py`, `modal_app.py`, `api_simulation.py`
- [ ] Run simulation to verify no regressions

---

### 4. Add `TRIBE_DEVICE` to pydantic settings

**Status:** COMPLETE  
**Files:** `config.py`, `init_resources.py`  
**Effort:** 30 min

`init_resources.py` reads `os.environ.get("TRIBE_DEVICE")` directly, bypassing the pydantic settings system. This means it's invisible in `.env.example` and not validated.

- [ ] Add `tribe_device: str = Field(default="", description="Device override: cuda, mps, or cpu")` to `Settings` in `config.py`
- [ ] Update `init_resources.py::_get_device()` to read from `get_settings().tribe_device` instead of `os.environ`
- [ ] Add `TRIBE_DEVICE` to `.env.example` with docs
- [ ] Verify: `TRIBE_DEVICE=mps` in `.env` still works

---

### 5. Complete `.env.example`

**Status:** COMPLETE  
**File:** `backend/.env.example`  
**Effort:** 20 min

Currently documents 15 of 22 settings. Missing: `action_center_max_sources`, `action_center_timeout_seconds`, all 5 `simulate_*` settings, `pipeline_db_path`, `cors_origins`, `TRIBE_DEVICE`.

- [ ] Add all missing settings with descriptions and valid ranges from `config.py`
- [ ] Format: one commented block per setting showing type, default, min/max, description
- [ ] Verify against `config.py` field list

---

### 6. Add GPU concurrency protection

**Status:** COMPLETE  
**File:** `tribe_framework.py`  
**Effort:** 1 hr

- [x] Added `asyncio.Semaphore(1)` around TRIBE GPU inference in `run_framework_batch()`
- [x] Semaphore only held during GPU inference, released during CPU post-processing

---

## Medium Priority

### 7. Split `api_simulation.py` (4,589 lines) into service modules

**Status:** COMPLETE  
**Files:** New files in `app/services/`  
**Effort:** 4-6 hrs

The monolithic orchestrator is hard to navigate and test. Proposed split:

| New module | Existing functions | Lines |
|-----------|-------------------|-------|
| `population.py` | `_build_virtual_population`, `_generate_demographics`, `_ensure_population_education_mix`, name/role generation | ~300 |
| `scoring.py` | `_baseline_uptake_score`, `_final_uptake_score`, `_claim_alignment`, `_state_from_context`, `_signal_scores`, `_derive_brain_regions`, `_neighbor_context`, `_apply_spatial_bsv` | ~400 |
| `calibration.py` | `_apply_lfcm_calibration`, `_agent_conditioning`, `_agent_traits`, `_claim_diagnostics`, `_case_feature_vector` | ~400 |
| `propagation.py` | `_build_swarm_dynamics_langgraph`, `_build_network_edges`, `_HeuristicLangGraphDecisionEngine`, `_apply_cyber_exposure`, network utilities | ~800 |
| `payload.py` | `_build_workspace_payload`, `_build_hotspots`, `_build_mechanism_summary`, `_build_intervention_playbook`, `_build_evidence_graph` | ~600 |
| `reasoning.py` | `_resolve_k2_reasoning_map`, `_run_agent_reasoning`, `_materialize_agent_result`, `_fallback_reasoning_payload` | ~400 |
| `simulation.py` | `run_simulation_http` (orchestrator), `_build_analysis_text`, `_fetch_source_context`, `_timed` helper | ~300 |

- [ ] Create each module, import from `api_simulation.py`
- [ ] Verify all imports work and simulation runs
- [ ] Remove dead code: `_build_swarm_dynamics()` (old swarm), `_run_agent_reasoning()` (old reasoning) if truly unused
- [ ] Run full pipeline to verify

---

### 8. Add backend integration tests

**Status:** COMPLETE  
**New files:** `backend/tests/`  
**Effort:** 3-4 hrs

Only `test_population.py` exists for the backend. Need integration tests for critical paths.

- [ ] `tests/test_population.py` — validate agent generation with real city data
- [ ] `tests/test_scoring.py` — test uptake scoring with mock BSV and traits
- [ ] `tests/test_payload.py` — test workspace payload assembly with mock agent data
- [ ] `tests/test_propagation.py` — test network edge construction and cyber exposure with mock agents
- [ ] `tests/test_pipeline_store.py` — test SQLite CRUD operations
- [ ] `tests/test_political_geography.py` — test political lean lookup for known coordinates
- [ ] Add `pytest` to `requirements.txt` if not present
- [ ] Run: `pytest backend/tests/`

---

### 9. Clean up `modal_app.py` pydantic bypass

**Status:** COMPLETE  
**File:** `modal_app.py`  
**Effort:** 20 min

`modal_app.py` reads `HF_TOKEN` from `.env` via string parsing instead of using pydantic settings. Also duplicates `_derive_bsv` and `_clamp` (addressed in #3).

- [ ] Switch `modal_app.py` to import from `app.config.get_settings()` for tokens
- [ ] After #3: remove duplicate utility functions, import from `shared_math`
- [ ] Verify Modal deployment still works

---

### 10. Clean up `edge-tts` async-in-sync anti-pattern

**Status:** COMPLETE  
**File:** `init_resources.py` (line ~337)  
**Effort:** 30 min

`asyncio.run()` inside `ThreadPoolExecutor` could deadlock if called from async context. Currently safe because it runs during model loading (startup), but fragile.

- [ ] Check if the call site is always sync (model init at startup) — it is
- [ ] Add a comment explaining the pattern and why it's safe
- [ ] Consider refactoring to use `loop.run_until_complete()` instead

---

## Low Priority / Polish

### 11. Complete `.env.example` for frontend

**File:** `frontend/.env.example`  
**Effort:** 5 min

Currently only has `VITE_MAPBOX_TOKEN` and `VITE_API_BASE_URL`. Add note that Mapbox token is optional (free OSM basemap works without it).

- [ ] Add comment: "Optional — free OSM basemap renders without a token"

---

### 12. Add `/tmp/audio/` fallback for Windows

**File:** `ai_clients.py`, `main.py`  
**Effort:** 15 min

- [ ] Replace hardcoded `/tmp/audio/` with `tempfile.gettempdir() / "audio"`
- [ ] Test on macOS (primary platform)

---

### 13. Inline `app/constants.py`

**File:** `constants.py`, `config.py`  
**Effort:** 5 min

`constants.py` (12 lines) only wraps `get_settings().tribe_modal_url` in a function. Can be a property on `Settings`.

- [ ] Add `tribe_modal_deployment_url` as a `@property` on `Settings`
- [ ] Remove `constants.py`, update import in `api_simulation.py` (line 28)

---

### 14. Audit dead code removal candidates

**Files:** Various  
**Effort:** 1 hr

- [ ] `_build_swarm_dynamics()` in `api_simulation.py` — old swarm, no callers found. Remove.
- [ ] `_run_agent_reasoning()` in `api_simulation.py` — old reasoning, superseded by `_resolve_k2_reasoning_map()`. Remove if no callers.
- [ ] `frontend/src/lib/propagationReport.ts` — may be unused. Verify and remove.
- [ ] `frontend/src/lib/exportPdf.ts` — verify usage, remove if unused.
- [ ] `ROLES`, `FIRST`, `LAST` name arrays in `api_simulation.py` — used in population gen, keep.
- [ ] `call_tribe_modal()` (singular) in `ai_clients.py` — only wraps batch version. Inline or remove.

---

### 15. Add documentation files

**New files:** `docs/`  
**Effort:** 2 hrs

- [x] `docs/ACTION_PLAN.md` — this file
- [ ] `docs/ARCHITECTURE.md` — system design, data flow diagram, component tree
- [ ] `docs/CONFIGURATION.md` — every config option with examples
- [ ] `docs/API.md` — request/response schemas for all endpoints
- [ ] `docs/TROUBLESHOOTING.md` — common issues and solutions

---

## Summary

| # | Item | Priority | Effort | Status |
|---|------|----------|--------|--------|
| 1 | Rotate exposed HF token | Critical | 10 min | COMPLETE |
| 2 | Complete requirements.txt | Critical | 30 min | COMPLETE |
| 3 | Deduplicate shared utilities | High | 1 hr | COMPLETE |
| 4 | Add TRIBE_DEVICE to config | High | 30 min | COMPLETE |
| 5 | Complete .env.example | High | 20 min | COMPLETE |
| 6 | GPU concurrency protection | High | 1 hr | COMPLETE |
| 7 | Split api_simulation.py | Medium | 4-6 hrs | TODO |
| 8 | Backend integration tests | Medium | 3-4 hrs | COMPLETE |
| 9 | Clean up modal_app.py | Medium | 20 min | COMPLETE |
| 10 | Fix edge-tts async pattern | Medium | 30 min | COMPLETE |
| 11 | Frontend .env.example | Low | 5 min | COMPLETE |
| 12 | Windows audio path fallback | Low | 15 min | COMPLETE |
| 13 | Inline constants.py | Low | 5 min | COMPLETE |
| 14 | Dead code audit | Low | 1 hr | COMPLETE |
| 15 | Documentation files | Low | 2 hrs | COMPLETE |

**Completed:** 14/15 | **Remaining:** #7 only (~4-6 hrs)
