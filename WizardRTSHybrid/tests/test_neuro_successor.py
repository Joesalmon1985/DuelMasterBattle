"""T1.2 and T1.3: a split successor is played by somebody (N07), and a faction is alive until history collapses it."""
import os

from wizard_rts import construction as con
from wizard_rts import history, territory
from wizard_rts.sim_api import HybridEnv


def _env(agent):
    os.environ.setdefault("HYBRID_AI", "1")
    env = HybridEnv(507, agent_factions=(agent,), profile="developer", step_ms=1000)
    env.reset()
    return env


def _found_second_settlement(w, name):
    """Deploy a settler 40-140 tiles from the faction's home (the same fixture the civilisation-rule tests use) and return its settlement record."""
    home = con.faction_warehouse(w, name)
    t = w.terrain
    for y in range(8, t.h - 8, 4):
        for x in range(8, t.w - 8, 4):
            d = territory.cheb((x, y), (home["tx"], home["ty"]))
            if d < 60 or d > 140:
                continue
            u = {"id": "u", "definition": territory.SETTLER_DEFINITION, "faction_name": name, "alive": True, "tx": x, "ty": y}
            if territory.deploy_check(w, u) is None:
                uid = w._unit(w.faction_info[name]["id"], name, "settlers", "Settlers", territory.SETTLER_DEFINITION, (x, y))
                territory._create_command_center(w, w.units[uid])
                return next(r for r in w.dmb.settlements.values() if r["faction"] == name and not r.get("home") and tuple(r["tile"]) == (x, y))
    raise AssertionError("no site for a second settlement")


def test_the_successor_of_a_heuristic_seat_is_played_by_the_built_in_ai():
    env = _env("Red")
    w = env.world
    rec = _found_second_settlement(w, "Orange")
    assert "Orange" in w.ai_factions
    successor = history.split(w, "Orange", rec)
    assert successor in w.ai_factions and successor not in w.__dict__.get("agent_successors", {}).get("Orange", [])
    mark = len(w.events)
    for _ in range(60):
        env.step({})
    acted = [e for e in w.events[mark:] if e.get("kind") in ("card_drafted", "ai_build") and e.get("faction") == successor]
    assert acted, "the successor issued no command within 60 s"  # a fresh successor has an empty store: its first act is the card draft


def test_the_successor_of_an_agent_seat_is_an_extra_seat_of_that_agent():
    env = _env("Red")
    w = env.world
    assert env.seats_of("Red") == ["Red"]
    rec = _found_second_settlement(w, "Red")
    successor = history.split(w, "Red", rec)
    assert successor not in w.ai_factions  # the built-in AI does not play it
    assert env.seats_of("Red") == ["Red", successor] and env.seats() == ["Red", successor]
    mark = len(w.events)
    obs, rewards, terminated, truncated, info = env.step({})
    for _ in range(59):
        env.step({})
    assert not [e for e in w.events[mark:] if e.get("kind") in ("card_drafted", "ai_build") and e.get("faction") == successor]  # nobody plays it but the agent
    assert set(obs) == {"Red", successor} and successor in rewards and successor in terminated and info["seats"] == ["Red", successor]
    menu = env.legal_actions(successor)
    assert menu["draft"], "a fresh successor holds card offers"
    res = env.apply(successor, {"op": "draft", "card": menu["draft"][0]})
    assert res["status"] == "ok", res
    # and it cannot touch the parent's things
    parent_wh = con.faction_warehouse(w, "Red")
    assert env.apply(successor, {"op": "demolish", "building": con.faction_warehouse(w, "Blue")["id"]})["reason"] == "not_yours"
    assert parent_wh is not None


def test_a_successor_of_a_successor_is_still_the_same_agents_seat():
    env = _env("Red")
    w = env.world
    first = history.split(w, "Red", _found_second_settlement(w, "Red"))
    second = history.split(w, first, _found_second_settlement(w, first))
    assert env.seats_of("Red") == ["Red", first, second]


def test_a_faction_that_loses_its_capital_building_but_holds_another_settlement_is_still_alive():
    env = _env("Orange")
    w = env.world
    _found_second_settlement(w, "Orange")
    home = con.faction_warehouse(w, "Orange")
    w.damage_building(home["id"], 10**9, ["structure"], {})
    for _ in range(20):
        obs, rewards, terminated, truncated, info = env.step({})
    assert terminated["Orange"] is False and obs["Orange"]["alive"] is True
    assert info["faction_states"]["Orange"] in ("active", "declining")


def test_a_faction_with_nothing_left_is_collapsed_and_terminated():
    env = _env("Red")
    w = env.world
    wh = con.faction_warehouse(w, "Red")
    w.damage_building(wh["id"], 10**9, ["structure"], {})
    for u in list(w.units.values()):
        if u["faction_name"] == "Red" and territory.is_founder(u):
            u["alive"] = False
    for _ in range(30):
        obs, rewards, terminated, truncated, info = env.step({})
        if terminated["Red"]:
            break
    assert terminated["Red"] is True and info["faction_states"]["Red"] == "collapsed" and obs["Red"]["alive"] is False
    assert rewards["Red"] <= env.weights["eliminated"] + 5
