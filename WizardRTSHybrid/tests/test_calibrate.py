"""Plan v2 6.1: recipes derived from OpenRA credits sit on one scale, are physical wares, and are card-only."""
from wizard_rts import calibrate, construction as con, rules, tech
from wizard_rts.world import HybridWorld


def test_cost_grows_with_credits_inside_each_template():
    for template in calibrate.TEMPLATES:
        values = [calibrate.recipe(c, template)["value"] for c in (200, 500, 1000, 2000, 2400)]
        assert values == sorted(values) and values[-1] > 2 * values[0]  # whole-ware rounding keeps the cheap end above its exact value


def test_value_tracks_credits_within_rounding_and_wares_exist():
    for _b, unit, actor, _l, template in calibrate.NEW_UNITS:
        credits = int(rules.actor(f"openra.{actor}")["cost"])
        r = calibrate.recipe(credits, template)
        assert 0.6 <= r["value"] / (credits / calibrate.CREDITS_PER_VALUE) <= 1.6, (unit, r)
        assert set(r["cost"]) <= set(calibrate.WARE_VALUE) and all(n >= 1 for n in r["cost"].values())


def test_new_units_are_in_the_recipes_and_card_only():
    for building, unit, actor, *_ in calibrate.NEW_UNITS:
        assert con.RECIPES[building][unit]["definition"] == f"openra.{actor}"
    w = HybridWorld(507, profile="test_showcase")
    assert not tech.unit_allowed(w, "Red", "cruiser") and tech.unit_allowed(w, "Red", "tank")  # the ungated roster is unchanged
    d = HybridWorld(507, profile="developer")
    assert not tech.unit_allowed(d, "Red", "cruiser")
    from wizard_rts.content import graph

    card = next(cid for cid, c in graph.generated_cards().items() if "unit:cruiser" in c["entities"])
    assert tech.grant(d, "Red", card)["status"] == "ok"
    assert tech.unit_allowed(d, "Red", "cruiser")
