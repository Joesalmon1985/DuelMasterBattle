"""Faction commands cannot touch another faction's buildings or units (V4 P4); God Mode (no faction) still can."""
from wizard_rts import construction as con
from wizard_rts.world import HybridWorld


def _w():
    w = HybridWorld(507, profile="test_showcase")
    w.ai_enabled = False
    return w


def test_a_faction_cannot_command_another_factions_things():
    w = _w()
    blue_wh = con.faction_warehouse(w, "Blue")
    red_u = next(u for u in w.units.values() if u["faction_name"] == "Red")
    blue_u = next(u for u in w.units.values() if u["faction_name"] == "Blue")
    assert w.queue(blue_wh["id"], "x", faction="Red")["reason"] == "not_yours"
    assert w.cancel(blue_wh["id"], 0, faction="Red")["reason"] == "not_yours"
    assert w.rally(blue_wh["id"], 5, 5, faction="Red")["reason"] == "not_yours"
    assert w.demolish(blue_wh["id"], faction="Red")["reason"] == "not_yours"
    assert w.move([blue_u["id"]], 5, 5, faction="Red")["reason"] == "not_yours"
    assert w.stop([red_u["id"], blue_u["id"]], faction="Red")["reason"] == "not_yours"
    assert w.deploy(blue_u["id"], faction="Red")["reason"] == "not_yours"
    assert w.order(blue_u["id"], red_u["id"], faction="Red")["reason"] == "not_yours"
    assert w.ability("Red", "board", unit=blue_u["id"], transport=red_u["id"])["reason"] == "not_yours"


def test_god_mode_without_a_faction_is_unchanged():
    w = _w()
    blue_u = next(u for u in w.units.values() if u["faction_name"] == "Blue")
    assert w.move([blue_u["id"]], blue_u["tx"] + 1, blue_u["ty"]).get("reason") != "not_yours"
