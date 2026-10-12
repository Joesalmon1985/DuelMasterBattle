"""A barracks waits for its tribe's soldier wares; after a long wait it falls back to the hybrid ax recipe (still goods-fed)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ["HYBRID_AI"] = "0"

from wizard_rts import construction as con  # noqa: E402
from wizard_rts.economy import produce  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def _barracks(w, faction):
    return next(b for b in w.buildings.values() if b["faction_name"] == faction and b["kind"] == "barracks")


def test_tribe_recipe_first_then_ax_after_the_patience_runs_out() -> None:
    w = HybridWorld(507)
    w.ai_enabled = False
    bar = _barracks(w, "Blue")
    assert con.recipe_for(w, bar, "infantry")["cost"] == {"armor_helmet": 1, "spear_wooden": 1}  # the Empire soldier's wares
    w.queue(bar["id"], "infantry")
    n = len(w.units)
    def run(seconds: int, stop=lambda: False) -> None:
        for _ in range(seconds):
            w.advance(1000, int(w.dmb.clock.get("clock_sequence", 0)) + 1, snapshot=False)
            if stop():
                break

    run(30)  # nothing arrives: the tribe wares are not in the warehouse
    assert len(w.units) == n and not bar.get("tribe_fallback")
    bar["wait_ms"] = con.TRIBE_PATIENCE_MS - 500  # a long wait, without simulating twenty-five minutes
    run(3)
    assert bar.get("tribe_fallback") is True
    assert any(e["kind"] == "tribe_fallback" and e["faction"] == "Blue" for e in w.events)
    assert con.recipe_for(w, bar, "infantry")["cost"] == {"ax": 1}
    # still goods-fed: with no ax anywhere nothing is recruited, with one delivered a rifleman appears
    wh = con.faction_warehouse(w, "Blue")
    produce(w, wh["id"], "ax", 2)
    run(1500, lambda: len(w.units) > n)
    assert len(w.units) > n
    assert w.stats["consumed_ax"] >= 1
