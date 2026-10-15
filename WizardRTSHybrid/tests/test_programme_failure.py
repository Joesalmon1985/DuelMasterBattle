"""A failed sub-programme must not starve the programmes after it (V4 P2: smelting works made no gold with gold ore and coal in stock)."""
from test_widelands_completion import done, run, world


def test_a_smelting_works_without_iron_ore_still_smelts_gold():
    w = world()
    b = done(w, "wl:barbarians_smelting_works", stock={"gold_ore": 3, "coal": 3})
    run(w, 400)
    assert w.stats.get("consumed_gold_ore", 0) >= 1, (b.get("stall"), b.get("stack"))
    assert w.stats.get("consumed_coal", 0) >= 1
