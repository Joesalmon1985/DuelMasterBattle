"""T2.3: candidate generation for the nine heads. Every candidate is applied to an isolated copy of the world and the simulator's answer is counted; the
generator is deterministic, structurally sound, covers every HybridEnv op, and reveals nothing the faction has not seen."""
import collections
import os
import pickle
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import neuro_worlds as NW
from neuro import schema as S
from neuro.candidates import HEADS, Candidate, CandidateGenerator
from neuro.observer import FactionObserver
from test_neuro_features import _scramble_what_a_faction_cannot_see
from wizard_rts.sim_api import ACTION_OPS, HybridEnv

FACTIONS = ("Red", "Blue", "Green", "Yellow", "Purple", "Orange")
SCENES = {"world20": FACTIONS, "rich_world": ("Red", "Blue"), "modern_world": ("Red",)}
CAP = {"world20": 40, "rich_world": 60, "modern_world": 60}
_BLOBS: dict[str, bytes] = {}
_STATS: dict[str, dict] = {}


def blob(name):
    if name not in _BLOBS:
        w = NW.world_at(20) if name == "world20" else getattr(NW, name)()
        _BLOBS[name] = pickle.dumps(w, protocol=5)
    return _BLOBS[name]


def generate(name, faction, t=1200):
    w = pickle.loads(blob(name))
    ob = FactionObserver(w, faction)
    gen = CandidateGenerator(SimpleNamespace(world=w), faction, ob)
    return w, ob, gen, ob.observe(t)


def apply_isolated(name, faction, cand):
    w = pickle.loads(blob(name))
    env = HybridEnv(seed=1, map_size="standard", agent_factions=(faction,), step_ms=1000, profile="campaign")
    env.world = w
    return env.apply(faction, cand.action)


def op_name(c):
    return c.action["op"] + (":" + c.action["what"] if c.action["op"] == "ability" else "")


def acceptance(name):
    """{head: [accepted, tried]} and {head: Counter(reason)} for a scene, sampling up to CAP candidates per head and faction (evenly spaced)."""
    if name in _STATS:
        return _STATS[name]
    rate = collections.defaultdict(lambda: [0, 0])
    reasons = collections.defaultdict(collections.Counter)
    made = collections.Counter()
    for f in SCENES[name]:
        _w, _ob, gen, obs = generate(name, f)
        for head, lst in gen.all(obs).items():
            made[head] += len(lst)
            step = max(1, len(lst) // CAP[name])
            for c in lst[::step][:CAP[name]]:
                r = apply_isolated(name, f, c)
                rate[head][1] += 1
                if r.get("status") == "ok":
                    rate[head][0] += 1
                else:
                    reasons[head][r.get("reason")] += 1
    _STATS[name] = (dict(rate), dict(reasons), dict(made))
    return _STATS[name]


# ------------------------------------------------------------------------------------------------------------------------ acceptance
@pytest.mark.parametrize("scene", sorted(SCENES))
def test_the_simulator_accepts_the_candidates(scene):
    rate, reasons, made = acceptance(scene)
    total_ok = sum(a for a, _t in rate.values())
    total = sum(t for _a, t in rate.values())
    print(f"\n{scene}: candidates generated {made}")
    for head in sorted(rate):
        a, t = rate[head]
        print(f"  {head}: {a}/{t} = {100 * a / max(1, t):.1f}%  {reasons.get(head, {})}")
    print(f"  overall {total_ok}/{total} = {100 * total_ok / max(1, total):.1f}%")
    assert total_ok / total >= 0.95
    for head, (a, t) in rate.items():
        if head == "H7":
            assert a >= 1 or t == 0, "no trade candidate was accepted"
            assert set(reasons.get("H7", {})) <= {"partner_cannot_supply"}  # the partner's stock is hidden: the simulator may refuse, and that is the only reason
        else:
            assert a / t >= 0.95, (head, reasons.get(head))


def test_every_head_has_candidates_somewhere_and_the_whole_command_surface_is_covered():
    seen_heads, seen_ops = collections.Counter(), collections.Counter()
    for scene, factions in SCENES.items():
        for f in factions:
            _w, _ob, gen, obs = generate(scene, f)
            for head, lst in gen.all(obs).items():
                seen_heads[head] += len(lst)
                for c in lst:
                    seen_ops[op_name(c)] += 1
    assert set(seen_heads) == set(HEADS) and all(seen_heads[h] > 0 for h in HEADS), seen_heads
    for ability in ("capture", "infiltrate", "c4", "repair", "lay_mine", "board", "power"):
        assert seen_ops["ability:" + ability] > 0, ability
    covered = {k.split(":")[0] for k in seen_ops}
    # waterway needs a shore: it has its own test below
    assert set(ACTION_OPS) - covered <= {"waterway"}, sorted(set(ACTION_OPS) - covered)
    print("\ncandidates by op across the scenes:", dict(seen_ops))


def test_a_waterway_candidate_appears_between_two_shore_buildings_and_is_accepted():
    from test_widelands_completion import coastal_spots, raw_building, world as coastal_world
    from wizard_rts import construction as con

    w = coastal_world()
    spots = coastal_spots(w)
    a = raw_building(w, "tavern", spots[0], store=False)
    cand = None
    for tile in [p for p in spots if 3 <= abs(p[0] - spots[0][0]) + abs(p[1] - spots[0][1]) <= 12][:30]:
        b = raw_building(w, "tavern", tile)
        probe = pickle.loads(pickle.dumps(w, protocol=5))
        if probe.waterway("Red", a["id"], b["id"])["status"] == "ok":
            cand = b
            break
        w.buildings.pop(b["id"])
    if cand is None:
        pytest.skip("no waterway site on this seed")
    gen = CandidateGenerator(SimpleNamespace(world=w), "Red", FactionObserver(w, "Red"))
    obs = gen.observer.observe(600)
    ways = [c for c in gen.all(obs)["H2"] if c.action["op"] == "waterway"]
    assert ways, "the generator did not offer the waterway the simulator accepts"
    env = HybridEnv(seed=1, map_size="standard", agent_factions=("Red",), step_ms=1000, profile="campaign")
    env.world = w
    assert env.apply("Red", ways[0].action)["status"] == "ok"
    assert con.faction_warehouse(w, "Red") is not None


# ------------------------------------------------------------------------------------------------------------------------ structure
@pytest.mark.parametrize("scene", sorted(SCENES))
def test_candidates_are_well_formed(scene):
    for f in SCENES[scene]:
        _w, _ob, gen, obs = generate(scene, f)
        for head, lst in gen.all(obs).items():
            keys = [c.key for c in lst]
            assert len(keys) == len(set(keys)), (head, "duplicate keys")
            for c in lst:
                assert isinstance(c, Candidate) and c.head == head and c.action["op"] in ACTION_OPS
                assert c.features.dtype == np.float32 and c.features.shape == (len(S.HEAD_RAW[head]),), (head, c.features.shape)
                assert np.isfinite(c.features).all() and (np.abs(c.features) <= 5.0).all()
                assert c.key[0] == head
                for k in ("settlement", "building", "factory", "founder", "post", "slot", "card", "a", "b"):
                    if k in c.refs and isinstance(c.refs[k], int) and c.refs[k] >= 0:
                        limit = {"settlement": len(obs.s_ids), "building": len(obs.b_ids), "factory": len(obs.b_ids), "post": len(obs.b_ids), "a": len(obs.b_ids), "b": len(obs.b_ids),
                                 "founder": len(obs.u_ids), "slot": len(obs.n13_factions), "card": len(obs.card_ids)}[k]
                        assert c.refs[k] < limit, (head, k, c.refs[k], limit)
                for r in c.refs.get("squad", []):
                    assert 0 <= r < len(obs.u_ids)
                if "kind_row" in c.refs:
                    assert 0 <= c.refs["kind_row"] < len(__import__("neuro.features", fromlist=["x"]).kind_static())
    # the caps of the design: at most 96 build pairs per decision
    _w, _ob, gen, obs = generate("world20", "Red")
    assert len(gen.all(obs)["H1"]) <= 96


# ------------------------------------------------------------------------------------------------------------------------ determinism
def _summary(cands):
    return {h: [(c.key, tuple(c.features.tolist()), repr(c.action)) for c in lst] for h, lst in cands.items()}


def test_the_same_world_gives_the_same_candidates():
    a = _summary(generate("rich_world", "Red")[2].all(generate("rich_world", "Red")[3]))
    b = _summary(generate("rich_world", "Red")[2].all(generate("rich_world", "Red")[3]))
    assert a == b


def _digest_in_subprocess(hashseed):
    root, repo, tests = Path(__file__).resolve().parents[1], Path(__file__).resolve().parents[2], Path(__file__).resolve().parent
    code = (f"import sys; sys.path[:0] = [{str(root)!r}, {str(repo)!r}, {str(tests)!r}]\n"
            "import hashlib\nfrom types import SimpleNamespace\nimport neuro_worlds as NW\n"
            "from neuro.candidates import CandidateGenerator\nfrom neuro.observer import FactionObserver\n"
            "w = NW.world_at(4)\n"
            "h = hashlib.sha256()\n"
            "for f in ('Red', 'Blue'):\n"
            "    ob = FactionObserver(w, f); gen = CandidateGenerator(SimpleNamespace(world=w), f, ob)\n"
            "    for head, lst in sorted(gen.all(ob.observe(240)).items()):\n"
            "        for c in lst: h.update(repr((c.key, c.action)).encode()); h.update(c.features.tobytes())\n"
            "print(h.hexdigest())\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**os.environ, "PYTHONHASHSEED": str(hashseed)}, timeout=900)
    assert out.returncode == 0, out.stderr[-2000:]
    return out.stdout.strip().splitlines()[-1]


def test_candidates_do_not_depend_on_the_hash_seed():
    assert _digest_in_subprocess(1) == _digest_in_subprocess(2)


# ------------------------------------------------------------------------------------------------------------------------ hidden information
@pytest.mark.parametrize("scene,me", [("world20", "Red"), ("world20", "Green"), ("rich_world", "Red")])
def test_candidates_do_not_change_when_only_unseen_things_change(scene, me):
    w1, _ob1, gen1, obs1 = generate(scene, me)
    w2 = pickle.loads(blob(scene))
    _scramble_what_a_faction_cannot_see(w2, me)
    ob2 = FactionObserver(w2, me)
    gen2 = CandidateGenerator(SimpleNamespace(world=w2), me, ob2)
    obs2 = ob2.observe(1200)
    assert _summary(gen1.all(obs1)) == _summary(gen2.all(obs2))


def test_the_trade_candidates_do_not_depend_on_the_partners_stock():
    w1, _ob, gen, obs = generate("rich_world", "Red")
    before = [c for c in gen.all(obs)["H7"]]
    assert before
    w2 = pickle.loads(blob("rich_world"))
    for b in w2.buildings.values():
        if b["faction_name"] in ("Blue", "Green") and b["id"] in w2.stocks:
            w2.stocks[b["id"]] = {g: 0 for g in w2.stocks[b["id"]]}  # the partners' stores are emptied: Red cannot know
    ob2 = FactionObserver(w2, "Red")
    after = CandidateGenerator(SimpleNamespace(world=w2), "Red", ob2).all(ob2.observe(1200))["H7"]
    assert [(c.key, c.action) for c in before] == [(c.key, c.action) for c in after]


# ------------------------------------------------------------------------------------------------------------------------ bookkeeping and cost
def test_a_rejected_candidate_is_withheld_for_sixty_seconds_and_nothing_else_changes():
    _w, ob, gen, obs = generate("world20", "Red")
    first = gen.all(obs)
    victim = first["H1"][0]
    gen.note_rejection(victim, "tile_occupied", 1200)
    again = gen.all(ob.observe(1260))
    assert victim.key not in {c.key for c in again["H1"]} and len(again["H1"]) >= len(first["H1"]) - 1
    later = gen.all(ob.observe(1300))
    assert victim.key in {c.key for c in later["H1"]} or len(later["H1"]) == 96  # after the 60 s it may be offered again
    assert gen.rejections == {"tile_occupied": 1}


def test_candidate_generation_time_is_reported_and_bounded():
    rows = {}
    for scene in ("world20", "rich_world"):
        for f in SCENES[scene]:
            w = pickle.loads(blob(scene))
            ob = FactionObserver(w, f)
            gen = CandidateGenerator(SimpleNamespace(world=w), f, ob)
            ob.observe(1140)
            gen.all(ob.observe(1200))
            ts = []
            for i in range(6):
                obs = ob.observe(1260 + 60 * i)
                t = time.perf_counter()
                gen.all(obs)
                ts.append((time.perf_counter() - t) * 1000)
            rows[f"{scene}/{f}"] = sum(ts) / len(ts)
    print("candidate generation ms per decision:", {k: round(v, 1) for k, v in rows.items()}, "mean", round(sum(rows.values()) / len(rows), 1))
    assert max(rows.values()) < 120.0  # a pathology guard; the target (10 ms) is reported in the milestone evidence
