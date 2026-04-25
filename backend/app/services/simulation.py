"""Simulation orchestration: TRIBE BSV, spatial modifiers, K2 routing, persistence, WS."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal, is_within_latlon_radius
from app.models import Agent, SimulationLog
from app.services.ai_clients import BSV, call_k2_think, call_tribe_modal
from app.services.websocket_manager import connection_manager

logger = logging.getLogger(__name__)

_PARSE_THINK = re.compile(
    r"<think>([\s\S]*?)</think>", re.IGNORECASE
)
_PARSE_ACTION = re.compile(
    r"<action>\s*(Adopted|Rejected)\s*</action>", re.IGNORECASE
)


def parse_k2_output(text: str) -> tuple[str, str]:
    """Returns (thinking_excerpt, 'adopted' | 'rejected')."""
    tm = _PARSE_THINK.search(text)
    thinking = (tm.group(1).strip() if tm else "") or "(no redacted block)"
    am = _PARSE_ACTION.search(text)
    if not am:
        return thinking, "rejected"
    return thinking, am.group(1).lower()


def _apply_spatial_bsv(
    base: BSV,
    adopted_neighbor_count: int,
) -> BSV:
    b: dict[str, float] = {**base}
    if adopted_neighbor_count >= 3:
        b["defensive_posture"] = max(0.0, float(b["defensive_posture"]) - 0.2)
    return {
        "cognitive_load": float(b["cognitive_load"]),
        "emotional_agitation": float(b["emotional_agitation"]),
        "defensive_posture": float(b["defensive_posture"]),
        "working_memory_strain": float(b["working_memory_strain"]),
    }


@dataclass(frozen=True)
class _Pos:
    id: int
    latitude: float
    longitude: float


def _neighbor_belief_stats(
    pos: _Pos,
    all_positions: list[_Pos],
    belief_by_id: dict[int, str],
    radius_deg: float = 0.05,
) -> tuple[int, int]:
    adopted = 0
    in_radius = 0
    for p in all_positions:
        if p.id == pos.id:
            continue
        if not is_within_latlon_radius(
            pos.latitude, pos.longitude, p.latitude, p.longitude, radius_deg
        ):
            continue
        in_radius += 1
        if belief_by_id.get(p.id) == "adopted":
            adopted += 1
    return adopted, in_radius


def _format_ts(cycle_start: float) -> str:
    el = time.time() - cycle_start
    return f"[{int(el // 60):02d}:{int(el % 60):02d}]"


async def _persist_log(session: AsyncSession, ts: float, log_text: str, agent_id: int) -> None:
    session.add(
        SimulationLog(
            timestamp=ts,
            log_text=log_text,
            agent_id=agent_id,
        )
    )
    await session.commit()


async def _update_agent_state(
    session: AsyncSession,
    agent_id: int,
    *,
    belief_state: str,
    infect_time: float,
    cognitive_load: float,
) -> None:
    await session.execute(
        update(Agent)
        .where(Agent.id == agent_id)
        .values(
            belief_state=belief_state,
            infect_time=infect_time,
            cognitive_load=cognitive_load,
        )
    )
    await session.commit()


async def run_simulation_cycle(catalyst_text: str) -> None:
    """Full async cycle: TRIBE BSV, per-agent K2, SQLite updates, WebSocket feed."""
    cycle_start = time.time()
    sem = asyncio.Semaphore(8)

    async with httpx.AsyncClient() as httpx_client:
        baseline = await call_tribe_modal(httpx_client, catalyst_text)

        async with SessionLocal() as session:
            res = await session.execute(select(Agent).order_by(Agent.id))
            agents: list[Agent] = list(res.scalars().all())
            await session.commit()

        positions: list[_Pos] = [
            _Pos(id=a.id, latitude=a.latitude, longitude=a.longitude) for a in agents
        ]
        initial_belief: dict[int, str] = {a.id: a.belief_state for a in agents}

        for agent in agents:
            pos = _Pos(id=agent.id, latitude=agent.latitude, longitude=agent.longitude)
            adopted_n, in_radius = _neighbor_belief_stats(
                pos, positions, initial_belief
            )
            mod_bsv = _apply_spatial_bsv(baseline, adopted_n)

            async with sem:
                try:
                    raw = await call_k2_think(
                        httpx_client,
                        name=agent.name,
                        role=agent.role,
                        bsv=mod_bsv,
                        adopted_neighbor_count=adopted_n,
                        total_neighbors_in_radius=in_radius,
                        catalyst_text=catalyst_text,
                    )
                except Exception:
                    logger.exception("K2 call failed for agent %s", agent.id)
                    raw = (
                        "<think>upstream failure</think> "
                        "<action>Rejected</action>"
                    )

            think, action = parse_k2_output(raw)
            now = time.time()
            stamp = _format_ts(cycle_start)

            if action == "adopted":
                new_belief = "adopted"
                new_infect = now
            else:
                new_belief = "rejected"
                new_infect = 0.0

            async with SessionLocal() as s2:
                await _update_agent_state(
                    s2,
                    agent.id,
                    belief_state=new_belief,
                    infect_time=new_infect,
                    cognitive_load=mod_bsv["cognitive_load"],
                )


            log_line = (
                f"{stamp} Agent {agent.id}: <think>{think}</think> "
                f"-> Action: {action.capitalize()}."
            )
            async with SessionLocal() as s3:
                await _persist_log(
                    s3, now, log_line, agent.id
                )

            await connection_manager.broadcast(
                {
                    "type": "agent_update",
                    "payload": {
                        "id": agent.id,
                        "belief_state": new_belief,
                        "infect_time": int(new_infect),
                    },
                }
            )
            await connection_manager.broadcast(
                {
                    "type": "terminal_log",
                    "payload": {
                        "text": f"> {log_line}",
                    },
                }
            )

    logger.info("Simulation cycle complete for catalyst len=%s", len(catalyst_text))
