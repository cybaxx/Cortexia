# Troubleshooting

## Simulation times out (504 Gateway Timeout)

**Symptom:** `POST /api/simulate` returns 504 after ~3 minutes.

**Cause:** TRIBE neural inference on MPS/CPU is slower than the configured `simulate_total_timeout_seconds`.

**Fix:**
```env
# backend/.env
simulate_total_timeout_seconds=900   # increase from default 180
simulate_tribe_timeout_seconds=600   # increase from default 120
simulate_population_size=24          # reduce from default 72
```

Also reduce text length — TRIBE processing time scales with word count (~40-60s per word on MPS).

## Frontend shows "socket hang up" / blank dashboard

**Cause:** Vite proxy timeout kills long simulation requests.

**Fix:** Added `timeout: 900000` and `proxyTimeout: 900000` to `frontend/vite.config.ts`. Restart frontend if you're on an older version.

## "Simulation response did not include live TRIBE metadata"

**Cause:** Loading a persisted run from before the `tribe_meta` persist fix (runs before #10).

**Fix:** Run a new simulation. Old persisted runs (< #10) lack `tribe_meta` fields.

## Map shows "Set VITE_MAPBOX_TOKEN" but no basemap

**Cause:** No Mapbox token configured.

**Fix:** This is cosmetic — the map still works with free OpenStreetMap tiles. Agents, hotspots, and edges render correctly. Set `VITE_MAPBOX_TOKEN=your_token` in `frontend/.env` for premium tiles.

## DuckDuckGo search returns no results

**Cause:** SSL certificate issues in corporate/restricted networks.

**Fix:** The `ddgs` library (not `duckduckgo-search`) handles this better. If still failing, the Action Center falls back to simulation-only data. No API key needed.

## Ollama isn't generating reasoning traces

**Check:** Ollama must be running before the backend starts.
```bash
ollama serve           # start Ollama
ollama pull llama3.2   # ensure model is downloaded
```

**Config in `backend/.env`:**
```env
IFM_API_KEY=ollama
IFM_API_URL=http://localhost:11434/v1/chat/completions
IFM_K2_MODEL=llama3.2:latest
```

If Ollama is unreachable, the simulation uses deterministic fallback reasoning — structurally correct but simpler natural language.

## "Address already in use" on port 8000

**Fix:**
```bash
lsof -ti :8000 | xargs kill -9
```

## Python import errors after fresh install

**Cause:** Missing dependencies. Run the full setup:
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash scripts/setup_tribe_framework.sh
```

The `setup_tribe_framework.sh` script installs the vendored TRIBE framework and its heavy dependencies.

## Simulation crashes with KeyError

**Symptom:** `KeyError: '_pipeline'` or `KeyError: 'Butler'` in backend logs.

**Fix:** These were bugs in the original HackTech 2026 prototype, fixed in this fork. If you see them, ensure you're on the latest commit.

## MongoDB / Redis errors

**Cause:** These are only used in `tribe_neural/api.py` (ARQ worker mode) and `modal_app.py` (Modal deployment). Not needed for framework mode.

**Fix:** Set `TRIBE_RUNTIME_MODE=framework` (default) to skip these.
