"""Lightweight SQLite store for persisted case runs and agent outcomes."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.config import get_settings


def _db_path() -> Path:
    return Path(get_settings().pipeline_db_path).expanduser().resolve()


def init_pipeline_store() -> None:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS case_runs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              domain TEXT NOT NULL,
              city_id TEXT NOT NULL,
              case_goal TEXT NOT NULL,
              evidence_json TEXT NOT NULL,
              analysis_text TEXT NOT NULL,
              source_excerpt TEXT,
              source_warning TEXT,
              claim_json TEXT NOT NULL,
              fidelity REAL NOT NULL,
              response_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_outcomes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              run_id INTEGER NOT NULL,
              agent_id INTEGER NOT NULL,
              name TEXT NOT NULL,
              role TEXT NOT NULL,
              latitude REAL NOT NULL,
              longitude REAL NOT NULL,
              demographics_json TEXT NOT NULL DEFAULT '{}',
              spread_notes TEXT NOT NULL DEFAULT '',
              tribe_json TEXT NOT NULL,
              calibrated_json TEXT NOT NULL,
              traits_json TEXT NOT NULL,
              score_json TEXT NOT NULL,
              outcome_json TEXT NOT NULL,
              FOREIGN KEY(run_id) REFERENCES case_runs(id)
            )
            """
        )
        _ensure_agent_outcome_columns(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_conversations (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              run_id INTEGER NOT NULL,
              agent_id INTEGER NOT NULL,
              user_message TEXT NOT NULL,
              agent_reply TEXT NOT NULL,
              sentiment TEXT NOT NULL,
              stance TEXT NOT NULL,
              audio_filename TEXT,
              FOREIGN KEY(run_id) REFERENCES case_runs(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS simulation_rounds (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              run_id INTEGER NOT NULL,
              round_number INTEGER NOT NULL,
              adoption_rate REAL NOT NULL,
              rejection_rate REAL NOT NULL,
              neutral_rate REAL NOT NULL,
              dominant_mechanism TEXT NOT NULL,
              notable_shift TEXT NOT NULL,
              posts_json TEXT NOT NULL,
              FOREIGN KEY(run_id) REFERENCES case_runs(id)
            )
            """
        )
        conn.commit()


def _ensure_agent_outcome_columns(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(agent_outcomes)").fetchall()
    columns = {str(row[1]) for row in rows}
    if "demographics_json" not in columns:
        conn.execute("ALTER TABLE agent_outcomes ADD COLUMN demographics_json TEXT NOT NULL DEFAULT '{}'")
    if "spread_notes" not in columns:
        conn.execute("ALTER TABLE agent_outcomes ADD COLUMN spread_notes TEXT NOT NULL DEFAULT ''")


def persist_case_run(
    *,
    domain: str,
    city_id: str,
    case_goal: str,
    evidence: dict[str, Any],
    analysis_text: str,
    source_excerpt: str | None,
    source_warning: str | None,
    claim: dict[str, Any],
    fidelity: float,
    response: dict[str, Any],
    agent_rows: list[dict[str, Any]],
    round_rows: list[dict[str, Any]] | None = None,
) -> int:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        _ensure_agent_outcome_columns(conn)
        cursor = conn.execute(
            """
            INSERT INTO case_runs (
              domain, city_id, case_goal, evidence_json, analysis_text,
              source_excerpt, source_warning, claim_json, fidelity, response_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
              domain,
              city_id,
              case_goal,
              json.dumps(evidence),
              analysis_text,
              source_excerpt,
              source_warning,
              json.dumps(claim),
              fidelity,
              json.dumps(response),
            ),
        )
        run_id = int(cursor.lastrowid)
        conn.executemany(
            """
            INSERT INTO agent_outcomes (
              run_id, agent_id, name, role, latitude, longitude,
              demographics_json, spread_notes, tribe_json, calibrated_json, traits_json, score_json, outcome_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    row["agent_id"],
                    row["name"],
                    row["role"],
                    row["latitude"],
                    row["longitude"],
                    json.dumps(row.get("demographics") or {}),
                    str(row.get("spread_notes") or ""),
                    json.dumps(row["tribe"]),
                    json.dumps(row["calibrated"]),
                    json.dumps(row["traits"]),
                    json.dumps(row["scores"]),
                    json.dumps(row["outcome"]),
                )
                for row in agent_rows
            ],
        )
        if round_rows:
            conn.executemany(
                """
                INSERT INTO simulation_rounds (
                  run_id, round_number, adoption_rate, rejection_rate, neutral_rate,
                  dominant_mechanism, notable_shift, posts_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        row["round_number"],
                        row["adoption_rate"],
                        row["rejection_rate"],
                        row["neutral_rate"],
                        row["dominant_mechanism"],
                        row["notable_shift"],
                        json.dumps(row["posts"]),
                    )
                    for row in round_rows
                ],
            )
        conn.commit()
    return run_id


def fetch_case_run(run_id: int) -> dict[str, Any] | None:
    path = _db_path()
    if not path.exists():
        return None
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM case_runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "domain": row["domain"],
            "city_id": row["city_id"],
            "case_goal": row["case_goal"],
            "evidence": json.loads(row["evidence_json"]),
            "analysis_text": row["analysis_text"],
            "source_excerpt": row["source_excerpt"],
            "source_warning": row["source_warning"],
            "claim": json.loads(row["claim_json"]),
            "fidelity": row["fidelity"],
            "response": json.loads(row["response_json"]),
        }


def list_recent_runs(limit: int = 10) -> list[dict[str, Any]]:
    path = _db_path()
    if not path.exists():
        return []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, created_at, domain, city_id, case_goal, claim_json, fidelity FROM case_runs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "domain": row["domain"],
                "city_id": row["city_id"],
                "case_goal": row["case_goal"],
                "claim": json.loads(row["claim_json"]),
                "fidelity": row["fidelity"],
            }
            for row in rows
        ]


def fetch_agent_outcome(run_id: int, agent_id: int) -> dict[str, Any] | None:
    path = _db_path()
    if not path.exists():
        return None
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_agent_outcome_columns(conn)
        row = conn.execute(
            "SELECT * FROM agent_outcomes WHERE run_id = ? AND agent_id = ?",
            (run_id, agent_id),
        ).fetchone()
        if row is None:
            return None
        return {
            "run_id": row["run_id"],
            "agent_id": row["agent_id"],
            "name": row["name"],
            "role": row["role"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "demographics": json.loads(row["demographics_json"]) if row["demographics_json"] else {},
            "spread_notes": row["spread_notes"] or "",
            "tribe": json.loads(row["tribe_json"]),
            "calibrated": json.loads(row["calibrated_json"]),
            "traits": json.loads(row["traits_json"]),
            "scores": json.loads(row["score_json"]),
            "outcome": json.loads(row["outcome_json"]),
        }


def list_run_agents(run_id: int, limit: int = 250) -> list[dict[str, Any]]:
    path = _db_path()
    if not path.exists():
        return []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_agent_outcome_columns(conn)
        rows = conn.execute(
            """
            SELECT * FROM agent_outcomes
            WHERE run_id = ?
            ORDER BY agent_id ASC
            LIMIT ?
            """,
            (run_id, limit),
        ).fetchall()
        return [
            {
                "run_id": row["run_id"],
                "agent_id": row["agent_id"],
                "name": row["name"],
                "role": row["role"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "demographics": json.loads(row["demographics_json"]) if row["demographics_json"] else {},
                "spread_notes": row["spread_notes"] or "",
                "tribe": json.loads(row["tribe_json"]),
                "calibrated": json.loads(row["calibrated_json"]),
                "traits": json.loads(row["traits_json"]),
                "scores": json.loads(row["score_json"]),
                "outcome": json.loads(row["outcome_json"]),
            }
            for row in rows
        ]


def append_agent_conversation(
    *,
    run_id: int,
    agent_id: int,
    user_message: str,
    agent_reply: str,
    sentiment: str,
    stance: str,
    audio_filename: str | None,
) -> int:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO agent_conversations (
              run_id, agent_id, user_message, agent_reply, sentiment, stance, audio_filename
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, agent_id, user_message, agent_reply, sentiment, stance, audio_filename),
        )
        conn.commit()
        return int(cursor.lastrowid)


def update_agent_spread_notes(*, run_id: int, agent_id: int, spread_notes: str) -> None:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        _ensure_agent_outcome_columns(conn)
        conn.execute(
            """
            UPDATE agent_outcomes
            SET spread_notes = ?
            WHERE run_id = ? AND agent_id = ?
            """,
            (spread_notes, run_id, agent_id),
        )
        conn.commit()


def list_agent_conversations(run_id: int, agent_id: int, limit: int = 12) -> list[dict[str, Any]]:
    path = _db_path()
    if not path.exists():
        return []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, created_at, user_message, agent_reply, sentiment, stance, audio_filename
            FROM agent_conversations
            WHERE run_id = ? AND agent_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (run_id, agent_id, limit),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "user_message": row["user_message"],
                "agent_reply": row["agent_reply"],
                "sentiment": row["sentiment"],
                "stance": row["stance"],
                "audio_filename": row["audio_filename"],
            }
            for row in reversed(rows)
        ]


def list_simulation_rounds(run_id: int) -> list[dict[str, Any]]:
    path = _db_path()
    if not path.exists():
        return []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT round_number, adoption_rate, rejection_rate, neutral_rate,
                   dominant_mechanism, notable_shift, posts_json
            FROM simulation_rounds
            WHERE run_id = ?
            ORDER BY round_number ASC
            """,
            (run_id,),
        ).fetchall()
        return [
            {
                "round": row["round_number"],
                "adoption_rate": row["adoption_rate"],
                "rejection_rate": row["rejection_rate"],
                "neutral_rate": row["neutral_rate"],
                "dominant_mechanism": row["dominant_mechanism"],
                "notable_shift": row["notable_shift"],
                "posts": json.loads(row["posts_json"]),
            }
            for row in rows
        ]
