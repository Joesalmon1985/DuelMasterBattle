"""Logic blocks (processors, memory, displays, switches, messages): filled in by the logic stage."""
from __future__ import annotations

from typing import Any


def init_logic(world: Any, b: dict, m: dict, spec: dict) -> None:
    m.update(code="", pc=0, vars={}, links=[], text="", cells=[0.0] * 64, display=[], enabled=True)


def step(world: Any, st: Any, b: dict, m: dict, spec: dict, s: float) -> None:
    m["state"] = "idle"
