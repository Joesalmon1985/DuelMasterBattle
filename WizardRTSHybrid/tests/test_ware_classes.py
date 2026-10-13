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


def test_a_grenadier_may_be_paid_with_an_armour_ware_in_place_of_iron():
    w = _world()
    b = _barracks(w)
    r = con.recipe_for(w, b, "grenadier")
    assert r["cost"] == {"iron": 1, "coal": 1, "ration": 1}  # the raw recipe is untouched: nothing is blocked
    assert r["class_subst"] == {"iron": ["helmet", "helmet_mask", "helmet_warhelm"]}
    assert WC.resolve(r, {"iron": 0, "coal": 1, "ration": 1, "helmet_mask": 1}) == {"helmet_mask": 1, "coal": 1, "ration": 1}
    assert WC.resolve(r, {"iron": 1, "helmet_mask": 1}) == {"iron": 1, "coal": 1, "ration": 1}  # raw iron in stock is used first
    assert WC.request_cost(r, {"helmet": 2}) == {"helmet": 1, "coal": 1, "ration": 1}  # the warehouse holds one: ask for that instead of iron
    assert WC.request_cost(r, {}) == r["cost"]
    assert "class_subst" not in con.recipe_for(w, b, "infantry")


def test_the_unit_uses_up_the_dead_end_ware_when_it_has_no_iron():
    w = _world()
    b = _barracks(w)
    for g, n in {"coal": 2, "ration": 2, "helmet_mask": 1}.items():
        produce(w, b["id"], g, n)
    assert con.queue_unit(w, b["id"], "grenadier")["status"] == "ok"
    base = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(45):
        w.advance(1000, base + i + 1, snapshot=False)
    assert w.stats.get("consumed_helmet_mask", 0) == 1 and w.stats.get("recruited", 0) >= 1
