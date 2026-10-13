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


# ---------------------------------------------------------------- expansion through the training interface

def _env_with_mcv(seed: int = 507):
    from wizard_rts import territory

    env = HybridEnv(seed, agent_factions=("Red",), step_ms=5000)
    env.reset()
    w = env.world
    site = None
    from wizard_rts import ai

    probe = w._unit(w.faction_info["Red"]["id"], "Red", "mcv", "MCV", "openra.mcv", (w.player["tx"], w.player["ty"]))
    site = ai._find_expansion_site(w, "Red", w.units[probe])
    w.units.pop(probe)
    assert site is not None
    uid = w._unit(w.faction_info["Red"]["id"], "Red", "mcv", "MCV", "openra.mcv", tuple(site))
    w.units[uid]["cargo"] = {"log": 3, "plank": 2, "granite": 1}
    return env, uid, site, territory


def test_deploy_is_an_action_with_a_mask_and_the_same_rules() -> None:
    env, uid, site, territory = _env_with_mcv()
    mask = env.legal_actions("Red")
    assert {"unit": uid, "ok": True, "reason": ""} in mask["deploy"]
    bad = env.world._unit(env.world.faction_info["Red"]["id"], "Red", "mcv", "MCV", "openra.mcv", (con.faction_warehouse(env.world, "Red")["tx"] + 6, con.faction_warehouse(env.world, "Red")["ty"] + 6))
    mask = env.legal_actions("Red")
    refused = next(d for d in mask["deploy"] if d["unit"] == bad)
    assert refused["ok"] is False and refused["reason"] == "overlaps_friendly_territory"
    assert any(e["unit"] == bad for e in mask["expansion_sites"]), "a refused MCV is offered a legal site"
    assert env.apply("Red", {"op": "deploy", "unit": bad})["reason"] == "overlaps_friendly_territory"
    assert env.apply("Blue", {"op": "deploy", "unit": uid})["reason"] == "not_yours"
    cells_before = env._territory("Red")
    assert env.apply("Red", {"op": "deploy", "unit": uid})["status"] == "ok"
    obs, rew, *_ = env.step({"Red": []})
    assert len(obs["Red"]["command_centers"]) == 2 and obs["Red"]["command_centers"][1]["outpost"] is True
    assert env._territory("Red") > cells_before
    assert rew["Red"] > 0, "territory is rewarded"
    assert uid not in env.world.units


def test_expansion_episode_is_deterministic_and_saves_and_replays() -> None:
    def run() -> tuple[str, list]:
        env, uid, site, territory = _env_with_mcv()
        env.step({"Red": [{"op": "deploy", "unit": uid}]})
        for _ in range(8):
            env.step({"Red": []})
        return env.state_hash(), env.log

    h1, log1 = run()
    h2, _ = run()
    assert h1 == h2
    env, uid, site, territory = _env_with_mcv()
    env.step({"Red": [{"op": "deploy", "unit": uid}]})
    blob = env.save()
    env.step({"Red": []})
    h_cont = env.state_hash()
    twin = HybridEnv(507, agent_factions=("Red",), step_ms=5000)
    twin.load(blob)
    twin.step({"Red": []})
    assert twin.state_hash() == h_cont
    assert len(env.flatten(env.observe("Red"))) == len(env.flatten(env.observe("Red")))


def test_turret_slot_points_at_the_target_in_red_alert_frame_order():
    import math

    from wizard_rts.world import HybridWorld

    w = HybridWorld(507, profile="test_showcase")
    w.ai_enabled = False
    w.visual_state = True
    red, blue = w.faction_info["Red"], w.faction_info["Blue"]
    shooter = w._unit(red["id"], "Red", "tank", "Tank", "openra.3tnk", (80, 80))
    w.units[shooter]["weapon"] = "120mm"
    cases = {(80, 70): 0, (70, 80): 8, (80, 90): 16, (90, 80): 24, (70, 70): 4, (90, 70): 28}  # N, W, S, E, NW, NE (counter-clockwise from north)
    for (tx, ty), slot in cases.items():
        victim = w._unit(blue["id"], "Blue", "tank", "Tank", "openra.3tnk", (tx, ty))
        w.units[shooter]["target"] = {"kind": "unit", "id": victim}
        assert w.turret_slot(w.units[shooter]) == slot, (tx, ty)
        row = next(e for e in w.snapshot()["entities"] if e["id"] == shooter)
        assert row["turret"] == slot
        w.units.pop(victim)
    w.visual_state = False
    w.units[shooter]["target"] = {"kind": "unit", "id": w._unit(blue["id"], "Blue", "tank", "Tank", "openra.3tnk", (80, 70))}
    assert "turret" not in next(e for e in w.snapshot()["entities"] if e["id"] == shooter)  # headless runs never carry it (hash-neutral)


def test_legal_actions_cover_widelands_and_mindustry_kinds_and_every_listed_build_works():
    env = HybridEnv(seed=507, agent_factions=["Red"], profile="test_showcase")
    env.reset()
    w = env.world
    from wizard_rts.industry import registry as ind

    wh = con.faction_warehouse(w, "Red")
    wares = {g for spec in con.full_menu().values() for g in spec["cost"]} | {g for k in ind.kinds() for g in (con.build_spec(k) or {"cost": {}})["cost"]}
    for g in wares:
        w.stocks[wh["id"]][g] = 500
    legal = env.legal_actions("Red")
    kinds = {e["kind"] for e in legal["build"]}
    assert any(k.startswith("wl:barbarians_") for k in kinds) and not any(k.startswith("wl:empire_") for k in kinds)
    assert any(k.startswith("mdy:") for k in kinds)
    for e in legal["build"]:
        x, y = e["sites"][0]
        assert con.check_placement(w, "Red", e["kind"], x, y)[0] is None, e["kind"]  # every listed site is one the simulation accepts
    wl = next(e for e in legal["build"] if e["kind"].startswith("wl:"))
    assert env.apply("Red", {"op": "build", "kind": wl["kind"], "tx": wl["sites"][0][0], "ty": wl["sites"][0][1]})["status"] == "ok"


def test_a_save_loads_in_a_fresh_process_with_the_same_hash_and_a_foreign_format_is_refused(tmp_path):
    import pickle
    import subprocess
    import sys

    env = HybridEnv(seed=507, agent_factions=["Red"])
    env.reset()
    for _ in range(3):
        env.step({"Red": []})
    blob = env.save()
    f = tmp_path / "save.bin"
    f.write_bytes(blob)
    h = env.world.state_hash()
    code = ("import sys; sys.path.insert(0, %r); from wizard_rts.sim_api import HybridEnv; e = HybridEnv(seed=1, agent_factions=['Red']); "
            "e.load(open(%r, 'rb').read()); print(e.world.state_hash())") % (str(Path(__file__).resolve().parents[1]), str(f))
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120)
    assert out.stdout.strip() == h, out.stderr
    old = pickle.loads(blob)
    old["format"] = 1
    import pytest
    with pytest.raises(ValueError):
        HybridEnv(seed=1, agent_factions=["Red"]).load(pickle.dumps(old))
