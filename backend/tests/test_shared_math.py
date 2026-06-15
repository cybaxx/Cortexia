"""Tests for shared math utilities."""

import math
import pytest
from app.services.shared_math import clamp, sigmoid


class TestClamp:
    def test_within_bounds(self):
        assert clamp(0.5) == 0.5
        assert clamp(0.5, 0.2, 0.8) == 0.5

    def test_below_lower(self):
        assert clamp(-0.5) == 0.0
        assert clamp(-0.5, 0.1, 0.9) == 0.1

    def test_above_upper(self):
        assert clamp(1.5) == 1.0
        assert clamp(1.5, 0.0, 0.8) == 0.8

    def test_custom_bounds(self):
        assert clamp(5, 2, 10) == 5
        assert clamp(-10, -5, 5) == -5
        assert clamp(100, -50, 50) == 50

    def test_boundary_values(self):
        assert clamp(0.0, 0.0, 1.0) == 0.0
        assert clamp(1.0, 0.0, 1.0) == 1.0


class TestSigmoid:
    def test_zero_input(self):
        assert sigmoid(0.0) == pytest.approx(0.5)

    def test_symmetry(self):
        assert sigmoid(2.0) == pytest.approx(1 - sigmoid(-2.0))

    def test_large_positive(self):
        assert sigmoid(10.0) > 0.999

    def test_large_negative(self):
        assert sigmoid(-10.0) < 0.001

    def test_monotonic(self):
        assert sigmoid(1.0) > sigmoid(0.0)
        assert sigmoid(2.0) > sigmoid(1.0)
