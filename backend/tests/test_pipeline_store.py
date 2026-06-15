"""Tests for SQLite pipeline persistence."""

import json
import os
import pytest
from app.pipeline_store import (
    persist_case_run,
    fetch_case_run,
    list_recent_runs,
)
from app.config import get_settings


@pytest.fixture
def sample_response():
    return {
        "case_summary": {
            "title": "Test case",
            "goal": "test",
            "domain": "Political Campaign",
            "target_region": "Los Angeles, CA",
            "spread_risk": "High",
            "overall_confidence": 0.8,
            "key_finding": "Claim spread rapidly.",
            "recommended_next_step": "Monitor.",
        },
        "spread_model": {
            "risk_score": 75,
            "spread_risk": "High",
            "belief_adoption_rate": 85,
            "population_reached": 90,
            "avg_cognitive_load": 0.8,
            "avg_defensive_activation": 0.6,
            "high_risk_segments": [],
            "belief_adoption_pathways": [],
            "hotspots": [],
            "network_summary": "Test summary",
            "core_story": "Test story",
        },
        "mechanisms": {
            "mechanism_summary": "Test mechanism",
            "dominant_cognitive_drivers": [],
            "target_segments": [],
            "evidence_links": [],
            "confidence_notes": [],
        },
        "intervention_playbook": [],
        "evidence_trace": {
            "original_text": "test",
            "analysis_text": "test",
            "source_url": None,
            "source_excerpt": None,
            "speaker_context": None,
            "claims": [],
            "themes": [],
            "provenance": {"source_type": "text", "transcript_used": False, "analysis_text_source": "direct"},
            "warnings": [],
        },
        "swarm_dynamics": {
            "rounds": [],
            "narrative_summary": "Test swarm",
            "network_edges": [],
            "event_log": [],
        },
        "summary": {"total": 24, "adopted": 20, "rejected": 2, "neutral": 2},
        "agents": [],
        "macro_result": {"score": 75, "risk_level": "High", "insights": [], "suggested_rewrite": "", "synthetic_thoughts": []},
        "tribe_meta": {
            "provider": "tribe_neural_framework",
            "model_id": "facebook/tribev2",
        },
        "stage_trace": [{"stage": "source_fetch", "seconds": 0.0}],
        "city_id": "los-angeles-ca",
        "domain": "Political Campaign",
        "case_goal": "test",
        "effective_catalyst_text": "test catalyst",
        "run_id": None,
    }


class TestPersistAndFetch:
    def test_persist_and_fetch(self, sample_response):
        run_id = persist_case_run(
            domain="Political Campaign",
            city_id="los-angeles-ca",
            case_goal="test goal",
            evidence={"text_input": "test evidence", "speaker_context": ""},
            analysis_text="test analysis",
            source_excerpt=None,
            source_warning=None,
            claim={"credibility": 0.5, "harm": 0.3, "virality": 0.2, "risk_label": "moderate"},
            fidelity=0.85,
            response=sample_response,
            agent_rows=[
                {
                    "agent_id": 0,
                    "name": "Test Agent",
                    "role": "Analyst",
                    "latitude": 34.05,
                    "longitude": -118.25,
                    "demographics": {"age_band": "25-34"},
                    "tribe": {"cognitive_load": 0.8},
                    "calibrated": {"cognitive_load": 0.75},
                    "traits": {"evidence_literacy": 0.6},
                    "scores": {"baseline": 0.5, "final": 0.7, "breakdown": {}},
                    "outcome": {"belief_state": "adopted", "confidence": 0.8, "dominant_signal": "social_proof"},
                    "spread_notes": "",
                }
            ],
            round_rows=[
                {
                    "round_number": 1,
                    "adoption_rate": 80,
                    "rejection_rate": 10,
                    "neutral_rate": 10,
                    "dominant_mechanism": "social_proof",
                    "notable_shift": "Initial spread",
                    "posts": [],
                }
            ],
        )

        assert isinstance(run_id, int)
        assert run_id > 0

        # Fetch it back
        record = fetch_case_run(run_id)
        assert record is not None
        assert record["domain"] == "Political Campaign"
        assert record["city_id"] == "los-angeles-ca"
        assert record["case_goal"] == "test goal"
        assert record["fidelity"] == 0.85
        ev = record.get("evidence", {})
        if isinstance(ev, str):
            ev = json.loads(ev)
        assert ev.get("text_input") == "test evidence"

        # Verify tribe_meta is persisted correctly (was a bug in original fork)
        response = record["response"]
        assert response["tribe_meta"]["provider"] == "tribe_neural_framework"
        assert response["tribe_meta"]["model_id"] == "facebook/tribev2"

    def test_list_recent_runs(self):
        runs = list_recent_runs(limit=5)
        assert isinstance(runs, list)
        for run in runs:
            assert "id" in run
            assert "created_at" in run
            assert "domain" in run
            assert "city_id" in run
            assert "case_goal" in run

    def test_fetch_nonexistent_run(self):
        record = fetch_case_run(999999)
        assert record is None
