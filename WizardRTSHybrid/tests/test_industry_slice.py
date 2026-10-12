"""M2 end-to-end slice: existing deposits -> drills -> belts (>= 8 tiles) -> powered smelter -> paid unit factory -> Mindustry unit ->
fight with an OpenRA unit, all in one HybridWorld, with the ware and reserve books balanced. Takes about 90 s of wall time."""
import pytest

from wizard_rts import construction as con
from wizard_rts import ledger
from wizard_rts.industry import fixture as F
from wizard_rts.industry import registry as R
from wizard_rts.industry import sim as S
from wizard_rts.world import HybridWorld

SEED = 507


@pytest.fixture(scope="module")
def slice_run():
    w = HybridWorld(SEED, profile="developer")
    w.ai_enabled = False
    w.outbreaks_enabled = False  # the slice is about the machines; catastrophes (nests, closures) are tested on their own
    w.disruptions_enabled = False
    init = ledger.snapshot_totals(w)
    layer = bytes(w.terrain.res_kind)
    totals0 = {k: sum(w.terrain.res_amt[i] for i in range(len(w.terrain.res_amt)) if w.terrain.res_kind[i] == c) for k, c in (("coal", 1), ("iron", 2))}
    ids = F.modern_fixture(w, "Red")
    seq = 0
    unit = None
    log = {"first_belt_live": None, "first_silicon": None}
    for sec in range(90 * 60):
        seq += 1
        w.advance(1000, seq, snapshot=False)
        if log["first_belt_live"] is None and any(b.get("line_live") and len(b["line"]["tiles"]) >= 8 for b in w.buildings.values() if b["kind"] == "mdy:conveyor"):
            log["first_belt_live"] = sec
        if log["first_silicon"] is None and w.stats.get("made_mdy.silicon"):
            log["first_silicon"] = sec
        unit = next((u for u in w.units.values() if u["kind"] == "mdy_dagger"), None)
        if unit:
            log["unit_at"] = sec
            break
    return w, ids, init, layer, totals0, unit, log, seq


def test_slice_produces_a_dagger_from_delivered_inputs(slice_run):
    w, ids, init, layer, totals0, unit, log, seq = slice_run
    assert unit is not None, "no dagger within 90 game minutes"
    assert log["first_belt_live"] is not None and log["first_belt_live"] < log["unit_at"]
    assert log["first_silicon"] < log["unit_at"]  # the unit only appears after the smelter delivered silicon
    f = w.buildings[ids["factory"]]
    assert f["faction_name"] == "Red" and unit["faction_name"] == "Red"
    assert w.stats["consumed_mdy.silicon"] >= 10 and w.stats["consumed_mdy.lead"] >= 10  # the plan's inputs were spent, not conjured
    belts = [b for b in w.buildings.values() if b["kind"] == "mdy:conveyor"]
    assert max(len(b["line"]["tiles"]) for b in belts) >= 8  # a visible run of at least eight tiles
    assert all(b["line_live"] for b in belts)


def test_slice_builds_everything_from_real_goods_on_existing_sites(slice_run):
    w, ids, init, layer, totals0, unit, log, seq = slice_run
    assert bytes(w.terrain.res_kind) == layer  # no ore squares were created
    assert w.stats["consumed_plank"] > 40 and w.stats["consumed_granite"] > 20 and w.stats["consumed_iron"] > 10  # machines paid in Widelands goods
    for key in ("coal_drill", "sand_drill", "lead_drill"):
        d = w.buildings[ids[key]]
        assert d["operational"] and d["mdy"]["role"] == "drill"
        assert any(w.resource_amount((x, y), r) is not None for x, y in S.footprint(d) for r in ("coal", "iron"))
    for ware in ("mdy.lead", "mdy.sand", "coal"):  # a drill whose reserve is spent reports no item, so the books are the evidence
        assert w.stats.get("drilled_" + ware, 0) > 0, ware
    assert w.buildings[ids["sand_drill"]]["mdy"]["item"] == "sand"  # floor drops never run out


def test_slice_books_balance_and_mineral_deposits_never_run_dry(slice_run):
    w, ids, init, layer, totals0, unit, log, seq = slice_run
    assert ledger.check(w, init) == []
    now = {k: sum(w.terrain.res_amt[i] for i in range(len(w.terrain.res_amt)) if w.terrain.res_kind[i] == c) for k, c in (("coal", 1), ("iron", 2))}
    assert now == totals0  # D22: drills on coal and iron deposits extract without lowering the reserve
    assert w.stats["extracted_units_coal"] >= 10 and w.stats["extracted_units_iron"] >= 10
    assert w.stats["made_mdy.lead"] == w.stats["extracted_units_iron"]  # one lead item per reserve unit (mindustry_overrides.json)


def test_slice_unit_fights_an_openra_unit_in_the_shared_combat_model(slice_run):
    w, ids, init, layer, totals0, unit, log, seq = slice_run
    ux, uy = unit["tx"], unit["ty"]
    foe = None
    for dx, dy in ((4, 0), (-4, 0), (0, 4), (0, -4), (3, 3), (-3, 3), (3, -3), (-3, -3), (5, 1), (-5, 1)):
        t = (ux + dx, uy + dy)
        if w.tile_speed("foot", *t) > 0 and t not in w.blocked:
            foe = w._unit(w.faction_info["Blue"]["id"], "Blue", "infantry", "Rifleman", "openra.e1", t)
            break
    assert foe is not None
    w.order(unit["id"], foe)
    w.order(foe, unit["id"])
    for _ in range(90):
        seq += 1
        w.advance(1000, seq, snapshot=False)
        if not w.units[foe].get("alive", True):
            break
    assert not w.units[foe].get("alive", True) and w.units[unit["id"]].get("alive", True)
    assert w.units[unit["id"]]["hp"] < w.units[unit["id"]]["max_hp"]
