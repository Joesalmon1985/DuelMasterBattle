"""Exhaustive small-state checks of every puzzle template: from the start every reachable state can still reach 'solved' (no dead ends), and
the action set the player can actually produce is searched completely, not sampled. Inventory use follows the dungeon: pickups are one-time,
items a puzzle consumes are gone, granted items arrive."""
import itertools
import json

import pytest

from wizard_rts.puzzle import gen, logic

LOCAL = ["clay_idol", "brass_gear", "tallow_candle", "mirror_shard", "black_seed"]


def actions_for(p):
    t = p["type"]
    out = [{"kind": "inspect", "slot": "x"}]
    if t == "offerings":
        out += [{"kind": "place", "slot": s["id"], "item": i} for s in p["slots"] for i in LOCAL + ["grey_stone", "sigil_ash", "sigil_vale"]]
    elif t == "exchange":
        out += [{"kind": "place", "item": i} for i in LOCAL] + [{"kind": "take"}]
    elif t in ("switch_chain",):
        out += [{"kind": "pull", "index": i} for i in range(3)]
    elif t == "mosaic":
        out += [{"kind": "tread", "index": i} for i in range(4)]
    elif t == "plate_hold":
        out += [{"kind": "place", "item": i} for i in LOCAL + ["grey_stone"]] + [{"kind": "step_on"}]
    elif t == "timed_gate":
        out += [{"kind": "pull"}, {"kind": "step"}, {"kind": "pass"}]
    elif t == "magic_target":
        out += [{"kind": "cast", "spell": s} for s in (0, 1, 6)]
    elif t == "two_levers":
        out += [{"kind": "pull", "index": i} for i in range(2)]
    return out


def start_inventory(p):
    inv = list(p.get("items", []))
    if p["type"] == "offerings":
        inv.append(p["slots"][1]["item"])  # the imported sigil the miner gave
    return tuple(sorted(inv))


def key(st, inv):
    st = dict(st, **({"wrong_pulls": min(2, st["wrong_pulls"])} if "wrong_pulls" in st else {}))  # a pure counter: cap it so the state space closes
    return json.dumps(st, sort_keys=True) + "|" + ",".join(inv)


def explore(p, max_states=4000):
    st0, inv0 = logic.fresh_state(p), start_inventory(p)
    seen = {key(st0, inv0): (st0, inv0)}
    edges = {}
    frontier = [(st0, inv0)]
    acts = actions_for(p)
    while frontier and len(seen) < max_states:
        nxt = []
        for st, inv in frontier:
            k = key(st, inv)
            edges[k] = []
            for a in acts:
                s2 = json.loads(json.dumps(st))
                ctx = {"items": list(inv), "spells": [0, 1, 6]}
                r = logic.act(p, s2, a, ctx)
                inv2 = list(inv)
                for c in r["consume"]:
                    if c in inv2:
                        inv2.remove(c)
                if r["grant"]:
                    inv2.append(r["grant"])
                k2 = key(s2, tuple(sorted(inv2)))
                edges[k].append(k2)
                if k2 not in seen:
                    seen[k2] = (s2, tuple(sorted(inv2)))
                    nxt.append(seen[k2])
        frontier = nxt
    return seen, edges


@pytest.mark.parametrize("seed", range(1, 25))
def test_every_reachable_state_can_still_be_solved(seed):
    d = {"id": f"c{seed}", "kind": "cave", "faction": "Red", "seed": seed * 31 + 5, "needs": {"item": "sigil_ash", "from": "settlement"}}
    for p in gen.generate(d):
        seen, edges = explore(p)
        assert len(seen) < 4000, (p["type"], "state space did not close")
        solved = {k for k, (st, _inv) in seen.items() if st.get("solved")}
        assert solved, p["type"]  # reachable at all
        # backward reachability: every explored state must reach a solved state
        can = set(solved)
        changed = True
        while changed:
            changed = False
            for k, outs in edges.items():
                if k not in can and any(o in can for o in outs):
                    can.add(k)
                    changed = True
        dead = [k for k in seen if k not in can and k in edges]
        assert not dead, (p["type"], len(dead), dead[:2])
