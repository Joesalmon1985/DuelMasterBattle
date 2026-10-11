"""A scripted wizard that plays the story through the public wizard ops only (same ops the Godot client sends).

It sees what the wizard sees: the dungeon view (tile rows and visible entities with their texts), its inventory, the dialogue lines
and choices. It never reads puzzle records, the duel secret or `world.story` internals. It is the scripted baseline of the
quest/dungeon/duel environments and the reference that every generated dungeon is solvable.
"""

from __future__ import annotations

import re
from collections import deque
from typing import Any

from wizard_rts import story
from wizard_rts.mastermind_solvers import ConsistentSolver


def op(world: Any, name: str, **kw: Any) -> dict[str, Any]:
    return story.dispatch(world, {"op": name, **kw})


def walk_to_npc(world: Any, npc: str) -> None:
    """Stand beside the person (the Godot client walks the wizard; here the pose is set to a free tile next to them)."""
    n = story.state(world)["npcs"][npc]
    place_wizard_near(world, n["tile"])


def place_wizard_near(world: Any, tile: list[int], rng: int = 1) -> None:
    x, y = tile
    for r in range(1, 4):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if abs(dx) + abs(dy) == r and world.tile_in_map(x + dx, y + dy) and (x + dx, y + dy) not in world.blocked:
                    world.set_pose(x + dx, y + dy, "down", snapshot=False)
                    return
    raise RuntimeError("no standing tile near %s" % (tile,))


def _bfs(view: dict[str, Any], goal_adjacent: tuple[int, int] | None, goal_tile: tuple[int, int] | None = None) -> list[tuple[int, int]] | None:
    rows, pos = view["rows"], tuple(view["pos"])
    solid = {tuple(e["pos"]) for e in view["entities"] if e["kind"] in ("door", "logs", "sign")}
    start = pos

    def ok(t: tuple[int, int]) -> bool:
        return 0 <= t[1] < len(rows) and 0 <= t[0] < len(rows[0]) and rows[t[1]][t[0]] != "#" and t not in solid

    def done(t: tuple[int, int]) -> bool:
        if goal_tile is not None:
            return t == goal_tile
        return abs(t[0] - goal_adjacent[0]) + abs(t[1] - goal_adjacent[1]) <= 1

    prev: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        if done(cur):
            path = []
            while cur != start:
                path.append(cur)
                cur = prev[cur]
            return path[::-1]
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            n = (cur[0] + dx, cur[1] + dy)
            if n not in prev and ok(n):
                prev[n] = cur
                q.append(n)
    return None


def go_adjacent(world: Any, view: dict[str, Any], target: tuple[int, int]) -> dict[str, Any]:
    path = _bfs(view, target)
    if path is None:
        raise RuntimeError("no route to %s" % (target,))
    cur = tuple(view["pos"])
    out: dict[str, Any] = {"view": view}
    for step in path:
        res = op(world, "dungeon_move", dx=step[0] - cur[0], dy=step[1] - cur[1])
        if res["status"] != "moved":
            raise RuntimeError("blocked at %s: %s" % (step, res))
        cur = step
        out = res
    return out["view"] if out.get("view") else view


def _ent(view: dict[str, Any], pred) -> dict[str, Any] | None:
    for e in view["entities"]:
        if pred(e):
            return e
    return None


def _room_of(view: dict[str, Any], y: int) -> int:
    from wizard_rts.puzzle.dungeon import ROOM_H, room_origin_y

    for r in range(4):
        if room_origin_y(r) <= y < room_origin_y(r) + ROOM_H:
            return r
    return -1


def solve_dungeon(world: Any, log: list[str] | None = None) -> bool:
    """Play all four rooms in order. Returns True when every puzzle reports solved. Raises if the content is not completable."""
    view = story.dungeon_view(world)
    from wizard_rts.puzzle.dungeon import room_origin_y

    for room in range(4):
        oy = room_origin_y(room)
        view = _room(world, view, room, oy, log)
        if room < 3:  # walk through the opened door to the next room
            door_y = oy - 1
            view = story.dungeon_view(world)
            nxt = room_origin_y(room + 1) + 6
            path = _bfs(view, None, (6, nxt))
            if path is None:
                raise RuntimeError("the door above room %d did not open" % room)
            cur = tuple(view["pos"])
            for step in path:
                res = op(world, "dungeon_move", dx=step[0] - cur[0], dy=step[1] - cur[1])
                assert res["status"] == "moved", res
                cur = step
            view = story.dungeon_view(world)
    return all(view["solved"])


def _room(world: Any, view: dict[str, Any], room: int, oy: int, log: list[str] | None) -> dict[str, Any]:
    def ents(kind: str | None = None):
        return [e for e in view["entities"] if oy <= e["pos"][1] < oy + 7 and (kind is None or e["kind"] == kind)]

    # evidence: read the clue sign (the first sign of the room)
    clue = next((e for e in ents("sign") if e["id"].endswith("_clue")), None)
    text = clue["text"] if clue else ""

    def use(entity: dict[str, Any], **kw: Any) -> dict[str, Any]:
        nonlocal view
        view = go_adjacent(world, story.dungeon_view(world), tuple(entity["pos"]))
        res = op(world, "dungeon_interact", entity=entity["id"], **kw)
        if log is not None:
            log.append("%s %s -> %s" % (entity["id"], kw, res.get("text", res.get("reason", ""))[:60]))
        view = story.dungeon_view(world)
        return res

    # collect every loose item in the room that a template might want
    for pick in [e for e in ents("pickup") if "requires" not in e["text"]]:
        if pick["id"].endswith("_reward") or pick["id"].endswith("_sigil"):
            continue
        use(pick)
    mech = [e for e in ents("logs")]
    lowered = text.lower()
    if "two niches" in lowered:  # offerings: the local item and the imported sigil
        niches = sorted(mech, key=lambda e: e["id"])
        inv = list(view["inventory"])
        sigil = next((i for i in inv if i.startswith("sigil_")), None)
        local = next((i for i in inv if i in ("clay_idol", "brass_gear", "tallow_candle", "mirror_shard", "black_seed")), None)
        for niche, item in zip(niches, (local, sigil)):
            use(niche, item=item)
    elif "key sits on a plate" in lowered:  # exchange: leave something heavy, take the key
        ped = mech[0]
        inv = [i for i in view["inventory"] if i in ("clay_idol", "brass_gear", "tallow_candle", "mirror_shard", "black_seed")]
        use(ped, item=inv[-1])
        use(ped)
    elif "three levers" in lowered:
        order = _words_to_order(text)
        levers = sorted(mech, key=lambda e: e["id"])
        for i in order:
            use(levers[i])
    elif "four coloured stones" in lowered:
        order = _words_to_order(text)
        tiles = sorted(mech, key=lambda e: e["id"])
        for i in order:
            use(tiles[i])
    elif "a plate in the floor" in lowered:
        use(mech[0], item="grey_stone")
    elif "pull the lever and the gate lifts" in lowered:
        lever = next(e for e in mech if "lever" in e["id"])
        gate = next(e for e in mech if e["id"].endswith("_gate"))
        view = go_adjacent(world, story.dungeon_view(world), tuple(lever["pos"]))
        op(world, "dungeon_interact", entity=lever["id"])
        view = go_adjacent(world, story.dungeon_view(world), tuple(gate["pos"]))
        op(world, "dungeon_interact", entity=gate["id"])
        view = story.dungeon_view(world)
    elif "wants a wizard" in lowered:
        target = mech[0]
        spell = 1 if "brazier" in lowered else (6 if "chasm" in lowered else 0)
        use(target, spell=spell)
    elif "carved face says" in lowered:
        m = re.search(r"Pull the (left|right)\.", text)
        said = 0 if m and m.group(1) == "left" else 1
        liar = "The face lies." in text
        correct = 1 - said if liar else said
        levers = sorted(mech, key=lambda e: e["id"])  # ids end _left / _right; sorted puts left first
        use(levers[correct])
    return story.dungeon_view(world)


def _words_to_order(text: str) -> list[int]:
    words = ["first", "second", "third", "fourth"]
    m = re.search(r"(first|second|third|fourth)(?:, then (?:first|second|third|fourth))+", text)
    seq = re.findall(r"first|second|third|fourth", m.group(0))
    return [words.index(w) for w in seq]


def break_the_code(world: Any, max_guesses: int = 14) -> dict[str, Any]:
    """Play the Mastermind duel with only the public feedback."""
    res = op(world, "duel_begin")
    if res["status"] != "started":
        return res
    solver = ConsistentSolver()
    history: list[tuple[list[int], int, int]] = []
    last: dict[str, Any] = res
    for _ in range(max_guesses):
        guess = solver.next_guess(history)
        last = op(world, "duel_guess", guess=guess)
        if last["status"] in ("solved", "exhausted"):
            return last
        fb = last["feedback"]
        history.append((guess, fb["exact"], fb["colour_only"]))
    return last
