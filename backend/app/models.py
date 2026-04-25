"""SQLAlchemy ORM models."""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    belief_state: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="neutral",
    )  # 'neutral' | 'adopted' | 'rejected'
    infect_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Last-known cognitive load from TRIBE+K2 cycle (for aggregate reporting)
    cognitive_load: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    logs: Mapped[list["SimulationLog"]] = relationship(
        "SimulationLog",
        back_populates="agent",
    )


class SimulationLog(Base):
    __tablename__ = "simulation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    log_text: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
    )

    agent: Mapped[Agent | None] = relationship("Agent", back_populates="logs")
