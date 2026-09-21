"""Village foundation checks against the full Prehistoric board start settlement."""

from __future__ import annotations

from sim.dmb.industry.projection import IndustryProjection
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.world.overworld_export import export_overworld_area, _opening_lines
from sim.dmb.world.settlement_layout import public_occupation_for


def test_baseline_has_no_active_quest() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    assert not sim.state.board.get("g05", {}).get("quest_enabled")
    assert not sim.state.board.get("fx_village", {}).get("quest_enabled")
    assert not sim.state.board.get("fx_village", {}).get("quest_id")
    area = export_overworld_area(sim.state)
    assert area.get("quest_id") in {"", None}
    ids = {str(e.get("id")) for e in area["entities"]}
    assert "cube:demon" not in ids
    assert "entrance:sluice" not in ids


def test_start_settlement_primaries_on_perimeter() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    home = str(sim.state.board["g05"]["start_node_id"])
    layout = (sim.state.board.get("local_projections") or {}).get(home)
    if not layout:
        from sim.dmb.world.projection import LocalProjectionService

        LocalProjectionService(sim.state).ensure_layout(home)
        layout = sim.state.board["local_projections"][home]
    w = int(layout["width"])
    for bid, anchor in (layout.get("buildings") or {}).items():
        building = sim.state.buildings[bid]
        if str(building.get("slot_kind")) != "primary":
            continue
        gx, gy = int(anchor["grid"][0]), int(anchor["grid"][1])
        assert gx <= 10 or gy <= 10 or gx >= w - 14 or gy >= w - 14


def test_occupations_stable_not_carrier() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    for _ in range(3):
        sim.advance(200, int(sim.state.clock.get("clock_sequence", 0)) + 1)
    workers = IndustryProjection(sim.state).workers()
    for row in workers:
        occ = str(row.get("public_occupation") or row.get("occupation") or "")
        assert occ
        assert occ.lower() != "carrier"


def test_baseline_dialogue_has_no_quest_promises() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    for pid in list(sim.state.people)[:20]:
        lines = _opening_lines(sim.state, pid)
        blob = " ".join(lines).lower()
        assert "quest.factory_shortage" not in blob
        assert "show you where" not in blob
        assert "follow me" not in blob
