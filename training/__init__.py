"""Faction leadership training package (C12 / G09).

Uses the production simulator only. Heuristic clones are never labelled trained.
"""

from __future__ import annotations

__all__ = [
    "OBSERVATION_SCHEMA_PATH",
    "TrainingEnvironment",
]

from pathlib import Path

OBSERVATION_SCHEMA_PATH = Path(__file__).resolve().parent / "observation_schema.json"

from training.environment import TrainingEnvironment  # noqa: E402
