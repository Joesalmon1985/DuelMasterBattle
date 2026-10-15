"""Cooperative exploration over the LAN (M3): two players, one living story. Both can talk to the same settlement person
and see the same quest; one player's dialogue or dungeon state never leaks into the other's view; the quest consequence
is shared because the world is. Uses the developer story fixture (a collapsed mine) on a developer-profile world.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
ROOT = HYB.parent
for entry in (str(HYB), str(ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

os.environ.setdefault("DMB_NO_NATIVE", "1")

from wizard_rts import story, story_fixture  # noqa: E402
from wizard_rts.net.client import NetClient  # noqa: E402
from wizard_rts.net.host import HostServer  # noqa: E402
from wizard_rts.net.session import MultiplayerSession  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402

SECRET, CODE = "s", "1111"


def _route(world, start: tuple[int, int], goal: tuple[int, int], rng: int, avoid: set[tuple[int, int]]) -> list[tuple[int, int]]:
    """Breadth-first over the authoritative walkability rules (the same ones the host applies to every step)."""
    from collections import deque

    def ok(t: tuple[int, int]) -> bool:
        return world.tile_in_map(*t) and t not in world.blocked and not world.solid_for_wizard(t) and t not in avoid

    prev: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        if abs(cur[0] - goal[0]) + abs(cur[1] - goal[1]) <= rng:
            path = []
            while cur is not None:
                path.append(cur)
                cur = prev[cur]
            return path[::-1][1:]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (cur[0] + dx, cur[1] + dy)
            if n in prev or abs(n[0] - start[0]) > 80 or abs(n[1] - start[1]) > 80 or not ok(n):
                continue
            prev[n] = cur
            q.append(n)
    return []


def _walk_to(world, c: NetClient, target: tuple[int, int], rng: int) -> None:
    start = (int(c.pose["tx"]), int(c.pose["ty"]))
    others = {(int(p["tx"]), int(p["ty"])) for pid, p in world.players.items() if pid != c.player_id}
    path = _route(world, start, target, rng, others)
    assert path or abs(start[0] - target[0]) + abs(start[1] - target[1]) <= rng, f"no route from {start} to {target}"
    import time

    for t in path:
        r = c.move(t[0], t[1], "down")
        assert r["status"] == "ok", (t, r)
        time.sleep(0.09)  # a walking wizard, not a teleporting one (the host caps steps per second)


def test_two_players_share_the_story_but_not_each_others_dialogue_state() -> None:
    world = HybridWorld(seed=507, map_size="small", profile="developer")
    world.visual_state = True
    world.ai_enabled = True
    fx = story_fixture.prepare(world, "Red")
    world.ai_enabled = False  # the scenario is prepared; nothing else should move the mine
    session = MultiplayerSession(world, name="story", join_code=CODE, host_secret=SECRET, max_players=2)
    host = HostServer(world, session, bind="127.0.0.1", port=0, discovery_port=None)
    host.start()
    th = threading.Thread(target=host.run_forever, daemon=True)
    th.start()
    try:
        a = NetClient("127.0.0.1", host.port, name="A").connect()
        b = NetClient("127.0.0.1", host.port, name="B").connect()
        assert a.hello(secret=SECRET)["status"] == "ok" and b.hello(code=CODE)["status"] == "ok"
        assert a.start()["status"] == "ok"
        a.state(full=True)
        b.state(full=True)
        # the NPC and the dungeon entrance are in both players' snapshots (the same quest, the same world)
        npc_id = fx["npc"]
        sa, sb = a.state(radius=120), b.state(radius=120)
        rows_a = {e["id"]: e for e in sa["snapshot"]["entities"]}
        rows_b = {e["id"]: e for e in sb["snapshot"]["entities"]}
        assert npc_id in rows_a and npc_id in rows_b
        assert [q["id"] for q in sa["snapshot"]["story"]["quests"]] == [q["id"] for q in sb["snapshot"]["story"]["quests"]] == [fx["quest"]]
        npc_tile = (int(rows_a[npc_id]["tx"]), int(rows_a[npc_id]["ty"]))
        # too far: the story refuses, for either player, through the same validation
        assert a.op({"op": "talk", "npc": npc_id})["reason"] == "too_far" or abs(int(a.pose["tx"]) - npc_tile[0]) + abs(int(a.pose["ty"]) - npc_tile[1]) <= story.TALK_RANGE
        # walk both up to the miner
        _walk_to(world, a, npc_tile, story.TALK_RANGE)
        _walk_to(world, b, npc_tile, story.TALK_RANGE)
        ta = a.op({"op": "talk", "npc": npc_id})
        tb = b.op({"op": "talk", "npc": npc_id})
        assert ta["status"] == "ok" and tb["status"] == "ok"
        assert ta["quest"] == tb["quest"] == fx["quest"]
        assert ta["lines"] and tb["lines"]
        assert "snapshot" not in ta  # a dialogue reply is small and private to the connection that asked
        # one player's dungeon state is his own: B enters the dungeon, A's view of the world stays outside
        entrance = world.story["dungeons"][fx["dungeon"]]["entrance"]["tile"]
        _walk_to(world, b, (int(entrance[0]), int(entrance[1])), story.ENTER_RANGE)
        eb = b.op({"op": "enter", "dungeon": fx["dungeon"]})
        assert eb["status"] == "ok", eb
        assert eb["view"], "B is inside"
        va = a.op({"op": "story_view"})
        assert va["view"] == {} and va["duel"] == {}
        assert a.state()["snapshot"]["story"]["in_dungeon"] == "" and b.state()["snapshot"]["story"]["in_dungeon"] == fx["dungeon"]
        assert session.links[a.player_id].story is None and session.links[b.player_id].story is not None
        assert session.links[b.player_id].story["quests"] is story.state(world)["quests"]  # world-level containers are shared
        # B picks nothing up for A: inventories are per player
        assert b.state()["snapshot"]["story"]["inventory"] == [] and a.state()["snapshot"]["story"]["inventory"] == []
        # A's dialogue choice (an accepted quest) is a world fact both players then see
        choices = [c["id"] for c in ta["choices"] if c.get("available")]
        if choices:
            ca = a.op({"op": "choose", "npc": npc_id, "choice": choices[0]})
            assert ca["status"] == "ok"
            status_a = next(q for q in a.state()["snapshot"]["story"]["quests"] if q["id"] == fx["quest"])["status"]
            status_b = next(q for q in b.state()["snapshot"]["story"]["quests"] if q["id"] == fx["quest"])["status"]
            assert status_a == status_b
        # B can leave the dungeon without touching A
        for _ in range(3):
            b.op({"op": "dungeon_move", "dx": 0, "dy": 1})
        assert a.op({"op": "story_view"})["view"] == {}
    finally:
        host.stop_flag = True
        th.join(timeout=5)
        host.stop()
