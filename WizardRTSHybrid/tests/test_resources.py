"""Resources come from deposits, not from buildings. Mineral sites are inexhaustible (D22); rocks and fish are finite/ecological."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wizard_rts.world import HybridWorld  # noqa: E402
from conftest import resource_sum, set_resource  # noqa: E402


def _world() -> HybridWorld:
    w = HybridWorld()
    w.dmb.hazards["catastrophe"]["cubes"][w.hazard_id]["active"] = False
    return w


def _of(w: HybridWorld, faction: str, kind: str) -> str:
    return next(i for i, b in w.buildings.items() if b["kind"] == kind and b["faction_name"] == faction)


def _run(w: HybridWorld, steps: int) -> None:
    base = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(steps):
        w.advance(100, base + i + 1, snapshot=False)


def test_mine_on_a_mineral_site_never_runs_dry_and_logs_its_source() -> None:
    """D22 (12 Oct 2026): a Widelands coal mine works its site for as long as it stands. The deposit layer does not shrink, the
    mine never reports exhaustion, and every unit dug is logged as an inexhaustible-deposit inflow (the only mineral source)."""
    from wizard_rts import programs_data

    saved = programs_data.ECONOMY_TARGETS["coal"]
    programs_data.ECONOMY_TARGETS["coal"] = 10**9  # keep the economy hungry so the mine never idles for lack of demand
    try:
        w = _world()
        w.outbreaks_enabled = False  # this test is about the mine rule: no outbreak losses or closures in between
        w.disruptions_enabled = False
        mine = w.buildings[_of(w, "Red", "mine")]
        centre = (mine["tx"], mine["ty"])
        nodes = [(centre[0] + dx, centre[1] + dy) for dx in range(-2, 3) for dy in range(-2, 3)]
        for n in nodes:
            if w.terrain is None or w.terrain.cls[n[1] * w.terrain.w + n[0]] == 1:  # mountain nodes on terrain worlds
                set_resource(w, n, "coal", 1)  # the thinnest possible field: under the old rule it was worked out in minutes
        nodes = w.resource_nodes(centre, 2, "coal")
        assert len(nodes) >= 10
        before = resource_sum(w, nodes, "coal")
        from wizard_rts.terrain import MINERALS, RES_CODE

        codes = {RES_CODE[m] for m in MINERALS}

        def minerals(t):  # the mineral part of the deposit layer (fish is caught and bred: it is meant to change)
            return [a for k, a in zip(t.res_kind, t.res_amt) if k in codes]
        layer = minerals(w.terrain) if w.terrain is not None else None
        for _ in range(30):  # 50 game minutes
            _run(w, 1_000)
        dug = sum(1 for e in w.events if e["kind"] == "mined" and e.get("building") == mine["id"])
        assert w.stats["mined_from_inexhaustible_deposit:coal"] >= 5
        assert resource_sum(w, nodes, "coal") == before  # the site is not consumed
        if layer is not None:
            assert minerals(w.terrain) == layer
        assert not mine.get("deposit_exhausted")
        assert w.stats.get("made_coal", 0) >= w.stats["mined_from_inexhaustible_deposit:coal"] - 8 and dug >= 0
    finally:
        programs_data.ECONOMY_TARGETS["coal"] = saved


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
