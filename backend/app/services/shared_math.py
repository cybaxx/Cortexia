"""Shared math utilities — single source for clamp, sigmoid.

Previously duplicated in tribe_framework.py, modal_app.py, and api_simulation.py.
"""

from __future__ import annotations

import math


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp a value to [lo, hi]."""
    return max(lo, min(hi, value))


def sigmoid(value: float) -> float:
    """Standard logistic sigmoid: 1 / (1 + exp(-x))."""
    return 1.0 / (1.0 + math.exp(-value))
