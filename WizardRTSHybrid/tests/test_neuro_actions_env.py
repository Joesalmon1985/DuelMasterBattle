"""T1.4: the full command surface of HybridEnv. Every op checks ownership, answers a malformed payload with `malformed:*`, and works where the
simulation allows it (industry fixtures in a developer world; two factions for trade and diplomacy)."""
import os

import pytest

import test_industry_mechanics as TIM
from wizard_rts import construction as con
from wizard_rts import diplomacy, tech, trade
from wizard_rts.economy import produce
from wizard_rts.industry import fixture as F
from wizard_rts.sim_api import ACTION_OPS, HybridEnv
from wizard_rts.world import HybridWorld


def _env(world=None):
    os.environ.setdefault("HYBRID_AI", "1")
    env = HybridEnv(507, agent_factions=("Red",), profile="developer", step_ms=1000)
    env.reset()
    if world is not None:
        env.world = world
    env.world.ai_enabled = False
    env.world.outbreaks_enabled = False
    return env


NEW_OPS = ("belt", "upgrade", "configure", "link_power", "trade", "propose", "respond", "break_treaty")


def test_the_new_ops_are_part_of_the_action_surface():
    assert set(NEW_OPS) <= set(ACTION_OPS)


# ---------------------------------------------------------------- ownership

def test_every_op_that_names_a_building_rejects_a_foreign_one():
    env = _env()
    w = env.world
    foe = con.faction_warehouse(w, "Blue")["id"]
    mine = con.faction_warehouse(w, "Red")["id"]
    cases = [
        {"op": "upgrade", "building": foe, "to": "mdy:mechanical_drill"},
        {"op": "configure", "building": foe, "key": "target", "value": "copper"},
        {"op": "link_power", "a": foe, "b": mine},
        {"op": "link_power", "a": mine, "b": foe},
        {"op": "trade", "building": foe, "partner": mine, "give": {"log": 1}, "want": {"iron": 1}},
    ]
    for action in cases:
        res = env.apply("Red", action)
        assert res["status"] == "rejected" and res["reason"] == "not_yours", (action, res)


def test_an_offer_can_only_be_answered_by_the_faction_it_is_addressed_to():
    env = _env()
    w = env.world
    res = env.apply("Red", {"op": "propose", "to": "Blue", "state": "truce"})
    assert res["status"] == "ok"
    offer = res["offer"]
    assert env.apply("Green", {"op": "respond", "offer": offer, "accept": True})["reason"] == "not_yours"
    assert env.apply("Red", {"op": "respond", "offer": offer, "accept": True})["reason"] == "not_yours"  # the proposer cannot accept its own offer
    assert diplomacy.state_of(w, "Red", "Blue") == "war"
    assert env.apply("Blue", {"op": "respond", "offer": offer, "accept": True}) == {"status": "ok", "accepted": True}
    assert diplomacy.state_of(w, "Red", "Blue") == "truce"
    assert env.apply("Blue", {"op": "respond", "offer": offer, "accept": True})["reason"] == "no_offer"


def test_diplomacy_rejects_nonsense():
    env = _env()
    assert env.apply("Red", {"op": "propose", "to": "Red", "state": "truce"})["reason"] == "bad_offer"
    assert env.apply("Red", {"op": "propose", "to": "Nobody", "state": "truce"})["reason"] == "bad_offer"
    assert env.apply("Red", {"op": "propose", "to": "Blue", "state": "war"})["reason"] == "bad_offer"
    assert env.apply("Red", {"op": "break_treaty", "with": "Blue"})["reason"] == "already_at_war"
    assert env.apply("Red", {"op": "break_treaty", "with": "Red"})["reason"] == "bad_relation"


def test_a_treaty_can_be_broken_by_either_side():
    env = _env()
    w = env.world
    offer = env.apply("Red", {"op": "propose", "to": "Blue", "state": "peace"})["offer"]
    env.apply("Blue", {"op": "respond", "offer": offer, "accept": True})
    assert diplomacy.state_of(w, "Red", "Blue") == "peace"
    assert env.apply("Blue", {"op": "break_treaty", "with": "Red"})["status"] == "ok"
    assert diplomacy.state_of(w, "Red", "Blue") == "war"


# ---------------------------------------------------------------- malformed payloads

@pytest.mark.parametrize("action", [
    {"op": "belt"},
    {"op": "belt", "tiles": "xy"},
    {"op": "belt", "tiles": [[1]]},
    {"op": "upgrade"},
    {"op": "configure", "building": "building:1"},
    {"op": "link_power", "a": "x"},
    {"op": "trade", "building": "x"},
    {"op": "propose"},
    {"op": "respond", "offer": "offer:0"},
    {"op": "break_treaty"},
])
def test_a_malformed_payload_is_rejected_not_raised(action):
    env = _env()
    res = env.apply("Red", action)
    assert res["status"] == "rejected" and res["reason"].startswith("malformed:"), res


# ---------------------------------------------------------------- the commands work where the simulation allows them

def _dev_world():
    w = TIM.world()
    TIM.cards(w)
    return w


def test_configure_link_power_and_belt_work_through_the_env():
    w = _dev_world()
    env = _env(w)
    x, y = F.open_ground(w, "Red", 14, 3)
    fp = [(x + a, y + b) for b in range(2) for a in range(2)]
    TIM.deposit(w, fp, "iron")
    drill = F.instant_machine(w, "Red", "mdy:mechanical_drill", (x, y))
    assert env.apply("Red", {"op": "configure", "building": drill, "key": "target", "value": "copper"})["status"] == "ok"
    assert env.apply("Red", {"op": "configure", "building": drill, "key": "target", "value": "nonsense"})["reason"] == "cannot_extract_here"
    # a belt from beside the drill (granted goods: the developer fixture)
    F.grant_goods(w, "Red")
    res = env.apply("Red", {"op": "belt", "tiles": [[x + 2 + i, y] for i in range(5)], "end_dir": 0, "kind": "mdy:conveyor"})
    assert res["status"] == "ok", res
    assert "snapshot" not in res
    # power: a node and a panel in range
    x2, y2 = F.open_ground(w, "Red", 12, 3, near=(x, y + 6))
    panel = F.instant_machine(w, "Red", "mdy:solar_panel", (x2, y2))
    node = F.instant_machine(w, "Red", "mdy:power_node", (x2 + 4, y2))
    TIM.run(w, 2)
    far = F.instant_machine(w, "Red", "mdy:solar_panel", (x2 + 9, y2))
    assert env.apply("Red", {"op": "link_power", "a": node, "b": far}) == {"status": "ok"}  # edge to edge, within the node's laser range
    assert env.apply("Red", {"op": "link_power", "a": node, "b": far})["reason"] == "already_linked"
    assert node in env.legal_actions("Red")["link_power"]
    assert env.apply("Red", {"op": "link_power", "a": panel, "b": node})["reason"] == "not_a_node"


def test_upgrade_turns_a_real_mine_into_a_drill_through_the_env():
    w = _dev_world()
    env = _env(w)
    mine, _tile, _fp = TIM._real_mine(w)
    F.grant_goods(w, "Red")
    assert env.apply("Red", {"op": "upgrade", "building": mine, "to": "mdy:silicon_smelter"})["reason"] == "cannot_upgrade"
    listed = [u for u in env.legal_actions("Red")["upgrade"] if u["building"] == mine]
    assert any(u["to"] == "mdy:mechanical_drill" for u in listed)
    res = env.apply("Red", {"op": "upgrade", "building": mine, "to": "mdy:mechanical_drill"})
    assert res["status"] == "ok", res


def _traders(allied=False):
    w = HybridWorld(507, profile="developer")
    w.ai_enabled = False
    w.outbreaks_enabled = False
    for f in ("Red", "Blue"):
        tech.grant(w, f, "dmb.card.trade")
    a, b = con.faction_warehouse(w, "Red"), con.faction_warehouse(w, "Blue")
    for wh, goods in ((a, {"log": 60, "ration": 2}), (b, {"iron": 20})):
        for g, n in goods.items():
            produce(w, wh["id"], g, n)
            w.stats["made_" + g] = w.stats.get("made_" + g, 0) + n
    if allied:
        diplomacy.set_state(w, "Red", "Blue", "alliance", why="test")
    return w, a, b


def test_a_caravan_goes_only_to_a_partner_the_faction_knows():
    w, a, b = _traders()
    env = _env(w)
    deal = {"op": "trade", "building": a["id"], "partner": b["id"], "give": {"log": 14}, "want": {"iron": 3}}
    assert env.apply("Red", deal)["reason"] == "unknown_partner"  # Blue's warehouse is hundreds of tiles away and has never been seen
    from wizard_rts import visibility

    visibility.remember(w, "Red", b)  # a scout saw it
    res = env.apply("Red", deal)
    assert res["status"] == "ok", res
    assert [t for t in env.legal_actions("Red")["trade"] if t["partner"] == b["id"]]


def test_an_ally_is_a_known_partner():
    w, a, b = _traders(allied=True)
    env = _env(w)
    assert {"building": a["id"], "partner": b["id"], "partner_faction": "Blue"} in env.legal_actions("Red")["trade"]
    res = env.apply("Red", {"op": "trade", "building": a["id"], "partner": b["id"], "give": {"log": 14}, "want": {"iron": 3}})
    assert res["status"] == "ok", res


def test_the_masks_for_diplomacy_list_what_is_possible():
    env = _env()
    acts = env.legal_actions("Red")
    assert {p["to"] for p in acts["propose"]} == {"Blue", "Green", "Yellow", "Purple", "Orange"}
    assert all(p["states"] == ["truce", "peace", "alliance"] for p in acts["propose"])
    assert acts["break_treaty"] == [] and acts["respond"] == []
    offer = env.apply("Blue", {"op": "propose", "to": "Red", "state": "truce"})["offer"]
    assert env.legal_actions("Red")["respond"] == [{"offer": offer, "from": "Blue", "state": "truce"}]


def test_step_can_skip_the_observation():
    env = _env()
    obs, rewards, terminated, truncated, info = env.step({}, observe=False)
    assert obs == {} and "Red" in rewards and "Red" in terminated and info["game_ms"] > 0
    obs2, *_ = env.step({})
    assert "Red" in obs2


def test_abilities_that_name_a_building_need_a_building_the_faction_can_see_or_remembers():
    env = _env()
    w = env.world
    foe = con.faction_warehouse(w, "Blue")["id"]
    mine = con.faction_warehouse(w, "Red")["id"]
    engineer = w._unit(w.faction_info["Red"]["id"], "Red", "engineer", "Engineer", "openra.e6", (con.faction_warehouse(w, "Red")["tx"] + 3, con.faction_warehouse(w, "Red")["ty"] + 3))
    for what in ("capture", "infiltrate", "c4"):
        res = env.apply("Red", {"op": "ability", "what": what, "unit": engineer, "building": foe})
        assert res["status"] == "rejected" and res["reason"] == "not_visible", (what, res)
    assert env.apply("Red", {"op": "ability", "what": "repair", "unit": engineer, "building": foe})["reason"] == "not_yours"
    from wizard_rts import visibility

    visibility.remember(w, "Red", w.buildings[foe])  # once seen, the building may be named (the simulator then judges the ability itself)
    assert env.apply("Red", {"op": "ability", "what": "capture", "unit": engineer, "building": foe})["reason"] != "not_visible"
    assert env.apply("Red", {"op": "ability", "what": "repair", "unit": engineer, "building": mine})["reason"] == "undamaged"
