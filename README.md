# Cortexia Compass

Monorepo layout:

- **`frontend/`** — Vite + React + TypeScript (Mapbox, etc.). Run: `cd frontend && npm install && npm run dev` (port **5173**). Open **http://127.0.0.1:5173/** (or the URL Vite prints). If **http://localhost:…** shows 404, your machine is resolving `localhost` to IPv6 while another app uses that port — prefer **127.0.0.1** or free port 8080. Env: `frontend/.env` (`VITE_MAPBOX_TOKEN`, `VITE_API_BASE_URL`). Dev server proxies **`/api`** to the FastAPI backend on port 8000.
- **`backend/`** — FastAPI + SQLite + WebSockets. Run: `cd backend && source .venv/bin/activate && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000`. Env: **`backend/.env`** — set **`TRIBE_MODAL_URL`** to your Modal `extract_bsv` URL; the app reads it via `app.constants.tribe_modal_deployment_url()`.
- **`backend/modal_app.py`** — TRIBE on Modal (`modal deploy modal_app.py` or `modal serve modal_app.py`).

Do not commit real `.env` files; use `*.env.example` as templates.
