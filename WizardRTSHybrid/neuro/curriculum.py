"""Catastrophe curriculum configuration (decision N10; execution plan T4.4; design 7.8).

A ladder of named levels, easiest first, each with the `outbreak_interval_scale` it applies to the world (smaller scale = outbreaks come sooner = harder).
Stage 1 has exactly one rung, C0 = the default cadence (scale 1.0). Later rungs are added only on the owner's decision (milestone M10); this module only
validates, serialises and draws levels.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Curriculum:
    levels: dict[str, float] = field(default_factory=lambda: {"C0": 1.0})  # label -> outbreak_interval_scale, easiest to hardest
    current: str = "C0"
    retention_fraction: float = 0.25
    retention_tolerance: float = 50.0

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not self.levels:
            raise ValueError("a curriculum needs at least one level")
        labels = list(self.levels)
        if len(set(labels)) != len(labels):
            raise ValueError("duplicate level labels")
        scales = [float(self.levels[k]) for k in labels]
        if scales[0] != 1.0:
            raise ValueError(f"the first level must be the default cadence (scale 1.0), got {scales[0]}")
        for a, b in zip(scales, scales[1:]):
            if not b < a:
                raise ValueError(f"scales must strictly decrease along the ladder: {scales}")
        if any(not 0.0 < s <= 1.0 for s in scales):
            raise ValueError(f"scales must lie in (0, 1]: {scales}")
        if self.current not in self.levels:
            raise ValueError(f"current level {self.current!r} is not one of {labels}")
        if not 0.0 <= self.retention_fraction <= 1.0:
            raise ValueError("retention_fraction must be in [0, 1]")
        if self.retention_tolerance < 0:
            raise ValueError("retention_tolerance must be >= 0")

    def scale_of(self, level: str) -> float:
        if level not in self.levels:
            raise ValueError(f"unknown catastrophe level {level!r}; the ladder is {list(self.levels)}")
        return float(self.levels[level])

    def earlier(self) -> list[str]:
        out = []
        for k in self.levels:
            if k == self.current:
                break
            out.append(k)
        return out

    def draw(self, rng: np.random.Generator) -> str:
        """`current`, except that with probability retention_fraction an earlier level (uniform) is drawn when one exists."""
        early = self.earlier()
        if early and rng.random() < self.retention_fraction:
            return early[int(rng.integers(0, len(early)))]
        return self.current

    def to_json(self) -> dict:
        return {"levels": {k: float(v) for k, v in self.levels.items()}, "current": self.current, "retention_fraction": float(self.retention_fraction),
                "retention_tolerance": float(self.retention_tolerance)}

    @staticmethod
    def from_json(d: dict | None) -> "Curriculum":
        if not d:
            return Curriculum()
        return Curriculum(levels={str(k): float(v) for k, v in d.get("levels", {"C0": 1.0}).items()}, current=str(d.get("current", "C0")),
                          retention_fraction=float(d.get("retention_fraction", 0.25)), retention_tolerance=float(d.get("retention_tolerance", 50.0)))
