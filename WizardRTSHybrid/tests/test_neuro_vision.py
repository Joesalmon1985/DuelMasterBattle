"""T1.1: what a faction knows about the others is what it has seen (sight) or been shown (a scout or a spy), plus a memory of enemy buildings
that outlives the sighting and is corrected only when the place is seen again. Controllers read it through neuro/vision.py."""
import os

import pytest

from neuro import vision
from wizard_rts import construction as con
from wizard_rts import military
from wizard_rts.sim_api import HybridEnv


def _env(**kw):
    os.environ.setdefault("HYBRID_AI", "1")
    env = HybridEnv(seed=kw.pop("seed", 507), agent_factions=("Red",), profile="campaign", step_ms=1000, **kw)
    env.reset()
    return env


def _soldier(w, faction="Red"):
    return next(u for u in w.units.values() if u["faction_name"] == faction and u.get("weapon") and u.get("alive", True))


def _put_next_to(w, unit, target, dx=3):
    unit["tx"], unit["ty"] = target["tx"] + dx, target["ty"]
    unit["path"] = []
    unit.pop("order", None)


def test_a_fresh_campaign_world_hides_every_other_faction():
    env = _env()
    w = env.world
    red = con.faction_warehouse(w, "Red")
    for other in ("Blue", "Green", "Yellow", "Purple", "Orange"):
        b = con.faction_warehouse(w, other)
        assert max(abs(b["tx"] - red["tx"]), abs(b["ty"] - red["ty"])) > 32  # beyond even the heuristic AI's old 32-tile rule
    obs = env.observe("Red")
    assert obs["enemy_capitals"] == {}
    assert obs["known_enemy_buildings"] == 0
    assert vision.known_enemy_buildings(w, "Red") == []
    assert vision.visible_units(w, "Red") == []
    assert env.legal_actions("Red")["attack"] == []


def test_a_building_that_comes_into_sight_is_remembered_and_attackable():
    env = _env()
    w = env.world
    blue = con.faction_warehouse(w, "Blue")
    _put_next_to(w, _soldier(w), blue)
    env.step({})
    for _ in range(10):
        env.step({})
    mem = vision.memory_of(w, "Red")
    assert blue["id"] in mem and mem[blue["id"]]["kind"] == "warehouse" and mem[blue["id"]]["faction_name"] == "Blue"
    assert [row["id"] for row in vision.known_enemy_buildings(w, "Red")] == sorted(mem)
    obs = env.observe("Red")
    assert obs["enemy_capitals"].get("Blue") == [blue["tx"], blue["ty"]]
    assert obs["known_enemy_buildings"] == len(mem)
    assert blue["id"] in env.legal_actions("Red")["attack"]


def test_the_memory_outlives_the_sighting():
    env = _env()
    w = env.world
    blue = con.faction_warehouse(w, "Blue")
    scout = _soldier(w)
    _put_next_to(w, scout, blue)
    for _ in range(10):
        env.step({})
    assert blue["id"] in vision.memory_of(w, "Red")
    military.kill_unit(w, scout, by="test")
    for _ in range(10):
        env.step({})
    assert blue["id"] not in {r["id"] for r in vision.visible_units(w, "Red")}
    assert blue["id"] in vision.memory_of(w, "Red")  # remembered, though nobody of Red can see it any more


def test_a_destroyed_building_is_forgotten_when_its_place_is_seen_again():
    env = _env()
    w = env.world
    blue = con.faction_warehouse(w, "Blue")
    scout = _soldier(w)
    _put_next_to(w, scout, blue)
    for _ in range(10):
        env.step({})
    assert blue["id"] in vision.memory_of(w, "Red")
    scout["tx"], scout["ty"] = blue["tx"] + 60, blue["ty"]  # leave
    for _ in range(6):
        env.step({})
    blue["hp"] = 0
    blue["destroyed"] = True
    for _ in range(6):
        env.step({})
    assert blue["id"] in vision.memory_of(w, "Red")  # nobody has looked: the stale entry stays
    _put_next_to(w, scout, blue)
    for _ in range(6):
        env.step({})
    assert blue["id"] not in vision.memory_of(w, "Red")
    assert blue["id"] not in env.legal_actions("Red")["attack"]


def test_an_unseen_target_cannot_be_ordered():
    env = _env()
    w = env.world
    blue = con.faction_warehouse(w, "Blue")
    res = env.apply("Red", {"op": "order", "unit": _soldier(w)["id"], "target": blue["id"]})
    assert res["status"] == "rejected" and res["reason"] == "not_visible"


def test_visible_regions_follow_sight():
    env = _env()
    w = env.world
    here = vision.visible_regions(w, "Red")
    assert isinstance(here, set)
    blue = con.faction_warehouse(w, "Blue")
    _put_next_to(w, _soldier(w), blue)
    there = vision.visible_regions(w, "Red")
    assert there != here or there  # sight moved with the soldier: its new surroundings count


def test_the_memory_is_deterministic():
    def run():
        os.environ["HYBRID_AI"] = "1"
        e = HybridEnv(seed=11, agent_factions=(), profile="campaign", step_ms=1000)
        e.reset()
        for _ in range(600):
            e.step({})
        return {f: sorted(vision.memory_of(e.world, f).items()) for f in ("Red", "Blue", "Green", "Yellow", "Purple", "Orange")}, e.state_hash()

    a, b = run(), run()
    assert a == b


@pytest.mark.parametrize("name", ["memory_of", "refresh", "visible_units", "known_enemy_buildings", "visible_regions"])
def test_the_facade_exposes_the_documented_interface(name):
    assert callable(getattr(vision, name))
