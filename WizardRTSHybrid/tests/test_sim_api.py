"""The headless training interface: deterministic reset and step, masks, rejection, rewards, save/restore, replay.

Level B/C/D. No Godot and no display are involved.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("HYBRID_AI", "1")

from wizard_rts import construction as con  # noqa: E402
from wizard_rts.sim_api import HybridEnv  # noqa: E402


def _scripted(env: HybridEnv, faction: str, steps: int) -> list[dict]:
    """A fixed plan: build the first legal producer site, road it, queue nothing. Returns the per-step action lists."""
    plan = []
    mask = env.legal_actions(faction)
    kinds = {b["kind"]: b["sites"] for b in mask["build"]}
    first = kinds["producer"][0]
    plan.append([{"op": "build", "kind": "producer", "tx": first[0], "ty": first[1]}])
    return plan + [[] for _ in range(steps - 1)]


def _episode(seed: int, steps: int = 6) -> tuple[str, list]:
    env = HybridEnv(seed, agent_factions=("Red",), step_ms=5000)
    env.reset()
    plan = _scripted(env, "Red", steps)
    rewards = []
    for actions in plan:
        obs, rew, term, trunc, info = env.step({"Red": actions})
        rewards.append(rew["Red"])
        if actions:
            site = env.world.buildings[max((b for b in env.world.buildings if env.world.buildings[b]["faction_name"] == "Red"), key=lambda i: int(i.split(":")[1]))]
            env.apply("Red", {"op": "road", "a": site["id"], "b": con.faction_warehouse(env.world, "Red")["id"]})
    return env.state_hash(), rewards


def test_reset_and_step_are_deterministic_for_a_seed() -> None:
    h1, r1 = _episode(507)
    h2, r2 = _episode(507)
    h3, _ = _episode(11)
    assert h1 == h2 and r1 == r2
    assert h1 != h3


def test_agent_faction_is_not_played_by_the_built_in_ai() -> None:
    env = HybridEnv(507, agent_factions=("Red",), step_ms=5000)
    env.reset()
    red_before = sum(1 for b in env.world.buildings.values() if b["faction_name"] == "Red")
    blue_before = sum(1 for b in env.world.buildings.values() if b["faction_name"] == "Blue")
    for _ in range(40):  # 200 game seconds
        env.step({})
    red = sum(1 for b in env.world.buildings.values() if b["faction_name"] == "Red")
    blue = sum(1 for b in env.world.buildings.values() if b["faction_name"] == "Blue")
    assert red == red_before  # nobody builds for Red
    assert blue > blue_before  # the built-in AI still plays Blue


def test_illegal_actions_are_rejected_with_reasons() -> None:
    env = HybridEnv(507, agent_factions=("Red",), step_ms=1000)
    obs = env.reset()
    w = env.world
    wh = con.faction_warehouse(w, "Red")
    water = next((x, y) for y in range(w.terrain.h) for x in range(w.terrain.w) if w.terrain.is_water(x, y) and abs(x - wh["tx"]) + abs(y - wh["ty"]) < 30)
    assert env.apply("Red", {"op": "build", "kind": "producer", "tx": water[0], "ty": water[1]})["reason"] in ("water", "outside_territory")
    assert env.apply("Red", {"op": "build", "kind": "nonsense", "tx": 1, "ty": 1})["reason"] == "unknown_kind"
    blue_b = next(b for b in w.buildings.values() if b["faction_name"] == "Blue" and b["kind"] == "producer")
    assert env.apply("Red", {"op": "demolish", "building": blue_b["id"]})["reason"] == "not_yours"
    blue_u = next(u for u in w.units.values() if u["faction_name"] == "Blue")
    assert env.apply("Red", {"op": "move", "units": [blue_u["id"]], "tx": 5, "ty": 5})["reason"] == "no_units"
    red_u = next(u for u in w.units.values() if u["faction_name"] == "Red" and u["kind"] == "tank")
    assert env.apply("Red", {"op": "move", "units": [red_u["id"]], "tx": water[0], "ty": water[1]})["status"] == "rejected"
    assert env.apply("Red", {"op": "fly"})["reason"] == "unknown_op"
    assert env.apply("Red", {"op": "build", "kind": "producer"})["reason"].startswith("malformed")
    assert obs["Red"]["alive"] is True


def test_legal_action_masks_only_list_actions_the_simulation_accepts() -> None:
    env = HybridEnv(507, agent_factions=("Red",), step_ms=1000)
    env.reset()
    mask = env.legal_actions("Red")
    assert mask["build"] and all(b["sites"] for b in mask["build"])
    for entry in mask["build"][:4]:
        tx, ty = entry["sites"][0]
        why, _ctx = con.check_placement(env.world, "Red", entry["kind"], tx, ty)
        assert why is None, (entry["kind"], why)
    assert {"unit": "infantry"} .items() <= next(q for q in mask["queue"] if q["unit"] == "infantry").items()
    # an unaffordable kind is masked out
    for g in list(env.world.stocks[con.faction_warehouse(env.world, "Red")["id"]]):
        env.world.stocks[con.faction_warehouse(env.world, "Red")["id"]][g] = 0
    assert env.legal_actions("Red")["build"] == []


def test_rewards_follow_measurable_state() -> None:
    env = HybridEnv(507, agent_factions=("Red",), step_ms=5000, weights={"wealth": 0.0, "territory": 1.0})
    env.reset()
    mask = env.legal_actions("Red")
    far = next(b for b in mask["build"] if b["kind"] == "producer")["sites"][-1]
    before_cells = env.observe("Red")["territory_cells"]
    obs, rew, term, trunc, info = env.step({"Red": [{"op": "build", "kind": "producer", "tx": far[0], "ty": far[1]}]})
    assert info["results"]["Red"][0]["status"] == "ok"
    after_cells = obs["Red"]["territory_cells"]
    assert rew["Red"] == float(after_cells - before_cells)  # with only the territory weight, reward is the territory delta
    assert obs["Red"]["constructing"].get("producer") == 1


def test_elimination_terminates_the_faction_and_pays_the_penalty() -> None:
    env = HybridEnv(507, agent_factions=("Red",), step_ms=1000)
    env.reset()
    wh = con.faction_warehouse(env.world, "Red")
    env.world.damage_building(wh["id"], 10**9, ["structure"], {})
    obs, rew, term, trunc, info = env.step({})
    assert term["Red"] is True and obs["Red"]["alive"] is False
    assert rew["Red"] <= env.weights["eliminated"] + 5


def test_battle_counters_attribute_kills_and_losses() -> None:
    env = HybridEnv(507, agent_factions=("Red",), step_ms=1000)
    env.reset()
    w = env.world
    t = w.terrain
    lake = t.meta["homes"][1]["lake"]
    sea = t.water_comp[lake[1] * t.w + lake[0]]
    spots = [(x, y) for x in range(lake[0] - 40, lake[0] + 60) for y in range(lake[1] - 30, lake[1] + 50) if t.in_bounds(x, y) and t.water_comp[y * t.w + x] == sea]
    a = w._unit(w.faction_info["Red"]["id"], "Red", "patrol_boat", "PT", "openra.pt", spots[0])
    b = w._unit(w.faction_info["Green"]["id"], "Green", "patrol_boat", "PT", "openra.pt", (spots[0][0] + 3, spots[0][1]))
    for _ in range(400):
        env.step({})
        if not w.units[a]["alive"] or not w.units[b]["alive"]:
            break
    fs = w.fstats
    dead = a if not w.units[a]["alive"] else b if not w.units[b]["alive"] else None
    assert dead is not None, w.fstats
    if dead is not None:
        winner = "Green" if dead == a else "Red"
        loser = "Red" if dead == a else "Green"
        assert fs[winner]["unit_kills"] >= 1 and fs[loser]["loss_value"] >= 500 and fs[winner]["kill_value"] >= 500


def test_save_restore_continues_identically() -> None:
    env = HybridEnv(507, agent_factions=("Red",), step_ms=5000)
    env.reset()
    for _ in range(5):
        env.step({})
    blob = env.save()
    for _ in range(5):
        env.step({})
    expected = env.state_hash()
    twin = HybridEnv(507, agent_factions=("Red",), step_ms=5000)
    twin.reset()
    twin.load(blob)
    for _ in range(5):
        twin.step({})
    assert twin.state_hash() == expected


def test_recorded_episode_replays_to_the_same_hash() -> None:
    env = HybridEnv(507, agent_factions=("Red",), step_ms=5000)
    env.reset()
    mask = env.legal_actions("Red")
    site = next(b for b in mask["build"] if b["kind"] == "quarry")["sites"][0]
    env.step({"Red": [{"op": "build", "kind": "quarry", "tx": site[0], "ty": site[1]}]})
    for _ in range(8):
        env.step({})
    assert env.replay() == env.state_hash()


def test_flat_observation_has_a_fixed_length() -> None:
    env = HybridEnv(507, agent_factions=("Red", "Blue"), step_ms=5000)
    obs = env.reset()
    env.step({})
    a, b = env.flatten(env.observe("Red")), env.flatten(env.observe("Blue"))
    assert len(a) == len(b) and all(isinstance(x, float) for x in a)
    assert set(obs) == {"Red", "Blue"}
    assert obs["Red"]["local_map"] and len(obs["Red"]["local_map"]) == len(obs["Red"]["local_map"][0])
