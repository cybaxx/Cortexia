"""Store for persistent, uniquely identifiable demographic populations."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.config import get_settings


def _db_path() -> Path:
    return Path(get_settings().pipeline_db_path).expanduser().resolve()


def init_population_store() -> None:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agents (
              id INTEGER PRIMARY KEY,
              city_id TEXT NOT NULL,
              name TEXT NOT NULL,
              role TEXT NOT NULL,
              latitude REAL NOT NULL,
              longitude REAL NOT NULL,
              age_band TEXT,
              age_years INTEGER,
              education_level TEXT,
              income_band TEXT,
              housing_status TEXT,
              language_profile TEXT,
              community_tenure TEXT,
              caregiving_load TEXT,
              digital_media_habit TEXT,
              demographics_json TEXT NOT NULL
            )
            """
        )
        _ensure_agent_columns(conn)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agents_city ON agents(city_id)")
        conn.commit()


def _ensure_agent_columns(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(agents)").fetchall()
    columns = {str(row[1]) for row in rows}
    required: dict[str, str] = {
        "age_band": "TEXT",
        "age_years": "INTEGER",
        "education_level": "TEXT",
        "income_band": "TEXT",
        "housing_status": "TEXT",
        "language_profile": "TEXT",
        "community_tenure": "TEXT",
        "caregiving_load": "TEXT",
        "digital_media_habit": "TEXT",
    }
    for name, sql_type in required.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE agents ADD COLUMN {name} {sql_type}")


def save_population(city_id: str, agents: list[dict[str, object]]) -> None:
    """Save newly generated agents to the database persistently."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executemany(
            """
            INSERT INTO agents (
              id, city_id, name, role, latitude, longitude,
              age_band, age_years, education_level, income_band, housing_status,
              language_profile, community_tenure, caregiving_load, digital_media_habit,
              demographics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              city_id=excluded.city_id,
              name=excluded.name,
              role=excluded.role,
              latitude=excluded.latitude,
              longitude=excluded.longitude,
              age_band=excluded.age_band,
              age_years=excluded.age_years,
              education_level=excluded.education_level,
              income_band=excluded.income_band,
              housing_status=excluded.housing_status,
              language_profile=excluded.language_profile,
              community_tenure=excluded.community_tenure,
              caregiving_load=excluded.caregiving_load,
              digital_media_habit=excluded.digital_media_habit,
              demographics_json=excluded.demographics_json
            """,
            [
                (
                    int(agent["id"]),  # type: ignore
                    city_id,
                    str(agent["name"]),
                    str(agent["role"]),
                    float(agent["lat"]),  # type: ignore
                    float(agent["lng"]),  # type: ignore
                    str((agent["demographics"] or {}).get("age_band", "")),  # type: ignore[index]
                    int((agent["demographics"] or {}).get("age_years", 0)),  # type: ignore[index]
                    str((agent["demographics"] or {}).get("education_level", "")),  # type: ignore[index]
                    str((agent["demographics"] or {}).get("income_band", "")),  # type: ignore[index]
                    str((agent["demographics"] or {}).get("housing_status", "")),  # type: ignore[index]
                    str((agent["demographics"] or {}).get("language_profile", "")),  # type: ignore[index]
                    str((agent["demographics"] or {}).get("community_tenure", "")),  # type: ignore[index]
                    str((agent["demographics"] or {}).get("caregiving_load", "")),  # type: ignore[index]
                    str((agent["demographics"] or {}).get("digital_media_habit", "")),  # type: ignore[index]
                    json.dumps(agent["demographics"]),
                )
                for agent in agents
            ],
        )
        conn.commit()


def fetch_population(city_id: str, limit: int) -> list[dict[str, object]]:
    """Fetch persistent agents for the given city."""
    path = _db_path()
    if not path.exists():
        return []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM agents WHERE city_id = ? ORDER BY id ASC LIMIT ?",
            (city_id, limit),
        ).fetchall()
        return [_row_to_agent_dict(row) for row in rows]


def fetch_population_agent(city_id: str, agent_id: int) -> dict[str, object] | None:
    path = _db_path()
    if not path.exists():
        return None
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM agents WHERE city_id = ? AND id = ?",
            (city_id, agent_id),
        ).fetchone()
        return _row_to_agent_dict(row) if row is not None else None


def list_population(city_id: str, limit: int = 200) -> list[dict[str, object]]:
    return fetch_population(city_id, limit)


def _row_to_agent_dict(row: sqlite3.Row | None) -> dict[str, object]:
    if row is None:
        return {}
    demographics_json = json.loads(row["demographics_json"]) if row["demographics_json"] else {}
    demographics: dict[str, Any] = {
        "age_band": row["age_band"] or demographics_json.get("age_band"),
        "age_years": row["age_years"] if row["age_years"] is not None else demographics_json.get("age_years"),
        "education_level": row["education_level"] or demographics_json.get("education_level"),
        "income_band": row["income_band"] or demographics_json.get("income_band"),
        "housing_status": row["housing_status"] or demographics_json.get("housing_status"),
        "language_profile": row["language_profile"] or demographics_json.get("language_profile"),
        "community_tenure": row["community_tenure"] or demographics_json.get("community_tenure"),
        "caregiving_load": row["caregiving_load"] or demographics_json.get("caregiving_load"),
        "digital_media_habit": row["digital_media_habit"] or demographics_json.get("digital_media_habit"),
    }
    return {
        "id": row["id"],
        "city_id": row["city_id"],
        "name": row["name"],
        "role": row["role"],
        "lat": row["latitude"],
        "lng": row["longitude"],
        "demographics": demographics,
    }
