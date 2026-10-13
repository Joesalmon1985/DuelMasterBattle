"""Decision C: dead-end tribe wares feed the OpenRA army through ware classes."""
import pytest

from wizard_rts import construction as con
from wizard_rts import tribes, ware_classes as WC, wl_defs
from wizard_rts.economy import produce
from wizard_rts.world import HybridWorld


@pytest.mark.parametrize("tribe", sorted(WC.CLASS_WARES))
def test_every_class_ware_exists_and_is_made_by_the_tribe(tribe):
    made = set()
    for spec in tribes.tribe_buildings(tribe).values():
        made |= set(spec.get("outputs", []))
    for cls, ws in WC.CLASS_WARES[tribe].items():
        assert ws and set(ws) <= made, (tribe, cls, [w for w in ws if w not in made])


def _world():
    w = HybridWorld(507, profile="test_showcase")
    w.ai_enabled = False
    return w


def _barracks(w, faction="Red"):
    from test_openra_content import building, unlock

    unlock(w, faction)
    return building(w, "barracks", faction)


def test_a_grenadier_is_paid_with_an_armour_ware_and_any_of_the_class_will_do():
    w = _world()
    b = _barracks(w)
    r = con.recipe_for(w, b, "grenadier")
    assert r["cost"].get("helmet") == 1 and r["class_alts"] == {"helmet": ["helmet_mask", "helmet_warhelm"]}
    # the alternate of the class stands in when the primary is missing
    assert WC.resolve(r, {"helmet_mask": 1})["helmet_mask"] == 1 and "helmet" not in WC.resolve(r, {"helmet_mask": 1})
    # a rifleman has no class ware
    assert "class_alts" not in con.recipe_for(w, b, "infantry")


def test_the_army_unit_consumes_the_class_ware_and_the_waiting_ends_in_a_fallback():
    w = _world()
    b = _barracks(w)
    stock = {g: 5 for g in ("iron", "coal", "ration")}
    stock["helmet_mask"] = 1
    for g, n in stock.items():
        produce(w, b["id"], g, n)
    assert con.queue_unit(w, b["id"], "grenadier")["status"] == "ok"
    base = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(40):
        w.advance(1000, base + i + 1, snapshot=False)
    assert w.stats.get("consumed_helmet_mask", 0) == 1
    # no class ware at all: after the patience the building drops the requirement
    w2 = _world()
    b2 = _barracks(w2)
    for g in ("iron", "coal", "ration"):
        produce(w2, b2["id"], g, 5)
    con.queue_unit(w2, b2["id"], "grenadier")
    b2["wait_ms"] = WC.CLASS_PATIENCE_MS
    base = int(w2.dmb.clock.get("clock_sequence", 0))
    for i in range(5):
        w2.advance(1000, base + i + 1, snapshot=False)
    assert b2.get("class_fallback") and any(e["kind"] == "class_fallback" for e in w2.events)
