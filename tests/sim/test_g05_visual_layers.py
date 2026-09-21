"""Visual integration: presenters mirror authoritative G01–G04 state."""

from __future__ import annotations

from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.world.overworld_export import export_overworld_area
from sim.dmb.world.world_map import export_world_map


def test_world_layers_export_matches_authority() -> None:
    sim = load_fixture("FX-WORLD-LAYERS", seed=507)
    area = export_overworld_area(sim.state, "node:35")
    entities = {str(e["id"]): e for e in area["entities"]}

    # Cart with real cargo lots
    cart = next(e for e in area["entities"] if e.get("kind") == "cart")
    cart_rec = sim.state.carts[cart["id"]]
    expected = [
        str(lot.get("good_id"))
        for lot in (cart_rec.get("cargo_lots") or [])
        if lot.get("good_id")
    ]
    assert cart.get("faction_id") == cart_rec.get("owner_faction")
    assert list(cart.get("cargo") or []) == expected

    # Soldiers retain unit_id + person_id and archetype shape key
    soldiers = [e for e in area["entities"] if e.get("kind") == "soldier"]
    assert len(soldiers) >= 3
    for s in soldiers:
        uid = str(s["unit_id"])
        assert uid in sim.state.units
        assert s.get("person_id") == sim.state.units[uid].get("person_id")
        assert s.get("archetype") in {"skirmisher", "line", "heavy"}
        assert s.get("faction_id") == sim.state.units[uid].get("faction_id")

    # Hazard cube:2 touches node:35
    hazards = [e for e in area["entities"] if e.get("kind") == "hazard"]
    assert any(e.get("cube_id") == "cube:2" for e in hazards)
    cube = ((sim.state.hazards.get("catastrophe") or {}).get("cubes") or {})["cube:2"]
    hz = next(e for e in hazards if e.get("cube_id") == "cube:2")
    assert hz.get("hex_id") == cube.get("hex_id")

    # Construction order projected
    constructions = [e for e in area["entities"] if e.get("kind") == "construction"]
    assert constructions
    oid = constructions[0]["order_id"]
    assert oid in sim.state.orders

    # Factory meters match Python
    meters = [r for r in area.get("industry_overlay") or [] if r.get("kind") == "factory_meter"]
    assert meters
    for row in meters:
        fid = row["building_id"]
        factory = sim.state.industry["factories"][fid]
        meter = factory.get("meter") or {}
        if isinstance(meter, dict):
            num = float(meter.get("numerator", 0))
            den = float(meter.get("denominator", 1) or 1)
            expected_prog = num / den
        else:
            expected_prog = float(meter)
        assert abs(float(row["meter_progress"]) - expected_prog) < 1e-6

    # Roads on map match built edges
    wmap = export_world_map(sim.state, reveal_all=True)
    built = {
        tuple(sorted([str(r["a"]), str(r["b"])]))
        for r in (sim.state.roads or {}).values()
        if r.get("status") == "built"
    }
    mapped = {tuple(sorted([str(r["a"]), str(r["b"])])) for r in wmap["roads"]}
    assert built == mapped
    assert any(h["cube_id"] == "cube:2" for h in wmap["hazards"])
    assert wmap["john"]["node_id"] == "node:35"


def test_baseline_still_has_hazard_without_quest() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    assert not sim.state.board.get("g05", {}).get("quest_enabled")
    area = export_overworld_area(sim.state, "node:35")
    assert any(e.get("kind") == "hazard" for e in area["entities"])
    assert not any(e.get("id") == "cube:demon" for e in area["entities"])


def test_full_board_unchanged() -> None:
    from sim.dmb.world.prehistoric_world import board_summary

    sim = load_fixture("FX-WORLD-LAYERS", seed=507)
    s = board_summary(sim)
    assert s["hexes"] == 19 and s["nodes"] == 54 and s["edges"] == 72
