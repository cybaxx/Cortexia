"""
Cortexia FastAPI orchestrator: SQLite, WebSockets, IFM / ElevenLabs / Modal integration.

From `backend/`: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal, init_db, seed_agents_if_empty
from app.models import Agent
from app.services.simulation import run_simulation_cycle
from app.services.websocket_manager import connection_manager

settings = get_settings()
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    await seed_agents_if_empty()
    logger.info("Cortexia API ready; CORS=%s", settings.cors_origin_list)
    yield


app = FastAPI(
    title="Cortexia Cognitive Impact API",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AgentOut(BaseModel):
    id: int
    name: str
    role: str
    latitude: float
    longitude: float
    belief_state: str
    infect_time: float
    cognitive_load: float


class InjectPayload(BaseModel):
    catalyst_text: str = Field(
        ..., examples=["Mandatory 5-day RTO implemented immediately."]
    )


class ReportOut(BaseModel):
    total_agents: int
    adopted: int
    rejected: int
    avg_cognitive_load: float


@app.get("/api/agents/init", response_model=list[AgentOut])
async def api_agents_init() -> list[AgentOut]:
    """Initial map: all agents from SQLite."""
    async with SessionLocal() as session:
        res = await session.execute(select(Agent).order_by(Agent.id))
        rows = list(res.scalars().all())
    return [
        AgentOut(
            id=a.id,
            name=a.name,
            role=a.role,
            latitude=a.latitude,
            longitude=a.longitude,
            belief_state=a.belief_state,
            infect_time=a.infect_time,
            cognitive_load=a.cognitive_load,
        )
        for a in rows
    ]


@app.post("/api/scenario/inject")
async def api_scenario_inject(body: InjectPayload) -> dict[str, str]:
    asyncio.create_task(run_simulation_cycle(body.catalyst_text))
    return {"status": "Simulation started"}


@app.get("/api/simulation/report", response_model=ReportOut)
async def api_simulation_report() -> ReportOut:
    async with SessionLocal() as session:
        total = await session.scalar(select(func.count()).select_from(Agent)) or 0
        adopted = (
            await session.scalar(
                select(func.count())
                .select_from(Agent)
                .where(Agent.belief_state == "adopted")
            )
            or 0
        )
        rejected = (
            await session.scalar(
                select(func.count())
                .select_from(Agent)
                .where(Agent.belief_state == "rejected")
            )
            or 0
        )
        avg = await session.scalar(select(func.avg(Agent.cognitive_load)))
    return ReportOut(
        total_agents=int(total),
        adopted=int(adopted),
        rejected=int(rejected),
        avg_cognitive_load=float(avg) if avg is not None else 0.0,
    )


@app.websocket("/api/simulation/ws")
async def api_simulation_ws(websocket: WebSocket) -> None:
    await connection_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
