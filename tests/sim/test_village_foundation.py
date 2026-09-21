"""Village Foundation: healthy baseline settlement spatial + dialogue integrity."""

from __future__ import annotations

from sim.dmb.industry.projection import IndustryProjection
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.world.overworld_export import export_overworld_area, _opening_lines
from sim.dmb.world.settlement_layout import hex_sector, public_occupation_for


def test_baseline_has_no_active_quest_landmarks() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    fx = sim.state.board["fx_village"]
    assert fx.get("mode") == "baseline"
    assert not fx.get("quest_enabled")
    assert not fx.get("quest_id")
    assert not fx.get("cause_id")
    cubes = ((sim.state.hazards or {}).get("catastrophe") or {}).get("cubes") or {}
    demon = cubes.get("cube:demon") or {}
    assert not demon.get("active")
    assert "entrance:sluice" not in (sim.state.board.get("entrances") or {})
    area = export_overworld_area(sim.state)
    kinds = {str(e.get("id")): e for e in area["entities"]}
    assert "cube:demon" not in kinds
    assert "entrance:sluice" not in kinds
    assert area.get("quest_id") in {"", None}


def test_quest_fixture_still_binds_shortage() -> None:
    sim = load_fixture("FX-VILLAGE-QUEST", seed=507)
    fx = sim.state.board["fx_village"]
    assert fx.get("mode") == "quest"
    assert fx.get("quest_enabled")
    assert fx.get("quest_id")
    assert fx.get("cause_id")
    cubes = ((sim.state.hazards or {}).get("catastrophe") or {}).get("cubes") or {}
    assert cubes.get("cube:demon", {}).get("active") is True


def test_primaries_on_perimeter_core_in_centre() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    fx = sim.state.board["fx_village"]
    node_id = fx["node_id"]
    layout = (sim.state.board.get("local_projections") or {})[node_id]
    w, h = int(layout["width"]), int(layout["height"])
    cx, cy = w // 2, h // 2
    for bid, anchor in (layout.get("buildings") or {}).items():
        building = sim.state.buildings[bid]
        slot = str(building.get("slot_kind") or "")
        gx, gy = int(anchor["grid"][0]), int(anchor["grid"][1])
        if slot == "primary":
            assert anchor.get("presentation") == "primary_site"
            assert anchor.get("sector") != "core"
            # Perimeter: near an edge.
            assert gx <= 8 or gy <= 8 or gx >= w - 12 or gy >= h - 12
        elif slot in {"centre", "warehouse", "processor", "factory"}:
            # Built core: not on the far edge band.
            assert abs(gx - cx) < w // 2 - 2
            assert abs(gy - cy) < h // 2 - 2


def test_primary_sectors_match_touching_hex_orientation() -> None:
    from sim.dmb.world.generation import BoardBuilder

    sim = load_fixture("FX-VILLAGE", seed=507)
    fx = sim.state.board["fx_village"]
    node_id = fx["node_id"]
    plan = BoardBuilder.generate(507, 2)
    layout = (sim.state.board.get("local_projections") or {})[node_id]
    for bid, anchor in (layout.get("buildings") or {}).items():
        building = sim.state.buildings[bid]
        if str(building.get("slot_kind")) != "primary":
            continue
        hid = str(building.get("hex_id") or "")
        expected = hex_sector(plan.board, node_id, hid)
        # Sector may nudge if collision — still must be a perimeter sector.
        assert anchor.get("sector") in {
            "north",
            "northeast",
            "east",
            "southeast",
            "south",
            "southwest",
            "west",
            "northwest",
        }
        # Prefer exact match when unique.
        used = [
            a.get("sector")
            for a in layout["buildings"].values()
            if a.get("presentation") == "primary_site"
        ]
        if used.count(expected) == 1:
            assert anchor.get("sector") == expected


def test_occupations_stable_not_carrier() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    for _ in range(3):
        sim.advance(200, int(sim.state.clock.get("clock_sequence", 0)) + 1)
    workers = IndustryProjection(sim.state).workers()
    assert workers
    for row in workers:
        occ = str(row.get("public_occupation") or row.get("occupation") or "")
        assert occ
        assert occ.lower() != "carrier"
        assert "attendant" not in occ.lower()
        person = sim.state.people[row["person_id"]]
        workplace = sim.state.buildings.get(str(person.get("workplace_id") or "")) or {}
        derived = public_occupation_for(person, workplace=workplace)
        assert derived == occ or derived == row.get("public_role")


def test_baseline_dialogue_has_no_quest_or_guide_promise() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    for pid in sim.state.people:
        lines = _opening_lines(sim.state, pid)
        blob = " ".join(lines).lower()
        assert "quest.factory_shortage" not in blob
        assert "cause.factory_shortage" not in blob
        assert "show you where" not in blob
        assert "follow me" not in blob
        assert "blockage" not in blob


def test_overworld_export_primaries_are_not_house_walls() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    area = export_overworld_area(sim.state)
    fx = sim.state.board["fx_village"]
    layout = (sim.state.board.get("local_projections") or {})[fx["node_id"]]
    rows = area["rows"]
    for bid, anchor in (layout.get("buildings") or {}).items():
        if str(sim.state.buildings[bid].get("slot_kind")) != "primary":
            continue
        gx, gy = int(anchor["grid"][0]), int(anchor["grid"][1])
        fw, fh = int(anchor["footprint"][0]), int(anchor["footprint"][1])
        wall_cells = 0
        site_cells = 0
        for dy in range(fh):
            for dx in range(fw):
                ch = rows[gy + dy][gx + dx]
                if ch == "#":
                    wall_cells += 1
                if ch in {"T", "r", "L", ",", "."}:
                    site_cells += 1
        assert wall_cells == 0
        assert site_cells > 0


def test_industry_still_runs_on_baseline() -> None:
    from sim.dmb.industry import fraction

    sim = load_fixture("FX-VILLAGE", seed=507)
    work_id = sim.state.board["fx_village"]["factory_work_id"]
    for _ in range(5):
        sim.advance(200, int(sim.state.clock.get("clock_sequence", 0)) + 1)
    rates = {}
    for event in reversed(sim.state.industry.get("events") or []):
        if event.get("kind") == "industry_rates":
            rates = event.get("rates") or {}
            break
    assert float(fraction(rates.get(work_id) or 0)) > 0
