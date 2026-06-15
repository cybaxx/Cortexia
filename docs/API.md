# Cortexia API

Base URL: `http://127.0.0.1:8000`

---

## Endpoints

### Health

**`GET /api/health`** — Liveness check.

```
200 { "status": "ok" }
```

---

### Simulation

**`POST /api/simulate`** — Run a full case simulation (main pipeline).

Request:
```json
{
  "domain": "Political Campaign",
  "city_id": "los-angeles-ca",
  "case_goal": "Assess spread risk",
  "message_complexity": 0.6,
  "evidence": {
    "text_input": "The claim text to analyze...",
    "source_url": null,
    "transcript": null,
    "edited_analysis_text": null,
    "speaker_context": "Additional context about the speaker or source.",
    "audio_input": null
  }
}
```

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `domain` | string | No | `"political"` | Simulation domain |
| `city_id` | string | No | `"la"` | City preset ID |
| `case_goal` | string | No | *(see default)* | Objective description |
| `message_complexity` | float | No | `0.5` | 0–1, or named: `"simple"`/`"medium"`/`"complex"` |
| `evidence.text_input` | string | No | `""` | Main claim/rumor text (12+ chars recommended) |
| `evidence.speaker_context` | string | No | `null` | Source attribution context |

Response: Full `SimulateResponse` JSON containing agents, spread model, mechanisms, intervention playbook, evidence trace, swarm dynamics, hotspots, and more. See the TypeScript types in `frontend/src/types/simulation.ts` for the complete schema.

Errors: `504` (timeout), `502` (upstream failure), `500` (internal error).

---

### Transcription

**`POST /api/transcribe`** — Transcribe audio via ElevenLabs STT.

Multipart form: `file` (audio upload) + optional `language_code` field.

Response:
```json
{
  "text": "transcribed text",
  "language_code": "en",
  "duration_seconds": 45.2,
  "transcript_confidence": 0.92,
  "speaker_ids": ["speaker_0"],
  "filename": "recording.mp3",
  "mime_type": "audio/mpeg",
  "source_type": "audio_upload"
}
```

---

### Runs

**`GET /api/runs/recent`** — List recent simulation runs.

Query params: `limit` (1–100, default 25), `domain`, `city_id`, `search`.

```json
{
  "runs": [{ "id": 1, "created_at": "...", "domain": "...", "city_id": "...", "case_goal": "...", "claim": {...}, "fidelity": 0.85 }]
}
```

---

**`GET /api/runs/search`** — Semantic search over runs via vector embeddings.

Query params: `q` (min 1 char), `limit` (1–20, default 5). Requires ChromaDB.

```json
{
  "results": [{ "run_id": 1, "score": 0.92, "fragment": "..." }]
}
```

---

**`GET /api/runs/{run_id}`** — Load a persisted run by ID.

Returns the full case record with all JSON fields deserialized.

---

**`DELETE /api/runs/{run_id}`** — Delete a run and all associated data (agents, conversations, rounds).

```json
{ "deleted": true, "run_id": 1 }
```

---

**`GET /api/runs/{run_id}/report`** — Generate a PDF report for a run.

Returns `application/pdf` file response.

---

### Run Agents

**`GET /api/runs/{run_id}/agents`** — List agents for a run.

Query: `limit` (1–400, default 180).

```json
{
  "agents": [{ "run_id": 1, "agent_id": 42, "name": "...", "role": "...", ... }]
}
```

---

**`GET /api/runs/{run_id}/agents/{agent_id}/profile`** — Get full agent profile including TRIBE, BSV, traits, scores, outcome.

---

**`PUT /api/runs/{run_id}/agents/{agent_id}/notes`** — Update agent spread notes.

```json
{ "spread_notes": "Analyst notes about this agent's behavior..." }
```

---

**`GET /api/runs/{run_id}/agents/{agent_id}/conversation`** — Get agent chat history.

```json
{
  "messages": [{
    "id": 1,
    "created_at": "...",
    "user_message": "...",
    "agent_reply": "...",
    "sentiment": "neutral",
    "stance": "adopted",
    "audio_url": "/api/audio/tts_abc123.mp3"
  }]
}
```

---

**`POST /api/runs/{run_id}/agents/{agent_id}/conversation`** — Send a message to an agent.

```json
{ "message": "Why did you decide to share this story?" }
```

Response includes the agent's LLM reply, sentiment, stance, and optional TTS audio URL.

---

### Populations

**`GET /api/populations/{city_id}/agents`** — List synthetic population for a city.

Query: `limit` (1–400, default 120).

---

**`GET /api/populations/{city_id}/agents/{agent_id}`** — Get a single population agent.

---

### Political Geography

**`GET /api/political-zones/{city_id}`** — GeoJSON overlay of precinct-level political lean.

Returns a GeoJSON FeatureCollection with zone boundaries, lean scores, and homogeneity.

---

### Action Center

**`GET /api/action-center/status`** — Research provider configuration.

```json
{
  "providers": { "tavily": true, "firecrawl": false, "local": true }
}
```

---

**`POST /api/action-center/research`** — Run a live web research dossier.

```json
{
  "domain": "public_health",
  "city_id": "los-angeles-ca",
  "case_goal": "Understand vaccine misinformation spread",
  "scenario": "A viral post claims vaccines cause long-term health issues...",
  "spread_risk": "High",
  "key_finding": "Misinformation targets young parents",
  "dominant_pathway": "social_contagion",
  "notes": "Focus on pediatrician counter-messaging"
}
```

---

### Audio

**`GET /api/audio/{filename}`** — Serve generated TTS audio files.

Returns `audio/mpeg` or `404`.

---

## Error responses

| Status | Meaning |
|--------|---------|
| `400` | Bad request (e.g. empty audio file) |
| `404` | Run, agent, or audio file not found |
| `500` | Internal pipeline error |
| `502` | Upstream service failure (LLM, TTS, STT) |
| `504` | Simulation timeout |

All error responses follow:
```json
{ "detail": "Human-readable error description" }
```
