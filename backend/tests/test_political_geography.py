"""Tests for political geography module."""

import pytest
from app.political_geography import (
    lookup_political_lean,
    get_political_zones_geojson,
    PoliticalContext,
)


class TestLookupPoliticalLean:
    def test_downtown_la_is_democratic(self):
        ctx = lookup_political_lean(34.05, -118.25, "los-angeles-ca")
        assert ctx.lean > 0.3
        assert "Downtown" in ctx.label or "East LA" in ctx.label or "Hollywood" in ctx.label

    def test_orange_county_edge_is_conservative(self):
        ctx = lookup_political_lean(33.78, -117.95, "los-angeles-ca")
        assert ctx.lean < 0.2  # swing/conservative-leaning

    def test_unknown_city_returns_neutral(self):
        ctx = lookup_political_lean(40.0, -75.0, "nonexistent-city")
        assert ctx.lean == 0.0
        assert ctx.homogeneity == 0.0
        assert ctx.label == "unknown"

    def test_homogeneity_is_nonzero_inside_zones(self):
        ctx_center = lookup_political_lean(34.05, -118.25, "los-angeles-ca")
        ctx_edge = lookup_political_lean(33.76, -117.94, "los-angeles-ca")
        # Both should have non-zero homogeneity (they're inside defined zones)
        assert ctx_center.homogeneity > 0.0
        assert ctx_edge.homogeneity > 0.0

    def test_all_six_cities_have_zones(self):
        for city in ("los-angeles-ca", "new-york-ny", "chicago-il", "miami-fl", "phoenix-az", "houston-tx"):
            ctx = lookup_political_lean(0, 0, city)
            assert -1.0 <= ctx.lean <= 1.0, f"{city} lean out of range"
            assert 0.0 <= ctx.homogeneity <= 1.0, f"{city} homogeneity out of range"

    def test_nyc_downtown_is_very_democratic(self):
        ctx = lookup_political_lean(40.75, -73.99, "new-york-ny")
        assert ctx.lean > 0.5

    def test_chicago_loop_is_democratic(self):
        ctx = lookup_political_lean(41.88, -87.63, "chicago-il")
        assert ctx.lean > 0.5

    def test_miami_dade_is_purple(self):
        ctx = lookup_political_lean(25.77, -80.19, "miami-fl")
        assert abs(ctx.lean) < 0.7  # swing county


class TestGeoJSON:
    def test_la_has_zones(self):
        geojson = get_political_zones_geojson("los-angeles-ca")
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) >= 10

    def test_features_have_required_properties(self):
        geojson = get_political_zones_geojson("los-angeles-ca")
        for feature in geojson["features"]:
            assert "geometry" in feature
            assert feature["geometry"]["type"] == "Polygon"
            assert "properties" in feature
            assert "lean" in feature["properties"]
            assert "label" in feature["properties"]
            assert "fill" in feature["properties"]
            assert -1.0 <= feature["properties"]["lean"] <= 1.0

    def test_unknown_city_returns_empty(self):
        geojson = get_political_zones_geojson("unknown")
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == 0
