from wizard_rts import construction as con
from wizard_rts import visibility
from wizard_rts.sim_api import HybridEnv
from wizard_rts.world import HybridWorld


def _w():
    w = HybridWorld(507, profile="test_showcase")
    w.ai_enabled = False
    return w


def test_a_faction_sees_near_its_own_things_and_not_across_the_map():
    w = _w()
    red = con.faction_warehouse(w, "Red")
    blue = con.faction_warehouse(w, "Blue")
    assert visibility.visible(w, "Red", red["tx"] + 3, red["ty"])
    far = max(abs(red["tx"] - blue["tx"]), abs(red["ty"] - blue["ty"]))
    assert far > 40
    assert not visibility.visible(w, "Red", blue["tx"], blue["ty"])
    seen = visibility.seen_enemies(w, "Red")
    assert all(e["faction"] != "Red" for e in seen["buildings"] + seen["units"])
    assert all(e["id"] != blue["id"] for e in seen["buildings"])


def test_an_enemy_unit_that_walks_into_sight_is_seen_and_remembered():
    w = _w()
    red = con.faction_warehouse(w, "Red")
    foe = next(u for u in w.units.values() if u["faction_name"] == "Blue")
    foe["tx"], foe["ty"] = red["tx"] + 4, red["ty"]
    assert foe["id"] in [e["id"] for e in visibility.seen_enemies(w, "Red")["units"]]
    visibility.refresh(w, "Red")
    assert visibility.known(w, "Red", foe["tx"], foe["ty"])
    foe["tx"] += 60
    assert foe["id"] not in [e["id"] for e in visibility.seen_enemies(w, "Red")["units"]]
    assert visibility.known(w, "Red", red["tx"] + 4, red["ty"])  # the ground stays explored


def test_the_observation_hides_capitals_never_seen():
    env = HybridEnv(seed=507, agent_factions=["Red"])
    env.reset()
    obs = env.observe("Red")
    blue = con.faction_warehouse(env.world, "Blue")
    assert "Blue" not in obs["enemy_capitals"] and "visible" in obs
    env.world.vis_explored = {}
    visibility.explored_of(env.world, "Red").add((blue["tx"] // visibility.CELL, blue["ty"] // visibility.CELL))
    assert env.observe("Red")["enemy_capitals"].get("Blue") == [blue["tx"], blue["ty"]]
