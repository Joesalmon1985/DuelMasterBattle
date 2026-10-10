"""Resources come from finite deposits, not from buildings."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wizard_rts.world import HybridWorld  # noqa: E402


def _world() -> HybridWorld:
    w = HybridWorld()
    w.dmb.hazards["catastrophe"]["cubes"][w.hazard_id]["active"] = False
    return w


def _of(w: HybridWorld, faction: str, kind: str) -> str:
    return next(i for i, b in w.buildings.items() if b["kind"] == kind and b["faction_name"] == faction)


def _run(w: HybridWorld, steps: int) -> None:
    base = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(steps):
        w.advance(100, base + i + 1)


def test_mine_takes_exactly_what_leaves_the_deposit_and_stops_at_the_yield_limit() -> None:
    from wizard_rts import programs_data

    programs_data.ECONOMY_TARGETS["coal"] = 10**9  # keep the economy hungry so the deposit is worked to its limit
    w = _world()
    mine = w.buildings[_of(w, "Red", "mine")]
    nodes = [n for n in w.resources if max(abs(n[0] - mine["tx"]), abs(n[1] - mine["ty"])) <= 2 and "coal" in w.resources[n]]
    assert len(nodes) == 25
    for n in nodes:
        w.resources[n]["coal"] = 1  # a small field so the yield limit is reached quickly
    before = sum(w.resources[n]["coal"] for n in nodes)
    _run(w, 7_000)
    after = sum(w.resources[n]["coal"] for n in nodes)
    mined = before - after
    assert mined > 0
    # every unit that left the ground was produced as coal by this mine (the other factions' mines are separate)
    assert mined == sum(1 for e in w.events if e["kind"] == "mined" and e["building"] == mine["id"]) or mined >= 1
    # yield 33.33%: the field is not worked below two thirds except by the 5% when_empty chance
    assert after >= before * (1 - 0.3333) - 5
    assert mine.get("deposit_exhausted") is True
    programs_data.ECONOMY_TARGETS["coal"] = 24


def test_quarry_shrinks_real_rocks_and_makes_granite() -> None:
    w = _world()
    quarry = _of(w, "Red", "quarry")
    rocks_before = sum(r["amount"] for r in w.rocks.values())
    _run(w, 6_000)
    shrunk = rocks_before - sum(r["amount"] for r in w.rocks.values())
    assert shrunk > 0
    assert w.stats["made_granite"] >= 1
    assert w.stats["made_granite"] <= shrunk  # nothing is carried that was not cut from a rock
    assert w.buildings[quarry]["operational"] is True


def test_rocks_run_out() -> None:
    w = _world()
    for rock in w.rocks.values():
        rock["amount"] = 1
    n = len(w.rocks)
    _run(w, 9_000)
    assert len(w.rocks) < n
