"""Per-faction ware flow: what each faction's own buildings made and consumed (side tables; they change no rule and are not in the state hash).

The world keeps global `made_*` and `consumed_*` counters for the ledger. A controller must not read those (they mix every faction), so the main
productive paths also record here, by the faction that owns the building: Widelands worker programmes, Mindustry machines, construction.
Sinks (fire, sabotage, trade losses, fixtures) are not recorded.

    world.ware_flow[faction]   = {"made": {ware: n}, "consumed": {ware: n}}   cumulative, per faction
    world.ware_flow_b[building id] = {"made": {...}, "consumed": {...}}       cumulative, per building (the settlement features sum over a settlement's buildings)

Features take differences over a window (neuro/observer.py).
"""
from __future__ import annotations

from typing import Any


def note(world: Any, building: dict, kind: str, good: str, n: int = 1) -> None:
    n = int(n)
    flow = world.__dict__.setdefault("ware_flow", {})
    side = flow.setdefault(building["faction_name"], {"made": {}, "consumed": {}})[kind]
    side[good] = side.get(good, 0) + n
    per = world.__dict__.setdefault("ware_flow_b", {}).setdefault(building["id"], {"made": {}, "consumed": {}})[kind]
    per[good] = per.get(good, 0) + n
