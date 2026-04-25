"""Async SQLite engine, session factory, and helpers."""

from __future__ import annotations

import random
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.models import Agent, Base

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)
SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ~0.05 degrees: neighbor radius in lat/lon space (spec)
def is_within_latlon_radius(
    a_lat: float, a_lon: float, b_lat: float, b_lon: float, radius_deg: float = 0.05
) -> bool:
    dlat, dlon = abs(a_lat - b_lat), abs(a_lon - b_lon)
    return (dlat**2 + dlon**2) ** 0.5 <= radius_deg


async def seed_agents_if_empty() -> None:
    """Create 100 LA-centered agents if the table is empty."""
    async with get_session() as session:
        count = await session.scalar(select(func.count()).select_from(Agent))
        if count and count > 0:
            return

    roles = (
        "analyst",
        "field_operator",
        "citizen",
        "planner",
        "observer",
    )
    center_lat, center_lon = 34.0522, -118.2437
    rng = random.Random(7)

    async with get_session() as session:
        for i in range(100):
            lat = center_lat + rng.uniform(-0.12, 0.12)
            lon = center_lon + rng.uniform(-0.15, 0.15)
            session.add(
                Agent(
                    name=f"Agent {i + 1}",
                    role=rng.choice(roles),
                    latitude=lat,
                    longitude=lon,
                    belief_state="neutral",
                    infect_time=0.0,
                    cognitive_load=0.0,
                )
            )
