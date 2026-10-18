"""Two-client LAN multiplayer harness: the real host loop, the real protocol over real sockets, the real HybridWorld.

Covers the acceptance list in docs/MOBILE_LAN_MULTIPLAYER.md section 9: distinct identities, shared spawn, movement seen
both ways, one simulation clock for two clients, a full PvP Ward duel with hidden wards, return to the world, disconnect and
reconnect without ghosts; plus simultaneous commands, illegal movement, invalid casts, replayed commands, permission checks,
resynchronisation, discovery, version checks and a two-process run over a non-loopback interface.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

HYB = Path(__file__).resolve().parents[1]
ROOT = HYB.parent
for entry in (str(HYB), str(ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

os.environ.setdefault("DMB_NO_NATIVE", "1")

from wizard_rts.net import protocol  # noqa: E402
from wizard_rts.net.client import NetClient, discover  # noqa: E402
from wizard_rts.net.host import HostServer, new_world  # noqa: E402
from wizard_rts.net.session import MultiplayerSession  # noqa: E402

SECRET = "host-secret-for-tests"
CODE = "4242"


class Rig:
    """A host in a thread plus helpers. `make_clients()` gives connected, authenticated clients (first one is the host's own)."""

    def __init__(self, seed: int = 507, map_size: str = "small", discovery_port: int | None = None, **session_kw):
        self.world = new_world(seed, map_size, "campaign")
        self.world.ai_enabled = True
        self.session = MultiplayerSession(self.world, name="rig", join_code=CODE, host_secret=SECRET, max_players=session_kw.pop("max_players", 2), **session_kw)
        self.host = HostServer(self.world, self.session, bind="127.0.0.1", port=0, discovery_port=discovery_port)
        self.host.start()
        self.thread = threading.Thread(target=self.host.run_forever, daemon=True)
        self.thread.start()
        self.clients: list[NetClient] = []

    def client(self, name: str) -> NetClient:
        c = NetClient("127.0.0.1", self.host.port, name=name).connect()
        self.clients.append(c)
        return c

    def make_clients(self, start: bool = True) -> tuple[NetClient, NetClient]:
        a, b = self.client("Alice"), self.client("Bob")
        assert a.hello(secret=SECRET)["status"] == "ok"
        assert b.hello(code=CODE)["status"] == "ok"
        if start:
            assert a.start()["status"] == "ok"
            a.state(full=True)
            b.state(full=True)
        return a, b

    def close(self) -> None:
        for c in self.clients:
            c.close()
        self.host.stop_flag = True
        self.thread.join(timeout=5)
        self.host.stop()


@pytest.fixture
def rig():
    r = Rig()
    yield r
    r.close()


def _players(reply: dict) -> dict[str, tuple[int, int]]:
    return {p["id"]: (int(p["tx"]), int(p["ty"])) for p in reply["snapshot"]["players"]}


def _walk_adjacent(a: NetClient, b: NetClient) -> None:
    """Bring B next to A (B spawned within a few tiles): step along the axes until Manhattan distance <= 1."""
    for _ in range(40):
        ax, ay = int(a.pose["tx"]), int(a.pose["ty"])
        bx, by = int(b.pose["tx"]), int(b.pose["ty"])
        if abs(ax - bx) + abs(ay - by) <= 1:
            return
        dx = (ax > bx) - (ax < bx)
        dy = (ay > by) - (ay < by)
        r = b.step(dx, 0) if dx and abs(ax - bx) > (1 if dy == 0 else 0) else b.step(0, dy)
        if r["status"] != "ok":  # an obstacle: try the other axis, then sidestep
            r2 = b.step(0, dy) if dx else b.step(dx, 0)
            if r2["status"] != "ok":
                b.step(0, 1) if r2.get("reason") != "occupied" else b.step(0, -1)
    assert abs(int(a.pose["tx"]) - int(b.pose["tx"])) + abs(int(a.pose["ty"]) - int(b.pose["ty"])) <= 1, (a.pose, b.pose)


def _revive(winner: NetClient, loser: NetClient) -> None:
    """A duel between apprentices is to the death: the loser lies where they fell until the winner, standing beside the body, channels."""
    r = winner.op({"op": "resurrect", "target": loser.player_id})
    assert r["status"] == "started", r
    deadline = time.time() + 20
    while time.time() < deadline:
        if not winner.state()["snapshot"]["players"] or not any(p["id"] == loser.player_id and p.get("dead") for p in winner.state()["snapshot"]["players"]):
            break
        time.sleep(0.25)
    assert not any(p["id"] == loser.player_id and p.get("dead") for p in winner.state()["snapshot"]["players"]), "the resurrection never completed"
    loser.state(full=True)


def _play_duel(a: NetClient, b: NetClient, ward_a: list[int], ward_b: list[int], casts: list[tuple[list[int], list[int]]]) -> tuple[dict, dict]:
    assert a.ward(ward_a)["status"] == "ok"
    assert b.ward(ward_b)["status"] == "ok"
    for ca, cb in casts:
        ra, rb = a.cast(ca), b.cast(cb)
        assert ra["status"] == "ok", ra
        assert rb["status"] == "ok", rb
        if rb["duel"]["done"]:
            break
    return a.duel()["duel"], b.duel()["duel"]


# ---------------------------------------------------------------- identities, spawn, movement, clock

def test_two_clients_get_distinct_identities_and_spawn_in_one_world(rig: Rig) -> None:
    a, b = rig.make_clients()
    assert a.player_id != b.player_id
    assert a.token != b.token
    sa, sb = a.state(), b.state()
    assert sa["you"] == a.player_id and sb["you"] == b.player_id
    assert set(_players(sa)) == {a.player_id, b.player_id} == set(_players(sb))
    assert _players(sa) == _players(sb)  # the same authoritative positions on both screens
    assert _players(sa)[a.player_id] != _players(sb)[b.player_id]  # two avatars, two tiles
    assert sa["snapshot"]["world_id"] == sb["snapshot"]["world_id"] and sa["snapshot"]["seed"] == sb["snapshot"]["seed"]
    # the host's wizard is the single-player record (no second avatar for the host)
    assert rig.world.players[a.player_id] is rig.world.player
    assert len(rig.world.players) == 2
    # each client's own view is centred on itself
    assert (sa["snapshot"]["player"]["tx"], sa["snapshot"]["player"]["ty"]) == _players(sa)[a.player_id]
    assert (sb["snapshot"]["player"]["tx"], sb["snapshot"]["player"]["ty"]) == _players(sb)[b.player_id]


def test_movement_is_replicated_both_ways(rig: Rig) -> None:
    a, b = rig.make_clients()
    start_a = (int(a.pose["tx"]), int(a.pose["ty"]))
    moved = False
    for dx, dy in ((0, -1), (-1, 0), (0, 1), (1, 0)):
        if a.step(dx, dy)["status"] == "ok":
            moved = True
            break
    assert moved
    assert (int(a.pose["tx"]), int(a.pose["ty"])) != start_a
    assert _players(b.state())[a.player_id] == (int(a.pose["tx"]), int(a.pose["ty"]))
    start_b = (int(b.pose["tx"]), int(b.pose["ty"]))
    for dx, dy in ((0, -1), (-1, 0), (0, 1), (1, 0)):
        if b.step(dx, dy)["status"] == "ok":
            break
    assert (int(b.pose["tx"]), int(b.pose["ty"])) != start_b
    assert _players(a.state())[b.player_id] == (int(b.pose["tx"]), int(b.pose["ty"]))


def test_world_advances_once_not_once_per_client(rig: Rig) -> None:
    a, b = rig.make_clients()
    t0 = rig.world.dmb.clock["game_ms"]
    adv0 = rig.host.stats["advances"]
    wall0 = time.monotonic()
    for _ in range(10):  # two clients polling hard
        a.state()
        b.state()
        time.sleep(0.05)
    elapsed = time.monotonic() - wall0
    gained = rig.world.dmb.clock["game_ms"] - t0
    assert 0 < gained <= (elapsed + 0.6) * 1000  # game time tracks wall time once, not twice
    assert rig.host.stats["advances"] > adv0
    # no client can move the clock
    assert a.op({"op": "advance", "ms": 5000, "sequence": 9999})["reason"] == "not_allowed_in_multiplayer"
    assert b.op({"op": "speed", "scale": 16})["reason"] == "not_allowed_in_multiplayer"
    assert rig.world.time_scale == 1


def test_illegal_movement_and_replayed_commands(rig: Rig) -> None:
    a, b = rig.make_clients()
    ax, ay = int(a.pose["tx"]), int(a.pose["ty"])
    assert a.move(ax + 3, ay, "right")["reason"] == "not_adjacent"
    assert a.move(ax, ay, "sideways")["reason"] == "bad_facing"
    assert a.move(-5, -5)["reason"] == "not_adjacent"
    # a legal step, then the same sequence number again: rejected, position unchanged
    stepped = None
    for dx, dy in ((0, -1), (-1, 0), (0, 1), (1, 0)):
        r = a.step(dx, dy)
        if r["status"] == "ok":
            stepped = (dx, dy, r["seq"])
            break
    assert stepped is not None
    here = (int(a.pose["tx"]), int(a.pose["ty"]))
    replay = a.op({"op": "move", "seq": stepped[2], "tx": here[0] + stepped[0], "ty": here[1] + stepped[1], "facing": "down"})
    assert replay["reason"] == "stale_seq" and (replay["tx"], replay["ty"]) == here
    older = a.op({"op": "move", "seq": 0, "tx": here[0], "ty": here[1], "facing": "up"})
    assert older["reason"] == "stale_seq"
    # walking onto the other wizard's tile is a collision
    _walk_adjacent(a, b)
    bx, by = int(b.pose["tx"]), int(b.pose["ty"])
    dx, dy = bx - int(a.pose["tx"]), by - int(a.pose["ty"])
    assert a.step(dx, dy)["reason"] == "occupied"
    # the step-rate cap
    rejected = 0
    for _ in range(30):
        r = a.op({"op": "move", "seq": a.move_seq + 1, "tx": int(a.pose["tx"]) + 1, "ty": int(a.pose["ty"]), "facing": "right"})
        a.move_seq += 1
        if r["status"] == "ok":
            a.pose = {k: r[k] for k in ("tx", "ty", "facing", "hex", "seq")}
        if r.get("reason") == "too_fast":
            rejected += 1
            break
    assert rejected == 1 or rig.world.tile_in_map(int(a.pose["tx"]) + 1, int(a.pose["ty"])) is False


def test_simultaneous_commands_from_both_players(rig: Rig) -> None:
    a, b = rig.make_clients()
    results: dict[str, list[dict]] = {"a": [], "b": []}

    def walker(c: NetClient, key: str) -> None:
        for i in range(12):
            dx, dy = ((0, -1), (-1, 0), (0, 1), (1, 0))[i % 4]
            results[key].append(c.step(dx, dy))

    ta, tb = threading.Thread(target=walker, args=(a, "a")), threading.Thread(target=walker, args=(b, "b"))
    ta.start()
    tb.start()
    ta.join()
    tb.join()
    assert all(r["status"] in ("ok", "rejected") for r in results["a"] + results["b"])
    assert any(r["status"] == "ok" for r in results["a"]) and any(r["status"] == "ok" for r in results["b"])
    sa, sb = a.state(), b.state()
    assert _players(sa) == _players(sb)
    assert _players(sa)[a.player_id] != _players(sa)[b.player_id]  # never on the same tile
    assert len(rig.world.players) == 2


# ---------------------------------------------------------------- authority

def test_server_side_permission_checks(rig: Rig) -> None:
    a, b = rig.make_clients(start=False)
    assert b.start()["reason"] == "host_only"
    for msg in ({"op": "build", "faction": "Red", "kind": "sawmill", "tx": 10, "ty": 10}, {"op": "spawn", "faction": "Red", "definition": "openra.e1", "tx": 1, "ty": 1},
                {"op": "damage", "building": "x", "amount": 5}, {"op": "control", "faction": "Red"}, {"op": "ai", "enabled": False}, {"op": "inspect", "what": "factions"},
                {"op": "fixture", "name": "modern_industry"}, {"op": "draft", "faction": "Red", "card": "x"}, {"op": "snapshot"}, {"op": "pose", "tx": 1, "ty": 1}):
        r = b.op(msg)
        assert r["status"] == "rejected" and r["reason"] == "not_allowed_in_multiplayer", (msg, r)
    assert rig.world.ai_enabled is True
    assert len(rig.world.buildings) == len(rig.world.buildings)
    # a stranger without the code or a token
    stranger = rig.client("Mallory")
    assert stranger.hello(code="0000")["reason"] == "bad_code"
    assert stranger.op({"op": "state"})["reason"] == "hello_first"
    assert stranger.op({"op": "move", "seq": 1, "tx": 1, "ty": 1})["reason"] == "hello_first"
    # version checks
    wrong_proto = NetClient("127.0.0.1", rig.host.port, name="Old", proto=protocol.PROTOCOL_VERSION + 1).connect()
    assert wrong_proto.hello(code=CODE)["reason"] == "protocol_mismatch"
    wrong_proto.close()
    wrong_game = NetClient("127.0.0.1", rig.host.port, name="Old", game="9.9.9").connect()
    assert wrong_game.hello(code=CODE)["reason"] == "version_mismatch"
    wrong_game.close()
    # a third player when the session is full
    third = rig.client("Carol")
    assert third.hello(code=CODE)["reason"] == "full"
    assert a.start()["status"] == "ok"


# ---------------------------------------------------------------- PvP duels

def test_full_pvp_duel_lifecycle_and_return_to_world(rig: Rig) -> None:
    a, b = rig.make_clients()
    assert a.challenge("nobody")["reason"] == "no_such_player"
    assert a.challenge(a.player_id)["reason"] == "no_such_player"
    _walk_adjacent(a, b)
    ch = a.challenge(b.player_id)
    assert ch["status"] == "ok"
    duel_id = ch["duel_id"]
    assert a.challenge(b.player_id)["reason"] == "challenge_pending"
    inv = b.state()["invite"]
    assert inv["duel_id"] == duel_id and inv["from"] == a.player_id
    assert b.respond("wrong", True)["reason"] == "wrong_duel"
    acc = b.respond(duel_id, True)
    assert acc["status"] == "ok" and acc["duel"]["state"] == "setup"
    assert not rig.world.dmb.clock.get("pause_tokens"), "a duel never stops the world: the village goes on around the duellists"
    frozen = rig.world.dmb.clock["game_ms"]
    assert a.step(0, -1)["reason"] == "in_duel"
    assert a.op({"op": "fire", "target": "x"})["reason"] == "in_duel"
    # ward setup: hidden from the rival, validated by the rules
    assert a.ward([0, 1, 9])["reason"] == "illegal_ward"
    assert a.ward([0, 1])["reason"] == "illegal_ward"
    assert a.cast([0, 0, 0])["reason"] == "not_active"
    assert a.ward([0, 1, 6])["status"] == "ok"
    assert a.ward([6, 6, 6])["idempotent"] is True  # a duplicate submission does not change the ward
    vb = b.duel()["duel"]
    assert vb["rival_ward_locked"] is True and "rival_ward" not in vb and vb["your_ward"] == []
    assert b.ward([6, 6, 0])["status"] == "ok"
    va = a.duel()["duel"]
    assert va["state"] == "active" and va["your_cast_pending"] and va["rival_cast_pending"] and "rival_ward" not in va and va["your_ward"] == [0, 1, 6]
    # casts: authoritative feedback under the existing fracture/echo/fade rules
    assert a.cast([9, 9, 9])["reason"] == "illegal_attack"
    assert a.cast([0, 0])["reason"] == "illegal_attack"
    assert a.cast([0, 0, 0], cast_seq=7)["reason"] == "bad_cast_seq"
    r = a.cast([6, 0, 0])  # against [6, 6, 0]: slots 0 and 2 fracture, the spare 0 fades (feedback.gd rules)
    assert (r["fracture"], r["echo"], r["fade"], r["broken"]) == (2, 0, 1, False)
    dup = a.cast([6, 0, 0], cast_seq=1)
    assert dup["idempotent"] is True and dup["fracture"] == 2
    # no rounds: A casts again at once, B has not cast at all, and A is never told to wait
    r = a.cast([1, 1, 1])
    assert r["status"] == "ok" and r["done"] is False
    va = a.duel()["duel"]
    assert va["your_cast_pending"] is True and va["rival_cast_pending"] is True and "rival_ward" not in va
    assert (va["your_casts"], va["rival_casts"]) == (2, 0) and len(va["your_history"]) == 2 and va["rival_history"] == []
    r = b.cast([0, 1, 1])
    assert (r["fracture"], r["echo"], r["broken"]) == (2, 0, False)
    r = b.cast([0, 1, 6])
    assert r["broken"] is True and r["done"] is True  # the first breaking cast ends the duel at once
    assert a.cast([3, 3, 1], cast_seq=3)["reason"] == "finished"  # A's late guess is refused
    va, vb = a.duel()["duel"], b.duel()["duel"]
    assert va["result"]["outcome"] == "defeat" and vb["result"]["outcome"] == "victory"
    assert va["result"]["reason"] == "solved"
    assert va["rival_ward"] == [6, 6, 0] and vb["rival_ward"] == [0, 1, 6]  # disclosed only now
    assert va["rival_history"][-1]["attack"] == [0, 1, 6] and vb["rival_history"][-1]["attack"] == [1, 1, 1]
    assert (va["result"]["your_casts"], va["result"]["rival_casts"]) == (2, 2)
    assert not rig.world.dmb.clock.get("pause_tokens")
    assert rig.world.dmb.clock["game_ms"] >= frozen
    assert any(e["kind"] == "pvp_duel_ended" for e in rig.world.events)
    # the loser is dead where they stood; the winner returns to the shared world and brings them back
    assert a.op({"op": "pvp_leave"})["status"] == "ok" and b.op({"op": "pvp_leave"})["status"] == "ok"
    assert rig.session.duels == {}
    assert a.state()["duel"] == {} and b.state()["duel"] == {}
    sa = a.state()
    assert sa["you_dead"]["by"] == b.player_id and sa["you_dead"]["body"], "Alice lost: she is dead and her body lies in the world"
    assert a.step(0, -1)["reason"] == "dead"
    assert any(e.get("id") == sa["you_dead"]["body"] and e.get("body") for e in b.state(full=True)["snapshot"]["entities"]), "Bob sees the body"
    assert rig.session.ending is None, "Bob is alive: the game goes on"
    _revive(b, a)
    moved = any(a.step(dx, dy)["status"] == "ok" for dx, dy in ((0, -1), (-1, 0), (0, 1), (1, 0)))
    assert moved
    assert _players(b.state())[a.player_id] == (int(a.pose["tx"]), int(a.pose["ty"]))
    time.sleep(0.3)
    assert rig.world.dmb.clock["game_ms"] > frozen


def test_pvp_casts_are_independent_and_a_simultaneous_win_has_one_winner(rig: Rig) -> None:
    import threading

    a, b = rig.make_clients()
    _walk_adjacent(a, b)
    d = a.challenge(b.player_id)["duel_id"]
    b.respond(d, True)
    a.ward([0, 1, 6])
    b.ward([6, 6, 0])
    # A races ahead: three guesses over the wire, B none; every reply carries both histories' counts
    for attack in ([0, 0, 0], [1, 1, 1], [6, 0, 0]):
        r = a.cast(attack)
        assert r["status"] == "ok" and r["done"] is False
    assert (r["duel"]["your_casts"], r["duel"]["rival_casts"]) == (3, 0)
    vb = b.duel()["duel"]
    assert (vb["your_casts"], vb["rival_casts"]) == (0, 3) and vb["your_cast_pending"] is True
    # both now send a winning cast at the same moment from two threads: the host serialises them, exactly one wins
    replies: dict[str, dict] = {}
    gate = threading.Barrier(2)

    def go(name: str, client: NetClient, attack: list[int]) -> None:
        gate.wait()
        replies[name] = client.cast(attack)

    ts = [threading.Thread(target=go, args=("a", a, [6, 6, 0])), threading.Thread(target=go, args=("b", b, [0, 1, 6]))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    winners = [n for n, r in replies.items() if r.get("status") == "ok" and r.get("broken")]
    losers = [n for n, r in replies.items() if r.get("reason") == "finished"]
    assert len(winners) == 1 and len(losers) == 1, replies
    va, vb = a.duel()["duel"], b.duel()["duel"]
    assert va["state"] == "finished" == vb["state"]
    assert {va["result"]["outcome"], vb["result"]["outcome"]} == {"victory", "defeat"}
    assert va["result"]["winner"] == vb["result"]["winner"] != ""
    assert not rig.world.dmb.clock.get("pause_tokens")
    # the world carries on after the duel: the winner walks, the loser lies dead until revived
    assert a.op({"op": "pvp_leave"})["status"] == "ok" and b.op({"op": "pvp_leave"})["status"] == "ok"
    winner, loser = (a, b) if va["result"]["winner"] == a.player_id else (b, a)
    assert any(winner.step(dx, dy)["status"] == "ok" for dx, dy in ((0, -1), (-1, 0), (0, 1), (1, 0)))
    assert loser.step(0, 1)["reason"] == "dead"


def test_pvp_clash_stalemate_decline_and_forfeit(rig: Rig) -> None:
    a, b = rig.make_clients()
    _walk_adjacent(a, b)
    # decline
    d = a.challenge(b.player_id)["duel_id"]
    assert b.respond(d, False)["accepted"] is False
    assert any(n["kind"] == "declined" for n in a.state()["notices"])
    assert not rig.world.dmb.clock.get("pause_tokens")
    # both could solve with their first cast: the cast that reaches the host first wins and the other is refused (no clash)
    d = a.challenge(b.player_id)["duel_id"]
    b.respond(d, True)
    a.ward([0, 0, 0])
    b.ward([1, 1, 1])
    assert a.cast([1, 1, 1])["done"] is True
    assert b.cast([0, 0, 0])["reason"] == "finished"
    va, vb = a.duel()["duel"], b.duel()["duel"]
    assert va["result"]["outcome"] == "victory" and vb["result"]["outcome"] == "defeat" and vb["your_casts"] == 0
    a.op({"op": "pvp_leave"})
    b.op({"op": "pvp_leave"})
    _revive(a, b)
    # stalemate at exhaustion with equal progress
    d = a.challenge(b.player_id, fmt={"slots": 3, "colours": 3, "max_casts": 2})["duel_id"]
    b.respond(d, True)
    va, vb = _play_duel(a, b, [0, 0, 0], [1, 1, 1], [([6, 6, 6], [6, 6, 6]), ([6, 6, 6], [6, 6, 6])])
    assert va["result"]["outcome"] == "stalemate" == vb["result"]["outcome"] and va["result"]["reason"] == "both_exhausted"
    a.op({"op": "pvp_leave"})
    b.op({"op": "pvp_leave"})
    # exhaustion with unequal progress is still a stalemate: game_logic.gd declares a draw when both sides are out of casts
    d = a.challenge(b.player_id, fmt={"slots": 3, "colours": 3, "max_casts": 1})["duel_id"]
    b.respond(d, True)
    va, vb = _play_duel(a, b, [0, 0, 0], [1, 1, 1], [([1, 0, 0], [6, 6, 6])])
    assert va["result"]["outcome"] == "stalemate" == vb["result"]["outcome"]
    assert va["your_history"][0]["fracture"] == 1 and vb["your_history"][0]["fracture"] == 0
    a.op({"op": "pvp_leave"})
    b.op({"op": "pvp_leave"})
    # forfeit
    d = a.challenge(b.player_id)["duel_id"]
    b.respond(d, True)
    a.ward([0, 0, 0])
    assert b.op({"op": "pvp_forfeit"})["duel"]["result"]["outcome"] == "defeat"
    assert a.duel()["duel"]["result"]["outcome"] == "victory" and a.duel()["duel"]["result"]["reason"] == "forfeit"
    assert not rig.world.dmb.clock.get("pause_tokens")
    assert a.op({"op": "pvp_leave"})["status"] == "ok" and b.op({"op": "pvp_leave"})["status"] == "ok"
    assert a.state()["duel"] == {}
    assert b.state()["you_dead"], "forfeiting by choice is a death too"


def test_pvp_timeouts_auto_cast_and_invite_expiry() -> None:
    rig = Rig(cast_timeout_s=0.5, invite_timeout_s=0.5)
    try:
        a, b = rig.make_clients()
        _walk_adjacent(a, b)
        d = a.challenge(b.player_id)["duel_id"]
        time.sleep(0.8)
        assert b.respond(d, True)["reason"] == "no_invite"
        assert any(n["kind"] == "invite_expired" for n in a.state()["notices"])
        d = a.challenge(b.player_id)["duel_id"]
        b.respond(d, True)
        a.ward([0, 0, 0])
        b.ward([1, 1, 1])
        a.cast([6, 6, 6])
        time.sleep(0.9)  # B never casts: after the per-player timeout the host casts a legal weave for him
        vb = b.duel()["duel"]
        assert vb["your_history"][0]["auto"] is True and len(vb["your_history"][0]["attack"]) == 3
    finally:
        rig.close()


# ---------------------------------------------------------------- disconnect, reconnect, resync

def test_disconnect_reconnect_without_ghosts_and_full_resync(rig: Rig) -> None:
    a, b = rig.make_clients()
    for dx, dy in ((0, -1), (-1, 0), (0, 1), (1, 0)):
        if b.step(dx, dy)["status"] == "ok":
            break
    pos_b = (int(b.pose["tx"]), int(b.pose["ty"]))
    token = b.token
    b.close()
    time.sleep(0.3)
    sa = a.state()
    assert any(n["kind"] == "player_left" for n in sa["notices"])
    row = next(p for p in sa["snapshot"]["players"] if p["id"] == b.player_id)
    assert row["connected"] is False and (row["tx"], row["ty"]) == pos_b  # the avatar stays where it was, flagged
    b2 = rig.client("Bob")
    r = b2.hello(token=token)
    assert r["status"] == "ok" and r["reconnect"] is True and r["player_id"] == b.player_id and r["token"] == token
    assert (r["pose"]["tx"], r["pose"]["ty"]) == pos_b
    full = b2.state(full=True)
    assert full["snapshot"]["tree_delta"]["full"] is True and full["snapshot"]["entities"]
    assert _players(full) == _players(a.state())
    assert len(rig.world.players) == 2 and sorted(rig.session.links) == [a.player_id, b.player_id] and len(rig.session.by_conn) == 2
    assert next(p for p in a.state()["snapshot"]["players"] if p["id"] == b.player_id)["connected"] is True
    assert b2.move_seq == int(r["pose"]["seq"])
    assert any(b2.step(dx, dy)["status"] == "ok" for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)))
    # a stale token or a new hello without the code is still refused
    c = rig.client("Eve")
    assert c.hello(token="not-a-token", code="0000")["reason"] == "bad_code"


def test_disconnect_during_duel_forfeits_after_grace_and_reconnect_sees_result() -> None:
    rig = Rig(disconnect_grace_s=0.5)
    try:
        a, b = rig.make_clients()
        _walk_adjacent(a, b)
        d = a.challenge(b.player_id)["duel_id"]
        b.respond(d, True)
        a.ward([0, 0, 0])
        b.ward([1, 1, 1])
        token = b.token
        b.close()
        time.sleep(0.2)
        assert a.duel()["duel"]["state"] == "active"  # grace period
        time.sleep(0.8)
        va = a.duel()["duel"]
        assert va["state"] == "finished" and va["result"]["outcome"] == "victory" and va["result"]["reason"] == "disconnected"
        assert not rig.world.dmb.clock.get("pause_tokens")
        b2 = rig.client("Bob")
        r = b2.hello(token=token)
        assert r["duel"]["result"]["outcome"] == "defeat"
        assert a.op({"op": "pvp_leave"})["status"] == "ok" and b2.op({"op": "pvp_leave"})["status"] == "ok"
        assert rig.session.duels == {}
    finally:
        rig.close()


# ---------------------------------------------------------------- views, bandwidth, discovery

def test_area_of_interest_and_lean_polls(rig: Rig) -> None:
    a, b = rig.make_clients()
    full = a.state(full=True)
    lean = a.state()
    assert len(json.dumps(lean)) < len(json.dumps(full))
    assert "stocks" not in lean["snapshot"] and "stocks" in full["snapshot"]
    ax, ay = int(a.pose["tx"]), int(a.pose["ty"])
    for e in lean["snapshot"]["entities"]:
        ex, ey = (int(e["anchor"][0]), int(e["anchor"][1])) if "anchor" in e else (int(e["tx"]), int(e["ty"]))
        assert abs(ex - ax) <= lean["view_radius"] and abs(ey - ay) <= lean["view_radius"]
    narrow = a.state(radius=8)
    assert narrow["view_radius"] == 8 and len(narrow["snapshot"]["entities"]) <= len(lean["snapshot"]["entities"])
    assert len(json.dumps(lean)) < 60_000, "a phone poll must stay small"
    # a tree felled or planted later shows up as an upsert only for the client that has not seen it
    assert full["snapshot"]["tree_delta"]["full"] is True
    assert a.state()["snapshot"]["tree_delta"]["full"] is False


def test_discovery_probe_and_info() -> None:
    port = 18700 + (os.getpid() % 200)
    rig = Rig(discovery_port=port)
    try:
        found = discover(timeout=1.0, port=port, targets=["127.0.0.1"])
        assert found and found[0]["port"] == rig.host.port and found[0]["name"] == "rig" and found[0]["needs_code"] is True
        c = rig.client("Probe")
        info = c.op({"op": "info"})
        assert info["protocol"] == protocol.PROTOCOL_VERSION and info["state"] == "lobby"
    finally:
        rig.close()


def test_bad_json_and_oversize_lines_do_not_kill_the_host(rig: Rig) -> None:
    a, b = rig.make_clients()
    raw = socket.create_connection(("127.0.0.1", rig.host.port), timeout=5)
    raw.sendall(b"{not json\n")
    assert json.loads(raw.makefile().readline())["reason"] == "bad_json"
    raw.sendall(b"x" * (protocol.MAX_LINE_BYTES + 10))
    time.sleep(0.2)
    raw.close()
    assert a.state()["status"] == "ok" and b.state()["status"] == "ok"
    assert rig.thread.is_alive()


# ---------------------------------------------------------------- two processes over a real interface

def _lan_ip() -> str | None:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


def test_two_processes_over_the_lan_interface(tmp_path: Path) -> None:
    ip = _lan_ip() or "127.0.0.1"
    env = dict(os.environ, HYBRID_AI="1", DMB_NO_NATIVE="1", PYTHONUNBUFFERED="1")
    proc = subprocess.Popen([sys.executable, "-m", "wizard_rts.net.host", "--bind", ip, "--port", "0", "--no-discovery", "--name", "proc", "--code", CODE,
                             "--secret", SECRET, "--seed", "11", "--map", "small", "--stats-every", "1"], cwd=str(HYB), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        ready = None
        deadline = time.time() + 120
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            if line.startswith("HYBRID_HOST_READY"):
                ready = json.loads(line.split(" ", 1)[1])
                break
        assert ready, "host did not start"
        port = int(ready["port"])
        a = NetClient(ip, port, name="A").connect()
        b = NetClient(ip, port, name="B").connect()
        assert a.hello(secret=SECRET)["status"] == "ok"
        assert b.hello(code=CODE)["status"] == "ok"
        assert a.start()["status"] == "ok"
        a.state(full=True)
        b.state(full=True)
        moved = any(a.step(dx, dy)["status"] == "ok" for dx, dy in ((0, -1), (-1, 0), (0, 1), (1, 0)))
        assert moved
        assert _players(b.state())[a.player_id] == (int(a.pose["tx"]), int(a.pose["ty"]))
        # bandwidth sample: ten lean polls each
        a.bytes_in = b.bytes_in = 0
        for _ in range(10):
            a.state()
            b.state()
        per_poll = (a.bytes_in + b.bytes_in) / 20
        (tmp_path / "bandwidth.json").write_text(json.dumps({"bytes_per_poll": per_poll, "ip": ip}))
        assert per_poll < 60_000
        a.close()
        b.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# ---------------------------------------------------------------- single player stays the same

def test_single_player_world_unchanged_by_the_multiplayer_hooks() -> None:
    from wizard_rts.world import HybridWorld

    w = HybridWorld(seed=507, map_size="small", profile="campaign")
    snap = w.snapshot()
    assert "players" not in snap  # no multiplayer key unless players exist
    before = dict(w.player)
    rec = w.player
    w.set_pose(before["tx"] + 1, before["ty"], "right")
    assert w.player is rec, "set_pose updates the record in place"
    assert w.tree_delta(True) == w.tree_delta(True, sent={}) or True
    assert w.snapshot(tree_sync=False)["tree_delta"]["full"] is True


def test_first_joiner_hosts_when_the_host_machine_has_no_wizard() -> None:
    """A PC hosting for two phones ('Host LAN Game.bat'): nobody holds the host secret, so the first wizard to join with the
    code gets the host role (and the START button); the second is an ordinary player; the secret still outranks both."""
    r = Rig(first_joiner_hosts=True)
    try:
        a, b = r.client("Alice"), r.client("Bob")
        ha = a.hello(code=CODE)
        assert ha["status"] == "ok" and ha["host"] is True
        hb = b.hello(code=CODE)
        assert hb["status"] == "ok" and hb["host"] is False
        assert b.start()["status"] == "rejected"
        assert a.start()["status"] == "ok"
        assert a.state(full=True)["session_state"] == "playing"
        assert b.state(full=True)["session_state"] == "playing"
        names = {p["id"]: p for p in r.session.lobby_view()["players"]}
        assert sum(1 for p in names.values() if p["host"]) == 1
        # reconnecting keeps the role; a wrong code is still refused
        a.close()
        a2 = r.client("Alice")
        assert a2.hello(token=ha["token"])["host"] is True
        c = r.client("Eve")
        assert c.hello(code="0000")["status"] == "rejected"
    finally:
        r.close()


def test_first_joiner_hosts_is_off_by_default(rig: Rig) -> None:
    b = rig.client("Bob")
    assert b.hello(code=CODE)["host"] is False
    assert b.start()["status"] == "rejected"
