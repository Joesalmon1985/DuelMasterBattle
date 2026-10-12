"""Ware conservation check shared by the tests and the evidence reports (ARCHITECTURE_CONTRACT section 5).

A ware is made (stats made_<ware>, counted when it lands in a stock, on a belt or in a machine buffer), held (stock, flag, carrier,
belt tile, machine buffer) or consumed (stats consumed_<ware>, which also logs wares lost with a destroyed machine).
`snapshot_totals` records the held amounts and the made/consumed counters at one moment; `check` later reports every ware whose
books do not balance: held_now + consumed_since == held_then + made_since.
"""

from __future__ import annotations

from typing import Any

from wizard_rts.industry import sim as industry
from wizard_rts.logistics import in_flight


def wares_in(world: Any) -> set[str]:
    out = {g for s in world.stocks.values() for g in s}
    out.update(g for u in world.units.values() for g in (u.get("cargo") or {}))
    out.update(k[len("made_"):] for k in world.stats if k.startswith("made_"))
    out.update(k[len("consumed_"):] for k in world.stats if k.startswith("consumed_"))
    out.update(industry.holdings(world))
    return out


def held(world: Any, good: str, extra: dict[str, int] | None = None) -> int:
    """Stocks, wares on roads, machine buffers and belts, and the cargo a live MCV or settlers' wagon is carrying to a new site."""
    ind = extra if extra is not None else industry.holdings(world)
    cargo = sum(int((u.get("cargo") or {}).get(good, 0)) for u in world.units.values() if u.get("alive", True))
    cargo += sum(int(c.get(good, 0)) for c in _queued_cargo(world))
    return sum(int(s.get(good, 0)) for s in world.stocks.values()) + in_flight(world, good) + ind.get(good, 0) + cargo


def _queued_cargo(world: Any) -> list[dict[str, int]]:
    """The load of a founder (MCV, settlers) that is being built: it left the store when work began and rides out with the vehicle."""
    from wizard_rts import construction as con

    out = []
    for b in world.buildings.values():
        for item in b.get("queue") or []:
            if item.get("state") == "building":
                rec = con.recipe_for(world, b, item["unit"]) or {}
                if rec.get("cargo"):
                    out.append(rec["cargo"])
    return out


def snapshot_totals(world: Any) -> dict[str, Any]:
    ind = industry.holdings(world)
    names = sorted(wares_in(world))
    return {"held": {g: held(world, g, ind) for g in names},
            "made": {g: int(world.stats.get("made_" + g, 0)) for g in names},
            "consumed": {g: int(world.stats.get("consumed_" + g, 0)) for g in names}}


def check(world: Any, snap: dict[str, Any] | None = None) -> list[tuple[str, int, int]]:
    """Wares whose books do not balance: (ware, held+consumed, held_then+made). `snap` None means since world creation."""
    snap = snap or {"held": {}, "made": {}, "consumed": {}}
    if "held" not in snap:  # an older call style: a plain held-amount dict taken at world creation
        snap = {"held": snap, "made": {}, "consumed": {}}
    ind = industry.holdings(world)
    bad = []
    for g in sorted(wares_in(world) | set(snap["held"])):
        have = held(world, g, ind) + int(world.stats.get("consumed_" + g, 0)) - snap["consumed"].get(g, 0)
        want = int(snap["held"].get(g, 0)) + int(world.stats.get("made_" + g, 0)) - snap["made"].get(g, 0)
        if have != want:
            bad.append((g, have, want))
    return bad
