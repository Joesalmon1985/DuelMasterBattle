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
