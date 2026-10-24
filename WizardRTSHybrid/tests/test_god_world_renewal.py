"""Renewal and history (docs/PLAN_GOD_WORLD_PANDEMIC.md stage 1; the brief's P01 to P04): the productive number tokens are reshuffled at every age
boundary with their own stream under the keep-apart rule, roles and the graph never move, the revision invalidates the layouts, a save made before
the boundary replays to the same tokens, and retired villages keep their actual built picture, produce nothing, and are built over by a new
settlement on the node without ever showing two hubs."""

from __future__ import annotations

import json
import random

from wizard_rts.god_world import ages, local_ops, rules, snapshot
from wizard_rts.god_world.board import GodBoard
from wizard_rts.god_world.world import GodWorld


def _running(seed=0, ops=False):
    w = GodWorld(seed=seed, map_name="Egyptian_Mandala_v1.2" if ops else None)
    w.local_ops_enabled = ops
    seq = [0]

    def step(ms=1000):
        seq[0] += 1
        w.advance(ms, seq[0], snapshot=False)

    while w.phase == "SETUP":
        step()
    return w, step


def _keep_apart_ok(board):
    keep = {int(t) for t in rules.board_spec().get("keep_apart", [])}
    for h in board.hexes:
        if board.roles[h] == rules.DESERT:
            continue
        if board.tokens[h] in keep and any(board.tokens.get(o) in keep for o in board.hex_neighbours(h)):
            return False
    return True


def test_p01_reshuffle_keeps_the_multiset_roles_graph_and_keep_apart_and_uses_its_own_stream():
    board = GodBoard.generate(3)
    roles = dict(board.roles)
    nodes = sorted(board.nodes)
    edges = sorted(board.edges)
    before = sorted(board.tokens[h] for h in board.hexes if board.roles[h] != rules.DESERT)
    rng = random.Random(99)
    tx = board.reshuffle_tokens(rng)
    after = sorted(board.tokens[h] for h in board.hexes if board.roles[h] != rules.DESERT)
    assert before == after
    assert board.roles == roles and sorted(board.nodes) == nodes and sorted(board.edges) == edges
    assert _keep_apart_ok(board)
    assert tx["before"] != tx["after"]
    assert sum(1 for h in tx["before"] if tx["before"][h] != tx["after"][h]) >= 10
    # dedicated stream: the same seed gives the same shuffle, the dice stream is untouched
    b2 = GodBoard.generate(3)
    tx2 = b2.reshuffle_tokens(random.Random(99))
    assert tx2["after"] == tx["after"]


def test_p02_the_boundary_reshuffles_once_after_the_ranking_and_bumps_the_revision():
    w, step = _running(0)
    tokens0 = dict(w.board.tokens)
    f = w.fids[0]
    assert w.production_revision == 1
    # the ranking that selects the carried villages uses the old tokens: pips before the trigger
    ranked_before = ages.rank_villages(w, f)
    ages.trigger(w, f, {"kind": "test", "faction": f})
    tr = w.transition
    assert tr["tokens_before"] == {h: tokens0[h] for h in tokens0 if w.board.roles[h] != rules.DESERT}
    assert tr["tokens_after"] == {h: w.board.tokens[h] for h in w.board.tokens if w.board.roles[h] != rules.DESERT}
    assert tr["production_revision"] == 2 and w.production_revision == 2
    assert [c["village"] for c in ranked_before][:2] == list(tr["selected"][f])
    assert _keep_apart_ok(w.board)
    assert sorted(tokens0.values()) == sorted(w.board.tokens.values())
    while w.phase != "RUNNING":
        step()
    # the new age's capacities come from the new tokens
    for v in w.villages.values():
        if v["status"] == "operational":
            caps = local_ops.init_dev(w, v)
            for hid, rec in caps.items():
                assert rec["cap"] == rules.pips(w.board.tokens[hid]) * max(1, int(v["level"]))
                assert rec["revision"] == 2


def test_p03_a_save_before_the_boundary_replays_to_the_same_tokens():
    w, step = _running(1)
    saved = json.loads(json.dumps(w.to_dict()))
    f = w.fids[1]
    ages.trigger(w, f, {"kind": "test", "faction": f})
    w2 = GodWorld.from_dict(saved)
    ages.trigger(w2, f, {"kind": "test", "faction": f})
    assert w2.board.tokens == w.board.tokens
    assert w2.transition["tokens_after"] == w.transition["tokens_after"]
    # and a save made after the boundary keeps them
    w3 = GodWorld.from_dict(json.loads(json.dumps(w.to_dict())))
    assert w3.board.tokens == w.board.tokens and w3.production_revision == 2


def test_p04_retired_villages_keep_their_built_picture_produce_nothing_and_are_built_over_without_two_hubs():
    w, step = _running(0, ops=True)
    # let the villages build for a while, then force the boundary
    for _ in range(240):
        step()
    f = w.fids[0]
    # a third village for the faction (placed directly: the test is about history, not founding), so the boundary retires one
    free = next(n for n in sorted(w.board.nodes) if w.node_free(n) and w.board.node_hexes[n])
    extra = f"v{len(w.villages) + 1}"
    w.villages[extra] = {"id": extra, "node": free, "faction": f, "level": 1, "status": "operational", "age": int(w.age), "name": "Thirdtown", "founded_ms": int(w.game_ms), "units": [], "history": []}
    local_ops.complete_all(w, w.villages[extra])
    for _ in range(20):
        step()
    built_before = {vid: [s["id"] for s in v["ops"]["sites"].values() if local_ops.built(s)] for vid, v in w.villages.items() if v.get("ops")}
    assert any(built_before.values())
    ages.trigger(w, f, {"kind": "test", "faction": f})
    retired = [w.villages[vid] for vid in w.transition["retired"]]
    assert retired
    for v in retired:
        assert v["status"] == "historical" and "ops" not in v
        fz = v["frozen"]
        assert {s["id"] for s in fz["sites"]} == set(built_before[v["id"]])
        assert sum(1 for s in fz["sites"] if s["kind"] == "hub") <= 1
    while w.phase != "RUNNING":
        step()
    snap_before = snapshot.snapshot(w)
    frozen_rows = [r for r in snap_before["villages"] if r["status"] == "historical" and r.get("frozen")]
    assert frozen_rows
    # no strategic effect: a historical village's hand, roads and claims count for nothing
    for v in retired:
        assert all(world_claim != v["id"] for world_claim in w.tree_claims.values())
    # step on: frozen pictures never change
    pics = {v["id"]: json.dumps(v["frozen"], sort_keys=True) for v in retired}
    for _ in range(60):
        step()
    for v in retired:
        assert json.dumps(v["frozen"], sort_keys=True) == pics[v["id"]]
    # build over: found a new settlement on a retired node and the frozen hub is superseded; never two hubs in the picture
    target = retired[0]
    fid = target["faction"]
    # give the faction the means and place the settlement directly (the test is about the picture, not the rules of founding)
    nid = target["node"]
    for other in list(w.villages.values()):
        if other["node"] == nid and other["status"] != "historical":
            other["status"] = "historical"
    new_id = f"v{len(w.villages) + 1}"
    w.villages[new_id] = {"id": new_id, "node": nid, "faction": fid, "level": 1, "status": "operational", "age": int(w.age), "name": "Newtown", "founded_ms": int(w.game_ms), "units": [], "history": []}
    local_ops.ensure(w, w.villages[new_id])
    fz = target["frozen"]
    assert all(s["superseded"] for s in fz["sites"] if s["kind"] == "hub")
    snap = snapshot.snapshot(w)
    row = next(r for r in snap["villages"] if r["id"] == target["id"])
    assert not any(s["kind"] == "hub" for s in row.get("frozen", {}).get("sites", []))
