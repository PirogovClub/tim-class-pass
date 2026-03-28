"""Enums for Stage 5.7 review metrics API."""

from __future__ import annotations

from enum import Enum


class ThroughputWindow(str, Enum):
    """Rolling window for throughput metrics (UTC, ending at computation time)."""

    DAYS_7 = "7d"
    DAYS_30 = "30d"
