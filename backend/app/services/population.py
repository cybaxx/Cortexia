"""Population generation for the simulation engine.

Generates virtual agents with diverse demographics and persists them
via the population store so every simulation run draws from a stable pool.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from app.city_presets import get_city
from app.population_store import fetch_population, save_population
from app.services.shared_math import clamp as _clamp


ROLES = (
    "Civic analyst",
    "Field organizer",
    "Educator",
    "Healthcare worker",
    "Policy aide",
    "Journalist",
    "Engineer",
    "Small business owner",
    "Researcher",
    "First responder",
    "Operations lead",
)

LOW_FORMAL_EDUCATION_LEVELS = (
    "Less than high school",
    "Limited formal schooling",
)

FIRST = [
    "Ava",
    "Noah",
    "Mia",
    "Liam",
    "Zoe",
    "Eli",
    "Maya",
    "Owen",
    "Iris",
    "Kai",
    "Lena",
    "Theo",
    "Nora",
    "Ezra",
]
LAST = [
    "Ramos",
    "Chen",
    "Patel",
    "Nguyen",
    "Okafor",
    "Silva",
    "Khan",
    "Walsh",
    "Brooks",
    "Tanaka",
    "Mendez",
    "Park",
    "Aoki",
    "Diallo",
]


@dataclass(frozen=True)
class _Demographics:
    age_band: str
    age_years: int
    education_level: str
    income_band: str
    housing_status: str
    language_profile: str
    community_tenure: str
    caregiving_load: str
    digital_media_habit: str


@dataclass(frozen=True)
class _Virt:
    id: int
    name: str
    role: str
    lat: float
    lng: float
    demographics: _Demographics


def _compress_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _seeded(i: int) -> float:
    x = math.sin(i * 9301 + 49297) * 233280
    return x - math.floor(x)


def _upper_first(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()][:6]


def _education_diversity_floor(count: int) -> int:
    """Minimum agents with `LOW_FORMAL_EDUCATION_LEVELS` so traits (literacy / susceptibility) span enough to color the map."""
    if count <= 0:
        return 0
    return min(count, max(6, int(round(count * 0.15))))


def _is_low_formal_education(level: str) -> bool:
    return level in LOW_FORMAL_EDUCATION_LEVELS


def _supports_low_formal_education(role: str) -> bool:
    lowered = role.lower()
    return not any(token in lowered for token in ("analyst", "research", "engineer", "journal", "policy"))


def _ensure_population_education_mix(city_id: str, agents: list[_Virt]) -> list[_Virt]:
    target_floor = _education_diversity_floor(len(agents))
    current = sum(1 for agent in agents if _is_low_formal_education(agent.demographics.education_level))
    if current >= target_floor:
        return agents

    candidates = sorted(
        [
            agent for agent in agents
            if not _is_low_formal_education(agent.demographics.education_level)
            and _supports_low_formal_education(agent.role)
        ],
        key=lambda agent: (_seeded(agent.id * 97 + 41), agent.id),
    )
    if not candidates:
        return agents

    replacements: dict[int, _Virt] = {}
    persisted_updates: list[dict[str, object]] = []
    for index, agent in enumerate(candidates[: max(0, target_floor - current)]):
        new_education = LOW_FORMAL_EDUCATION_LEVELS[index % len(LOW_FORMAL_EDUCATION_LEVELS)]
        updated = _Virt(
            id=agent.id,
            name=agent.name,
            role=agent.role,
            lat=agent.lat,
            lng=agent.lng,
            demographics=_Demographics(
                age_band=agent.demographics.age_band,
                age_years=agent.demographics.age_years,
                education_level=new_education,
                income_band=agent.demographics.income_band,
                housing_status=agent.demographics.housing_status,
                language_profile=agent.demographics.language_profile,
                community_tenure=agent.demographics.community_tenure,
                caregiving_load=agent.demographics.caregiving_load,
                digital_media_habit=agent.demographics.digital_media_habit,
            ),
        )
        replacements[agent.id] = updated
        persisted_updates.append(
            {
                "id": updated.id,
                "name": updated.name,
                "role": updated.role,
                "lat": updated.lat,
                "lng": updated.lng,
                "demographics": {
                    "age_band": updated.demographics.age_band,
                    "age_years": updated.demographics.age_years,
                    "education_level": updated.demographics.education_level,
                    "income_band": updated.demographics.income_band,
                    "housing_status": updated.demographics.housing_status,
                    "language_profile": updated.demographics.language_profile,
                    "community_tenure": updated.demographics.community_tenure,
                    "caregiving_load": updated.demographics.caregiving_load,
                    "digital_media_habit": updated.demographics.digital_media_habit,
                },
            }
        )

    if persisted_updates:
        save_population(city_id, persisted_updates)
    return [replacements.get(agent.id, agent) for agent in agents]


def _build_virtual_population(city_id: str, count: int) -> list[_Virt]:
    existing_agents = fetch_population(city_id, count)
    out: list[_Virt] = []

    for item in existing_agents:
        demo_dict = item["demographics"]
        out.append(
            _Virt(
                id=item["id"],
                name=item["name"],
                role=item["role"],
                lat=item["lat"],
                lng=item["lng"],
                demographics=_Demographics(
                    age_band=demo_dict["age_band"],
                    age_years=demo_dict["age_years"],
                    education_level=demo_dict["education_level"],
                    income_band=demo_dict["income_band"],
                    housing_status=demo_dict["housing_status"],
                    language_profile=demo_dict["language_profile"],
                    community_tenure=demo_dict["community_tenure"],
                    caregiving_load=demo_dict["caregiving_load"],
                    digital_media_habit=demo_dict["digital_media_habit"],
                ),
            )
        )

    if len(out) >= count:
        return _ensure_population_education_mix(city_id, out)

    # Generate missing agents
    city = get_city(city_id)
    zones = list(city.land_zones)
    zone_areas = [
        max(0.000001, (zone.lng_max - zone.lng_min) * (zone.lat_max - zone.lat_min))
        for zone in zones
    ]
    total_area = sum(zone_areas)
    cumulative: list[float] = []
    running = 0.0
    for area in zone_areas:
        running += area / total_area
        cumulative.append(running)

    new_agents_data = []
    start_id = len(out)

    for i in range(start_id, count):
        zone_pick = _seeded(i + 8500)
        zone_idx = next((idx for idx, bound in enumerate(cumulative) if zone_pick <= bound), 0)
        zone = zones[max(0, zone_idx)]
        r1 = _seeded(i + 1)
        r2 = _seeded(i + 1001)
        lng_inset = (zone.lng_max - zone.lng_min) * 0.08
        lat_inset = (zone.lat_max - zone.lat_min) * 0.08
        role = ROLES[i % len(ROLES)]
        lat = zone.lat_min + lat_inset + r2 * max(0.0001, zone.lat_max - zone.lat_min - lat_inset * 2)
        lng = zone.lng_min + lng_inset + r1 * max(0.0001, zone.lng_max - zone.lng_min - lng_inset * 2)
        name = f"{FIRST[i % len(FIRST)]} {LAST[(i * 3) % len(LAST)]}"
        
        demographics = _generate_demographics(
            agent_id=i,
            role=role,
            lat=lat,
            lng=lng,
            city_id=city_id,
        )

        virt = _Virt(
            id=i,
            name=name,
            role=role,
            lat=lat,
            lng=lng,
            demographics=demographics,
        )
        out.append(virt)

        new_agents_data.append({
            "id": virt.id,
            "name": virt.name,
            "role": virt.role,
            "lat": virt.lat,
            "lng": virt.lng,
            "demographics": {
                "age_band": demographics.age_band,
                "age_years": demographics.age_years,
                "education_level": demographics.education_level,
                "income_band": demographics.income_band,
                "housing_status": demographics.housing_status,
                "language_profile": demographics.language_profile,
                "community_tenure": demographics.community_tenure,
                "caregiving_load": demographics.caregiving_load,
                "digital_media_habit": demographics.digital_media_habit,
            }
        })

    if new_agents_data:
        save_population(city_id, new_agents_data)

    return _ensure_population_education_mix(city_id, out)


def _weighted_pick(seed: float, options: list[tuple[str, float]]) -> str:
    total = max(0.0001, sum(weight for _, weight in options))
    cursor = 0.0
    for label, weight in options:
        cursor += weight / total
        if seed <= cursor:
            return label
    return options[-1][0]


def _age_band_for_role(role: str, agent_id: int) -> tuple[str, int]:
    lowered = role.lower()
    seed = _seeded(agent_id * 19 + 7)
    if any(token in lowered for token in ("policy", "analyst", "research", "operations")):
        band = _weighted_pick(seed, [("25-34", 0.28), ("35-44", 0.34), ("45-54", 0.24), ("55-64", 0.14)])
    elif any(token in lowered for token in ("educator", "health", "journal", "responder")):
        band = _weighted_pick(seed, [("25-34", 0.22), ("35-44", 0.31), ("45-54", 0.29), ("55-64", 0.18)])
    else:
        band = _weighted_pick(seed, [("18-24", 0.14), ("25-34", 0.3), ("35-44", 0.24), ("45-54", 0.18), ("55-64", 0.1), ("65+", 0.04)])
    ranges = {
        "18-24": (18, 24),
        "25-34": (25, 34),
        "35-44": (35, 44),
        "45-54": (45, 54),
        "55-64": (55, 64),
        "65+": (65, 74),
    }
    lo, hi = ranges[band]
    age_years = lo + int(_seeded(agent_id * 23 + 13) * (hi - lo + 1))
    return band, age_years


def _generate_demographics(*, agent_id: int, role: str, lat: float, lng: float, city_id: str) -> _Demographics:
    city = get_city(city_id)
    lat_span = max(0.001, max(zone.lat_max for zone in city.land_zones) - min(zone.lat_min for zone in city.land_zones))
    lng_span = max(0.001, max(zone.lng_max for zone in city.land_zones) - min(zone.lng_min for zone in city.land_zones))
    northness = _clamp((lat - min(zone.lat_min for zone in city.land_zones)) / lat_span)
    eastness = _clamp((lng - min(zone.lng_min for zone in city.land_zones)) / lng_span)
    lowered = role.lower()
    age_band, age_years = _age_band_for_role(role, agent_id)
    education_seed = _seeded(agent_id * 31 + 3)
    if any(token in lowered for token in ("analyst", "research", "engineer", "journal")):
        # Still degree-heavy, but real-world variance (certificate programs, incomplete degrees).
        education = _weighted_pick(
            education_seed,
            [
                ("Some college", 0.1),
                ("Associate", 0.14),
                ("Bachelor's", 0.34),
                ("Master's", 0.32),
                ("Professional/Doctoral", 0.1),
            ],
        )
    elif any(token in lowered for token in ("policy", "educator", "health")):
        education = _weighted_pick(
            education_seed,
            [
                ("High school", 0.08),
                ("Some college", 0.14),
                ("Associate", 0.22),
                ("Bachelor's", 0.34),
                ("Master's", 0.14),
                ("Professional/Doctoral", 0.06),
                ("Limited formal schooling", 0.02),
            ],
        )
    else:
        education = _weighted_pick(
            education_seed,
            [
                ("Less than high school", 0.06),
                ("Limited formal schooling", 0.06),
                ("High school", 0.22),
                ("Some college", 0.26),
                ("Associate", 0.16),
                ("Bachelor's", 0.16),
                ("Master's", 0.06),
                ("Professional/Doctoral", 0.02),
            ],
        )

    income_seed = _seeded(agent_id * 37 + 9)
    role_income_bias = 0.12 if any(token in lowered for token in ("engineer", "policy", "research")) else 0.06 if any(token in lowered for token in ("health", "educator", "operations")) else -0.02
    income_position = _clamp(0.18 + eastness * 0.22 + northness * 0.12 + role_income_bias + (income_seed - 0.5) * 0.22)
    if income_position >= 0.72:
        income_band = "Upper middle income"
    elif income_position >= 0.52:
        income_band = "Middle income"
    elif income_position >= 0.34:
        income_band = "Lower middle income"
    else:
        income_band = "Economically strained"

    housing_seed = _seeded(agent_id * 41 + 5)
    if income_band == "Economically strained":
        housing_status = _weighted_pick(housing_seed, [("Stable renter", 0.48), ("Multigenerational household", 0.28), ("Housing insecure", 0.24)])
    elif income_band == "Upper middle income":
        housing_status = _weighted_pick(housing_seed, [("Homeowner", 0.54), ("Stable renter", 0.3), ("Multigenerational household", 0.16)])
    else:
        housing_status = _weighted_pick(housing_seed, [("Stable renter", 0.42), ("Homeowner", 0.34), ("Multigenerational household", 0.18), ("Housing insecure", 0.06)])

    language_profile = _weighted_pick(
        _seeded(agent_id * 43 + 17),
        [
            ("English-dominant", 0.46),
            ("Bilingual English-Spanish", 0.34),
            ("English plus household language", 0.14),
            ("Multilingual household", 0.06),
        ],
    )
    community_tenure = _weighted_pick(
        _seeded(agent_id * 47 + 21),
        [
            ("Recent arrival", 0.14),
            ("Established resident", 0.36),
            ("Long-term resident", 0.34),
            ("Deeply rooted local", 0.16),
        ],
    )
    caregiving_load = _weighted_pick(
        _seeded(agent_id * 53 + 27),
        [
            ("Low caregiving load", 0.42),
            ("Shared caregiving", 0.38),
            ("Primary caregiver", 0.2),
        ],
    )
    digital_media_habit = _weighted_pick(
        _seeded(agent_id * 59 + 31),
        [
            ("Local-news heavy", 0.26),
            ("Group-chat heavy", 0.24),
            ("Public-feed heavy", 0.24),
            ("Mixed verification habit", 0.26),
        ],
    )
    return _Demographics(
        age_band=age_band,
        age_years=age_years,
        education_level=education,
        income_band=income_band,
        housing_status=housing_status,
        language_profile=language_profile,
        community_tenure=community_tenure,
        caregiving_load=caregiving_load,
        digital_media_habit=digital_media_habit,
    )
