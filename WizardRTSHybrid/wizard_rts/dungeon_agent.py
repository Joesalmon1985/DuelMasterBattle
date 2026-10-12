"""A scripted dungeon player written against an `Actor` (view / move / interact), so the same expert drives the live game (through the
wizard ops), the headless dungeon environment and the content-reachability checks. It reads only what the wizard sees: tile rows,
visible entities and their texts, and the inventory."""

from __future__ import annotations

import re
from collections import deque
from typing import Any, Protocol

from wizard_rts.puzzle.dungeon import ROOM_H, room_origin_y


class Actor(Protocol):
    def view(self) -> dict[str, Any]: ...
    def move(self, dx: int, dy: int) -> dict[str, Any]: ...
    def interact(self, entity: str, item: str | None = None, spell: int | None = None) -> dict[str, Any]: ...


def bfs(view: dict[str, Any], goal_adjacent: tuple[int, int] | None, goal_tile: tuple[int, int] | None = None) -> list[tuple[int, int]] | None:
    rows, pos = view["rows"], tuple(view["pos"])
    solid = {tuple(e["pos"]) for e in view["entities"] if e["kind"] in ("door", "logs", "sign")}

    def ok(t: tuple[int, int]) -> bool:
        return 0 <= t[1] < len(rows) and 0 <= t[0] < len(rows[0]) and rows[t[1]][t[0]] != "#" and t not in solid

    def done(t: tuple[int, int]) -> bool:
        if goal_tile is not None:
            return t == goal_tile
        return abs(t[0] - goal_adjacent[0]) + abs(t[1] - goal_adjacent[1]) <= 1

    prev: dict[tuple[int, int], tuple[int, int] | None] = {pos: None}
    q = deque([pos])
    while q:
        cur = q.popleft()
        if done(cur):
            path = []
            while cur != pos:
                path.append(cur)
                cur = prev[cur]
            return path[::-1]
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            n = (cur[0] + dx, cur[1] + dy)
            if n not in prev and ok(n):
                prev[n] = cur
                q.append(n)
    return None


def pick_entity(entities: list[dict[str, Any]], pos: tuple[int, int]) -> dict[str, Any] | None:
    """The entity the UI's interact key would act on from `pos`: within one tile, nearest first, ties by id (shared with the environment)."""
    near = [e for e in entities if abs(e["pos"][0] - pos[0]) + abs(e["pos"][1] - pos[1]) <= 1]
    return sorted(near, key=lambda e: (abs(e["pos"][0] - pos[0]) + abs(e["pos"][1] - pos[1]), e["id"]))[0] if near else None


def stand_path(view: dict[str, Any], target: dict[str, Any], towards: tuple[int, int] | None = None) -> list[tuple[int, int]] | None:
    """Shortest walk to a tile from which interacting acts on `target` (not on a neighbouring entity). With `towards`, among the
    reachable such tiles the one nearest that point wins (the timed gate needs the lever side closest to the gate)."""
    rows = view["rows"]
    solid = {tuple(e["pos"]) for e in view["entities"] if e["kind"] in ("door", "logs", "sign")}
    tx, ty = target["pos"]
    cands = []
    for dx, dy in ((0, 0), (0, 1), (1, 0), (0, -1), (-1, 0)):
        t = (tx + dx, ty + dy)
        if not (0 <= t[1] < len(rows) and 0 <= t[0] < len(rows[0])) or rows[t[1]][t[0]] == "#" or t in solid:
            continue
        chosen = pick_entity(view["entities"], t)
        if chosen is not None and chosen["id"] == target["id"]:
            cands.append(t)
    best = None
    for t in cands:
        path = bfs(view, None, t)
        if path is None:
            continue
        key = (abs(t[0] - towards[0]) + abs(t[1] - towards[1]) if towards else 0, len(path), t)
        if best is None or key < best[0]:
            best = (key, path)
    return best[1] if best else None


def walk(actor: Actor, path: list[tuple[int, int]]) -> dict[str, Any]:
    cur = tuple(actor.view()["pos"])
    res: dict[str, Any] = {}
    for step in path:
        res = actor.move(step[0] - cur[0], step[1] - cur[1])
        if res["status"] != "moved":
            raise RuntimeError("blocked at %s: %s" % (step, res))
        cur = step
    return res


def go_adjacent(actor: Actor, target: tuple[int, int]) -> dict[str, Any]:
    path = bfs(actor.view(), target)
    if path is None:
        raise RuntimeError("no route to %s" % (target,))
    walk(actor, path)
    return actor.view()


def _words_to_order(text: str) -> list[int]:
    words = ["first", "second", "third", "fourth"]
    m = re.search(r"(first|second|third|fourth)(?:, then (?:first|second|third|fourth))+", text)
    return [words.index(w) for w in re.findall(r"first|second|third|fourth", m.group(0))]


def solve_room(actor: Actor, room: int, log: list[str] | None = None) -> None:
    oy = room_origin_y(room)

    def ents(kind: str | None = None) -> list[dict]:
        v = actor.view()
        return [e for e in v["entities"] if oy <= e["pos"][1] < oy + ROOM_H and (kind is None or e["kind"] == kind)]

    clue = next((e for e in ents("sign") if e["id"].endswith("_clue")), None)
    text = clue["text"] if clue else ""
    low = text.lower()

    def use(entity: dict[str, Any], **kw: Any) -> dict[str, Any]:
        path = stand_path(actor.view(), entity)
        if path is None:
            go_adjacent(actor, tuple(entity["pos"]))
        else:
            walk(actor, path)
        res = actor.interact(entity["id"], **kw)
        if log is not None:
            log.append("%s %s -> %s" % (entity["id"], kw, str(res.get("text", res.get("reason", "")))[:60]))
        return res

    for pick in [e for e in ents("pickup") if not (e["id"].endswith("_reward") or e["id"].endswith("_sigil"))]:
        use(pick)
    mech = sorted(ents("logs"), key=lambda e: e["id"])
    inv = list(actor.view()["inventory"])
    local_items = ("clay_idol", "brass_gear", "tallow_candle", "mirror_shard", "black_seed")
    if "two niches" in low:
        sigil = next((i for i in inv if i.startswith("sigil_")), None)
        local = next((i for i in inv if i in local_items), None)
        for niche, item in zip(mech, (local, sigil)):
            use(niche, item=item)
    elif "key sits on a plate" in low:
        fodder = [i for i in inv if i in local_items][-1]
        use(mech[0], item=fodder)
        use(mech[0])
    elif "three levers" in low:
        for i in _words_to_order(text):
            use(mech[i])
    elif "four coloured stones" in low:
        for i in _words_to_order(text):
            use(mech[i])
    elif "a plate in the floor" in low:
        use(mech[0], item="grey_stone")
    elif "pull the lever and the gate lifts" in low:
        lever = next(e for e in mech if "lever" in e["id"])
        gate = next(e for e in mech if e["id"].endswith("_gate"))
        # the gate counts nine steps once the lever is pulled: stand at the lever on the side nearest the gate
        walk(actor, stand_path(actor.view(), lever, towards=tuple(gate["pos"])) or [])
        actor.interact(lever["id"])
        walk(actor, stand_path(actor.view(), gate) or bfs(actor.view(), tuple(gate["pos"])) or [])
        res = actor.interact(gate["id"])
        if log is not None:
            log.append("gate -> %s" % str(res.get("text", ""))[:60])
    elif "wants a wizard" in low:
        use(mech[0], spell=1 if "brazier" in low else (6 if "chasm" in low else 0))
    elif "carved face says" in low:
        m = re.search(r"Pull the (left|right)\.", text)
        said = 0 if m and m.group(1) == "left" else 1
        liar = "The face lies." in text
        use(mech[1 - said if liar else said])


def solve_dungeon(actor: Actor, log: list[str] | None = None) -> bool:
    for room in range(4):
        solve_room(actor, room, log)
        if room < 3:
            nxt = room_origin_y(room + 1) + 6
            path = bfs(actor.view(), None, (6, nxt))
            if path is None:
                raise RuntimeError("the door above room %d did not open" % room)
            walk(actor, path)
    return all(actor.view()["solved"])
