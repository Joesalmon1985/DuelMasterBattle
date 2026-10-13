"""Plan v2 7.3: relations change who fights whom; treaties expire and can be broken; nests stay hostile to everyone."""
from wizard_rts import construction as con
from wizard_rts import diplomacy, military
from wizard_rts.world import HybridWorld


def world():
    w = HybridWorld(507, profile="test_showcase")
    w.ai_enabled = False
    w._seq = 0
    return w


def run(w, s):
    for _ in range(int(s)):
        w._seq += 1
        w.advance(1000, w._seq, snapshot=False)


def two_adjacent(w):
    red, blue = w.faction_info["Red"], w.faction_info["Blue"]
    u1 = w._unit(red["id"], "Red", "tank", "Tank", "openra.3tnk", (60, 60))
    u2 = w._unit(blue["id"], "Blue", "tank", "Tank", "openra.3tnk", (62, 60))
    for u in (u1, u2):
        w.units[u]["weapon"] = "120mm"
        w.units[u]["hp"] = 40000
    return u1, u2


def test_default_is_war_and_truce_stops_targeting():
    w = world()
    military._build_grid(w)
    r, b = w.faction_info["Red"]["id"], w.faction_info["Blue"]["id"]
    u1, u2 = two_adjacent(w)
    military._build_grid(w)
    assert military._scan(w, r, (60, 60), 6.0) == {"kind": "unit", "id": u2}
    diplomacy.set_state(w, "Red", "Blue", "truce", 60_000)
    military._build_grid(w)
    assert military._scan(w, r, (60, 60), 6.0) is None
    assert military._scan(w, b, (62, 60), 6.0) is None
    wh = next(x for x in w.buildings.values() if x["faction_name"] == "Blue" and x["kind"] == "warehouse")
    assert military.order_attack(w, u1, wh["id"])["reason"] == "not_at_war"


def test_treaty_expires_and_can_be_broken():
    w = world()
    diplomacy.set_state(w, "Red", "Blue", "truce", 20_000)
    assert diplomacy.state_of(w, "Red", "Blue") == "truce" and not diplomacy.hostile(w, "Blue", "Red")
    run(w, 25)
    assert diplomacy.state_of(w, "Red", "Blue") == "war"
    assert [e for e in w.events if e["kind"] == "relation_changed" and e["why"] == "expired"]
    diplomacy.set_state(w, "Red", "Green", "alliance")
    assert diplomacy.break_treaty(w, "Red", "Green")["status"] == "ok" and diplomacy.hostile(w, "Red", "Green")
    assert w.fstats["Red"]["treaties_broken"] == 1


def test_offers_are_accepted_refused_and_lapse():
    w = world()
    oid = diplomacy.propose(w, "Red", "Blue", "peace", 30_000)["offer"]
    assert diplomacy.respond(w, oid, False)["accepted"] is False and diplomacy.state_of(w, "Red", "Blue") == "war"
    oid = diplomacy.propose(w, "Red", "Blue", "peace", 30_000)["offer"]
    assert diplomacy.respond(w, oid, True)["accepted"] and diplomacy.state_of(w, "Red", "Blue") == "peace"
    oid2 = diplomacy.propose(w, "Red", "Green")["offer"]
    run(w, 130)
    assert oid2 not in w.offers


def test_nests_are_hostile_to_a_faction_in_a_truce():
    w = world()
    diplomacy.set_state(w, "Red", "Blue", "alliance")
    assert diplomacy.hostile(w, "Red", "") and diplomacy.hostile_ids(w, w.faction_info["Red"]["id"], "")


def test_cooperative_ai_rule_signs_truces_under_catastrophe_pressure():
    from wizard_rts import regions

    w = world()
    w.diplomacy_enabled = True
    rg = regions.state(w)
    run(w, 2)
    assert diplomacy.pressure(w) == 0.0
    rg.outbreaks = 4
    rg.era_outbreaks[0] = 4
    run(w, 12)
    assert diplomacy.state_of(w, "Red", "Blue") == "truce"
    w.diplomacy_policy = {"Red": "selfish", "Blue": "coop", "Green": "coop"}
    for k in list(w.relations):
        w.relations.pop(k)
    run(w, 12)
    assert diplomacy.state_of(w, "Red", "Blue") == "war" and diplomacy.state_of(w, "Blue", "Green") == "truce"


def test_nest_policies_ignore_selfish_and_coop():
    from wizard_rts import ai_plus, territory

    w = world()
    blue_cc = territory.command_centers(w, "Blue")[0]
    nest = {"kind": "blight_nest", "tx": blue_cc["tx"] + 3, "ty": blue_cc["ty"], "nest_cubes": 3, "faction": "", "faction_name": "", "hp": 1000}
    centre = (nest["tx"] - 2.0, nest["ty"])
    value = lambda name: ai_plus._target_value(w, name, nest, centre, 1e12)  # noqa: E731
    assert value("Red") == -1.0  # selfish (default): the nest is beside Blue's centre, not Red's
    w.nest_policy = {"Red": "coop", "Blue": "ignore"}
    assert value("Red") > 0  # cooperative: a nest beside anyone's settlement is everybody's problem
    assert value("Blue") == -1.0  # ignore: never
    w.outbreaks_enabled = False
    from wizard_rts import regions

    base = value("Red")
    regions.state(w).outbreaks = 6
    assert value("Red") > base  # the more of the loss limit is used, the more it is worth


def test_clinic_cures_its_region_for_rations_and_water_and_idles_when_clean():
    from wizard_rts import construction as con, regions
    from wizard_rts.economy import produce

    w = HybridWorld(507, profile="test_showcase")
    w.ai_enabled = False
    w.outbreaks_enabled = False
    w._seq = 0
    home = next(b for b in w.buildings.values() if b["faction_name"] == "Red" and b["kind"] == "warehouse")
    placed = None
    for dx in range(6, 30):
        for dy in range(6, 30):
            r = w.build("Red", "clinic", home["tx"] + dx, home["ty"] + dy)
            if r["status"] == "ok":
                placed = r["id"]
                break
        if placed:
            break
    assert placed
    b = w.buildings[placed]
    b.pop("constructing", None)
    b["operational"], b["hp"] = True, b["max_hp"]
    produce(w, placed, "ration", 2)
    produce(w, placed, "water", 2)
    rg = regions.state(w)
    i = rg.region_at(b["tx"], b["ty"])
    run(w, 100)
    assert w.stocks[placed].get("ration", 0) == 2  # a clean region: nothing consumed, nothing cured
    rg.cubes[i] = 3
    run(w, 200)
    assert rg.cubes[i] <= 2 and w.stats.get("cubes_cured", 0) >= 1 and w.fstats["Red"]["cubes_cured"] >= 1
    assert w.stats["consumed_ration"] >= 1 and w.stats["consumed_water"] >= 1
    assert [e for e in w.events if e["kind"] == "cube_cured"]
