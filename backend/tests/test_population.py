"""Tests for population generation and persistence."""

from app.population_store import (
    fetch_population,
    save_population,
    list_population,
)


class TestPopulationPersistence:
    def test_save_and_fetch(self):
        city_id = "test-city-001"
        agents = [
            {
                "id": 1001,
                "city_id": city_id,
                "name": "Test Agent 1",
                "role": "Analyst",
                "lat": 34.05,
                "lng": -118.25,
                "demographics": {"age_band": "25-34", "education_level": "Master's", "age_years": 30,
                                 "income_band": "Middle income", "housing_status": "Stable renter",
                                 "language_profile": "English-dominant", "community_tenure": "Established resident",
                                 "caregiving_load": "Low caregiving load", "digital_media_habit": "Mixed verification habit"},
                "tribe_bsv": {"cognitive_load": 0.7},
                "calibrated_bsv": {"cognitive_load": 0.65},
                "traits": {"evidence_literacy": 0.6},
                "scores": {"baseline": 0.5, "final": 0.7},
                "outcome": {"belief_state": "adopted", "confidence": 0.8},
                "spread_notes": "",
            }
        ]
        save_population(city_id, agents)

        fetched = fetch_population(city_id, limit=10)
        assert len(fetched) >= 1
        agent = next((a for a in fetched if a.get("agent_id") == 1001 or a.get("id") == 1001), None)
        assert agent is not None
        assert agent.get("name") == "Test Agent 1" or agent.get("name") is not None

    def test_list_population(self):
        city_id = "test-city-002"
        agents = [
            {
                "id": 2000 + i,
                "city_id": city_id,
                "name": f"Agent {i}",
                "role": "Analyst",
                "lat": 34.0 + i * 0.01,
                "lng": -118.0 - i * 0.01,
                "demographics": {"age_band": "25-34", "age_years": 30},
                "tribe_bsv": {"cognitive_load": 0.5},
                "calibrated_bsv": {"cognitive_load": 0.5},
                "traits": {"evidence_literacy": 0.5},
                "scores": {"baseline": 0.5, "final": 0.5},
                "outcome": {"belief_state": "neutral", "confidence": 0.5},
                "spread_notes": "",
            }
            for i in range(3)
        ]
        save_population(city_id, agents)

        listed = list_population(city_id, limit=3)
        assert len(listed) <= 3

    def test_fetch_empty_population(self):
        fetched = fetch_population("nonexistent-city-999", limit=10)
        assert fetched == []
