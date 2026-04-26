"""Target metros for API simulation (aligned with frontend `data/cities.ts`)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LandZone:
    lng_min: float
    lng_max: float
    lat_min: float
    lat_max: float


@dataclass(frozen=True)
class CityPreset:
    id: str
    label: str
    longitude: float
    latitude: float
    zoom: float
    span: float
    land_zones: tuple[LandZone, ...]


CITY_PRESETS: list[CityPreset] = [
    CityPreset(
        "la",
        "Los Angeles, CA",
        -118.2437,
        34.0522,
        10.5,
        0.22,
        (
            LandZone(-118.35, -118.14, 33.98, 34.14),
            LandZone(-118.18, -118.01, 33.97, 34.08),
            LandZone(-118.37, -118.20, 33.92, 33.98),
        ),
    ),
    CityPreset(
        "sf",
        "San Francisco, CA",
        -122.4194,
        37.7749,
        11,
        0.12,
        (
            LandZone(-122.51, -122.38, 37.71, 37.81),
            LandZone(-122.46, -122.38, 37.70, 37.71),
        ),
    ),
    CityPreset(
        "sd",
        "San Diego, CA",
        -117.1611,
        32.7157,
        10.5,
        0.18,
        (
            LandZone(-117.22, -117.05, 32.73, 32.80),
            LandZone(-117.17, -117.05, 32.69, 32.73),
            LandZone(-117.13, -117.05, 32.64, 32.69),
        ),
    ),
    CityPreset(
        "sj",
        "San Jose, CA",
        -121.8863,
        37.3382,
        10.5,
        0.15,
        (LandZone(-121.97, -121.82, 37.27, 37.41),),
    ),
    CityPreset(
        "sac",
        "Sacramento, CA",
        -121.4944,
        38.5816,
        10,
        0.14,
        (LandZone(-121.57, -121.42, 38.52, 38.64),),
    ),
]


def get_city(city_id: str) -> CityPreset:
    for c in CITY_PRESETS:
        if c.id == city_id:
            return c
    return CITY_PRESETS[0]
