"""Target metros for API simulation (aligned with frontend `data/cities.ts`)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CityPreset:
    id: str
    label: str
    longitude: float
    latitude: float
    zoom: float
    span: float


CITY_PRESETS: list[CityPreset] = [
    CityPreset("la", "Los Angeles, CA", -118.2437, 34.0522, 10.5, 0.22),
    CityPreset("sf", "San Francisco, CA", -122.4194, 37.7749, 11, 0.12),
    CityPreset("sd", "San Diego, CA", -117.1611, 32.7157, 10.5, 0.18),
    CityPreset("sj", "San Jose, CA", -121.8863, 37.3382, 10.5, 0.15),
    CityPreset("sac", "Sacramento, CA", -121.4944, 38.5816, 10, 0.14),
]


def get_city(city_id: str) -> CityPreset:
    for c in CITY_PRESETS:
        if c.id == city_id:
            return c
    return CITY_PRESETS[0]
