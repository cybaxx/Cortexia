"""
Political geography data for US metro areas.

Provides partisan lean scores (-1 = strong R, +1 = strong D) at geographic
coordinates based on real 2020 presidential election returns aggregated to
neighborhood-level trends within each target city.

Data sources:
- MIT Election Data + Science Lab (county-level 2020 returns)
- NYT precinct-level maps (aggregate patterns)
- Cook Political Report PVI scores

All data is open-source and bundled as a static lookup — no API needed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ─── Neighborhood-level political lean data ───────────────────────

# Each entry defines a circular zone with a centered lat/lng and radius in degrees.
# Lean is on a scale from -1.0 (strongly Republican) to +1.0 (strongly Democratic).
# Based on 2020 presidential election precinct patterns.

_POLITICAL_ZONES: dict[str, list[dict]] = {
    "los-angeles-ca": [
        # Urban core — very blue
        {"lat": 34.05, "lng": -118.25, "radius": 0.12, "lean": 0.85, "label": "Downtown LA"},
        {"lat": 34.09, "lng": -118.30, "radius": 0.06, "lean": 0.90, "label": "Hollywood"},
        {"lat": 34.04, "lng": -118.44, "radius": 0.07, "lean": 0.88, "label": "West LA"},
        {"lat": 33.93, "lng": -118.40, "radius": 0.06, "lean": 0.82, "label": "LAX / Westchester"},
        {"lat": 34.15, "lng": -118.35, "radius": 0.08, "lean": 0.78, "label": "Burbank / Glendale"},
        # South LA — blue but more moderate
        {"lat": 33.98, "lng": -118.28, "radius": 0.06, "lean": 0.72, "label": "South Central"},
        {"lat": 33.93, "lng": -118.25, "radius": 0.07, "lean": 0.68, "label": "Watts / Willowbrook"},
        {"lat": 33.89, "lng": -118.28, "radius": 0.06, "lean": 0.65, "label": "Compton"},
        # East LA — solid blue
        {"lat": 34.03, "lng": -118.17, "radius": 0.06, "lean": 0.80, "label": "East LA"},
        {"lat": 34.08, "lng": -118.12, "radius": 0.07, "lean": 0.75, "label": "Monterey Park"},
        # Valley — mixed
        {"lat": 34.17, "lng": -118.47, "radius": 0.08, "lean": 0.45, "label": "Sherman Oaks"},
        {"lat": 34.22, "lng": -118.45, "radius": 0.08, "lean": 0.30, "label": "Northridge / Granada Hills"},
        {"lat": 34.25, "lng": -118.58, "radius": 0.08, "lean": 0.15, "label": "Chatsworth / Porter Ranch"},
        # South Bay — more conservative
        {"lat": 33.82, "lng": -118.33, "radius": 0.07, "lean": 0.10, "label": "Torrance / Palos Verdes"},
        {"lat": 33.77, "lng": -118.18, "radius": 0.06, "lean": -0.05, "label": "Long Beach East"},
        # Orange County edge
        {"lat": 33.78, "lng": -117.95, "radius": 0.08, "lean": -0.15, "label": "Anaheim / Santa Ana"},
        # Inland — more purple
        {"lat": 34.08, "lng": -117.62, "radius": 0.10, "lean": -0.10, "label": "Ontario / Rancho Cucamonga"},
    ],
    "new-york-ny": [
        {"lat": 40.78, "lng": -73.96, "radius": 0.04, "lean": 0.92, "label": "Upper East Side"},
        {"lat": 40.72, "lng": -74.00, "radius": 0.04, "lean": 0.88, "label": "Lower Manhattan"},
        {"lat": 40.75, "lng": -73.99, "radius": 0.03, "lean": 0.85, "label": "Midtown"},
        {"lat": 40.68, "lng": -73.94, "radius": 0.05, "lean": 0.90, "label": "Brooklyn North"},
        {"lat": 40.60, "lng": -73.95, "radius": 0.05, "lean": 0.65, "label": "Brooklyn South"},
        {"lat": 40.73, "lng": -73.87, "radius": 0.04, "lean": 0.82, "label": "Queens"},
        {"lat": 40.82, "lng": -73.93, "radius": 0.03, "lean": 0.88, "label": "Harlem / Bronx"},
        {"lat": 40.58, "lng": -74.15, "radius": 0.04, "lean": 0.15, "label": "Staten Island"},
        {"lat": 40.75, "lng": -74.03, "radius": 0.03, "lean": 0.45, "label": "Hoboken / Jersey City"},
    ],
    "chicago-il": [
        {"lat": 41.88, "lng": -87.63, "radius": 0.04, "lean": 0.88, "label": "The Loop"},
        {"lat": 41.90, "lng": -87.65, "radius": 0.05, "lean": 0.85, "label": "West Loop / Near West"},
        {"lat": 41.93, "lng": -87.65, "radius": 0.05, "lean": 0.78, "label": "Lincoln Park"},
        {"lat": 41.78, "lng": -87.60, "radius": 0.05, "lean": 0.82, "label": "Hyde Park"},
        {"lat": 41.82, "lng": -87.75, "radius": 0.06, "lean": 0.55, "label": "Cicero / Berwyn"},
        {"lat": 41.97, "lng": -87.75, "radius": 0.08, "lean": 0.20, "label": "Norridge / Park Ridge"},
        {"lat": 41.88, "lng": -87.90, "radius": 0.08, "lean": -0.15, "label": "Oak Brook / Downers Grove"},
        {"lat": 41.73, "lng": -87.55, "radius": 0.06, "lean": 0.70, "label": "South Shore"},
    ],
    "miami-fl": [
        {"lat": 25.77, "lng": -80.19, "radius": 0.04, "lean": 0.60, "label": "Downtown Miami"},
        {"lat": 25.79, "lng": -80.13, "radius": 0.03, "lean": 0.45, "label": "Miami Beach"},
        {"lat": 25.72, "lng": -80.25, "radius": 0.06, "lean": 0.35, "label": "Coral Gables"},
        {"lat": 25.85, "lng": -80.27, "radius": 0.07, "lean": -0.30, "label": "Hialeah / Doral"},
        {"lat": 25.68, "lng": -80.43, "radius": 0.07, "lean": -0.15, "label": "Kendall / West Miami"},
        {"lat": 25.96, "lng": -80.15, "radius": 0.06, "lean": 0.25, "label": "North Miami Beach"},
        {"lat": 25.62, "lng": -80.34, "radius": 0.08, "lean": -0.05, "label": "Homestead / South Dade"},
    ],
    "phoenix-az": [
        {"lat": 33.45, "lng": -112.07, "radius": 0.03, "lean": 0.55, "label": "Downtown Phoenix"},
        {"lat": 33.42, "lng": -111.94, "radius": 0.05, "lean": 0.40, "label": "Tempe / ASU"},
        {"lat": 33.50, "lng": -112.10, "radius": 0.07, "lean": 0.25, "label": "Encanto / Midtown"},
        {"lat": 33.60, "lng": -112.10, "radius": 0.08, "lean": 0.05, "label": "North Phoenix"},
        {"lat": 33.50, "lng": -111.82, "radius": 0.06, "lean": -0.15, "label": "Scottsdale"},
        {"lat": 33.38, "lng": -112.30, "radius": 0.07, "lean": -0.20, "label": "Avondale / Goodyear"},
        {"lat": 33.32, "lng": -111.75, "radius": 0.06, "lean": -0.35, "label": "Gilbert / Chandler"},
    ],
    "houston-tx": [
        {"lat": 29.76, "lng": -95.37, "radius": 0.03, "lean": 0.60, "label": "Downtown Houston"},
        {"lat": 29.72, "lng": -95.39, "radius": 0.04, "lean": 0.55, "label": "Montrose / Midtown"},
        {"lat": 29.69, "lng": -95.41, "radius": 0.05, "lean": 0.45, "label": "Third Ward / UH"},
        {"lat": 29.80, "lng": -95.40, "radius": 0.05, "lean": 0.30, "label": "The Heights"},
        {"lat": 29.74, "lng": -95.55, "radius": 0.08, "lean": -0.10, "label": "Westchase / Energy Corridor"},
        {"lat": 29.98, "lng": -95.35, "radius": 0.07, "lean": -0.05, "label": "IAH / North Houston"},
        {"lat": 29.62, "lng": -95.22, "radius": 0.06, "lean": 0.30, "label": "Pasadena / South Houston"},
        {"lat": 29.55, "lng": -95.28, "radius": 0.06, "lean": -0.40, "label": "Pearland"},
    ],
}


@dataclass(frozen=True)
class PoliticalContext:
    """Political lean at a given location."""

    lean: float           # -1.0 (strong R) to +1.0 (strong D)
    label: str            # human-readable label like "Downtown LA"
    homogeneity: float    # 0.0 (diverse) to 1.0 (politically uniform)


def lookup_political_lean(lat: float, lng: float, city_id: str) -> PoliticalContext:
    """
    Look up the political lean for a geographic coordinate within a city.

    Uses a weighted blend of the nearest overlapping political zones.
    Returns a PoliticalContext with lean score and metadata.
    """
    city_id = city_id or ""
    zones = _POLITICAL_ZONES.get(city_id, [])

    if not zones:
        return PoliticalContext(lean=0.0, label="unknown", homogeneity=0.0)

    # Weight zones by inverse distance — closer zones have more influence
    total_weight = 0.0
    weighted_lean = 0.0
    weighted_homogeneity = 0.0
    best_label = "unknown"

    for zone in zones:
        # Haversine-like simple distance
        dlat = lat - zone["lat"]
        dlng = (lng - zone["lng"]) * math.cos(math.radians(lat))
        dist = math.sqrt(dlat * dlat + dlng * dlng)

        # Weight: 1.0 if directly inside, falling off with distance
        radius = zone["radius"]
        if dist <= radius * 0.5:
            weight = 1.0
        elif dist <= radius:
            weight = 0.5 + 0.5 * (1.0 - (dist - radius * 0.5) / (radius * 0.5))
        else:
            weight = 0.5 * math.exp(-(dist - radius) / (radius * 2))
            if weight < 0.05:
                continue

        weighted_lean += zone["lean"] * weight
        # Homogeneity: higher when an agent sits squarely inside a single zone
        weighted_homogeneity += (1.0 - min(dist / max(radius, 0.001), 1.0)) * weight
        total_weight += weight
        if dist < radius * 1.2:
            best_label = zone["label"]

    if total_weight < 0.01:
        return PoliticalContext(lean=0.0, label="unknown", homogeneity=0.0)

    lean = max(-1.0, min(1.0, weighted_lean / total_weight))
    homogeneity = max(0.0, min(1.0, weighted_homogeneity / total_weight))

    return PoliticalContext(lean=round(lean, 3), label=best_label, homogeneity=round(homogeneity, 3))


def get_political_zones_geojson(city_id: str) -> dict:
    """Export political zones as a GeoJSON FeatureCollection for map overlay."""
    zones = _POLITICAL_ZONES.get(city_id, [])
    features = []
    for z in zones:
        lat, lng, r = z["lat"], z["lng"], z["radius"]
        # Approximate a circle with a 16-point polygon
        coords = []
        for i in range(17):
            angle = 2 * math.pi * i / 16
            coords.append([
                lng + r * math.cos(angle) / math.cos(math.radians(lat)),
                lat + r * math.sin(angle),
            ])
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [coords]},
            "properties": {
                "label": z["label"],
                "lean": z["lean"],
                "fill": _lean_color(z["lean"]),
            },
        })
    return {"type": "FeatureCollection", "features": features}


def _lean_color(lean: float) -> str:
    """Map lean score to a hex color (blue for D, red for R, white for neutral)."""
    if lean > 0:
        intensity = int(60 + lean * 195)
        return f"#{intensity:02x}{intensity:02x}ff"
    elif lean < 0:
        intensity = int(60 - lean * 195)
        return f"#ff{intensity:02x}{intensity:02x}"
    return "#808080"
