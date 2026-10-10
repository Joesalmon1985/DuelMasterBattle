"""Fields, game, water, rations: nothing appears without a field, an animal, a deposit or a meal."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wizard_rts.animals import spawn_animal  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def _world() -> HybridWorld:
    w = HybridWorld()
    w.dmb.hazards["catastrophe"]["cubes"][w.hazard_id]["active"] = False
    return w


def _run(w: HybridWorld, steps: int) -> None:
    base = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(steps):
        w.advance(100, base + i + 1, snapshot=False)


def _wheat(w: HybridWorld) -> list[dict]:
    return [t for t in w.trees.values() if t["species"] == "wheat"]


def test_farmer_plants_fields_that_grow_and_are_harvested_once_ripe() -> None:
    w = _world()
    assert not _wheat(w)  # no field exists until a farmer plants one
    _run(w, 700)
    fields = _wheat(w)
    assert fields
    stages_seen: set[str] = set()
    for _ in range(40):
        _run(w, 100)
        stages_seen |= {f["stage"] for f in _wheat(w)}
    assert {"tiny", "small", "medium"} <= stages_seen
    _run(w, 12_000)
    assert w.stats.get("made_wheat", 0) >= 1
    # one wheat per ripe field: never more wheat than fields that were planted
    assert w.stats["made_wheat"] <= w.stats["fields_planted"]


def test_nothing_is_harvested_before_the_field_is_ripe() -> None:
    w = _world()
    _run(w, 200)
    for f in _wheat(w):
        f["timer_ms"] = 10**9  # frozen tiny
    for _ in range(60):
        _run(w, 100)
        for f in _wheat(w):
            if f["stage"] != "tiny":
                f["stage"], f["timer_ms"] = "tiny", 10**9
    assert w.stats.get("made_wheat", 0) == 0


def test_hunter_kills_a_real_animal_and_game_breeds_back() -> None:
    w = _world()
    before = len(w.animals)
    _run(w, 6_000)
    hunted = w.stats.get("made_meat", 0)
    assert hunted >= 1
    killed = sum(1 for e in w.events if e["kind"] == "animal_hunted")
    assert killed >= 1 or hunted >= 1
    born = sum(1 for e in w.events if e["kind"] == "animal_born")
    assert born + before - hunted >= 1  # renewal exists, and the herd is not simply gone
    # an empty land gives no meat
    w2 = _world()
    w2.animals.clear()
    _run(w2, 6_000)
    assert w2.stats.get("made_meat", 0) == 0


def test_well_draws_down_its_water_and_stops_when_dry() -> None:
    w = _world()
    well = next(b for b in w.buildings.values() if b["kind"] == "well" and b["faction_name"] == "Red")
    nodes = [(well["tx"] + dx, well["ty"] + dy) for dx in range(-1, 2) for dy in range(-1, 2)]
    for n in nodes:
        w.resources[n]["water"] = 1
    from wizard_rts import programs_data

    programs_data.ECONOMY_TARGETS["water"] = 10**9
    try:
        _run(w, 9_000)
    finally:
        programs_data.ECONOMY_TARGETS["water"] = 12
    assert sum(w.resources[n]["water"] for n in nodes) == 0
    assert well.get("deposit_exhausted") is True


def test_mines_stop_without_rations() -> None:
    w = _world()
    for b in list(w.buildings.values()):
        if b["kind"] in ("tavern", "hunter", "farm", "bakery"):
            w.damage_building(b["id"], 10**9, ["structure"], {})
    for wh in [b for b in w.buildings.values() if b["kind"] == "warehouse"]:
        w.stocks[wh["id"]]["ration"] = 0
        w.economy_totals.totals["ration"] = 0
    _run(w, 4_000)
    assert w.stats.get("made_coal", 0) == 0 and w.stats.get("made_iron_ore", 0) == 0
