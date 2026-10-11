"""Port of DmbDungeonMap (godot_project/sim/world/dungeon_map.gd): a generated dungeon as a tile area.

Four rooms of 11x7 in a column, entry at the bottom, a door above each room that opens once its puzzle is solved, a reward plinth in
the top room. `area_for` is read-only over dungeon and puzzle state and matches the GDScript output (tests/test_puzzle_parity.py).
`DungeonRun` adds what the headless game needs and the GDScript left to the scene: a position, four-direction movement over the
tile rows, interaction with the entities on the map and an inventory, all driven by the same `logic.act`.
"""

from __future__ import annotations

import copy
from typing import Any

from wizard_rts.puzzle import items as I
from wizard_rts.puzzle import logic

PREFIX = "dg_"
ROOM_W = 11
ROOM_H = 7
W = ROOM_W + 2
ENTRY = (6, 30)
HEIGHT = 4 * (ROOM_H + 1) + 1


def area_id(d: dict[str, Any]) -> str:
    return PREFIX + str(d["id"])


def room_origin_y(room: int) -> int:
    return 1 + (3 - room) * (ROOM_H + 1)


def _put(line: str, x: int, ch: str) -> str:
    return line[:x] + ch + line[x + 1:]


def _m(a: dict, b: dict) -> dict:
    out = dict(a)
    out.update(b)
    return out


def area_for(d: dict[str, Any], puzzle_states: dict[str, Any], world_node_area: str, arrive_pos: list[int]) -> dict[str, Any]:
    rows = ["#" * W for _ in range(HEIGHT)]
    for room in range(4):
        oy = room_origin_y(room)
        for y in range(oy, oy + ROOM_H):
            for x in range(1, W - 1):
                rows[y] = _put(rows[y], x, ".")
    entities: list[dict[str, Any]] = []
    aid = area_id(d)
    tower = str(d["kind"]) == "tower"
    rows[HEIGHT - 1] = _put(rows[HEIGHT - 1], 6, ":")
    entities.append({"kind": "exit", "id": aid + "_out", "pos": [6, HEIGHT - 1], "to_area": world_node_area, "to_pos": list(arrive_pos), "facing": "down",
                     "travel_text": "Daylight. You had forgotten it was a thing."})
    entities.append({"kind": "sign", "id": aid + "_sign", "pos": [2, room_origin_y(0) + ROOM_H - 1],
                     "text": "%s\n\nFour rooms. Each asks one thing. The last gives one thing." % (
                         "The tower's stair is worn in the middle, where every foot before yours went." if tower else
                         "The cave is dressed stone past the first yard. Somebody built this fast, and recently.")})
    for room in range(4):
        p = d["puzzles"][room]
        key = "%s/%s" % (d["id"], p["id"])
        st = puzzle_states.get(key) or logic.fresh_state(p)
        solved = bool(st.get("solved", False))
        oy = room_origin_y(room)
        if room < 3:
            door_y = oy - 1
            if solved:
                rows[door_y] = _put(rows[door_y], 6, ":")
            else:
                entities.append({"kind": "door", "id": "%s_%s_door" % (aid, p["id"]), "pos": [6, door_y], "marker": "door_dungeon",
                                 "text": "Shut. The room has not been answered.", "puzzle_key": key})
        entities.append({"kind": "sign", "id": "%s_%s_clue" % (aid, p["id"]), "pos": [1, oy], "text": "%s\n\n%s" % (p["title"], p["clue"]), "puzzle_key": key})
        _dress(entities, rows, aid, p, st, oy, key)
    top = room_origin_y(3)
    entities.append({"kind": "pickup", "id": "%s_reward" % aid, "pos": [5, top + 5], "sprite": "diamond", "requires_dungeon_solved": str(d["id"]),
                     "dungeon_reward": str(d["id"]), "text": ""})
    entities.append({"kind": "pickup", "id": "%s_sigil" % aid, "pos": [7, top + 5], "sprite": "ring", "requires_dungeon_solved": str(d["id"]),
                     "grant": {"item": str(d["provides"])}, "text": "%s. Cut here, for a lock somewhere else." % I.name_of(str(d["provides"]))})
    name = "%s %s" % (str(d["faction"]), "tower" if tower else "cave")
    return {"id": aid, "name": name, "rows": rows, "theme": "dungeon", "entities": entities, "dungeon": d}


def _dress(entities: list, rows: list, aid: str, p: dict, st: dict, oy: int, key: str) -> None:
    base = {"puzzle_key": key}
    cx, cy = 6, oy + 3
    t = p["type"]
    if t == "offerings":
        for i, sl in enumerate(p["slots"]):
            filled = str(sl["id"]) in st.get("filled", {})
            entities.append(_m(base, {"kind": "logs", "id": "%s_%s" % (aid, sl["id"]), "pos": [cx - 2 + i * 4, oy + 1], "marker": "idol" if filled else "box",
                                      "puzzle_action": {"kind": "place", "slot": str(sl["id"])}, "text": "A niche" + (" — filled." if filled else ", shaped for something.")}))
        for it in p["items"]:
            entities.append(_m(base, {"kind": "pickup", "id": "%s_%s_item_%s" % (aid, p["id"], it), "pos": [cx + 3, cy + 1], "sprite": I.sprite_of(it),
                                      "grant": {"item": it}, "text": I.describe(it)}))
    elif t == "exchange":
        taken = bool(st.get("key_taken", False))
        entities.append(_m(base, {"kind": "logs", "id": "%s_%s" % (aid, p["pedestal"]), "pos": [cx, cy], "marker": "ring" if not taken else "box",
                                  "puzzle_action": {"kind": "exchange"}, "text": "A plate on a pedestal." + (" A key rests on it." if not taken else " Bare.")}))
        for it in p["items"]:
            entities.append(_m(base, {"kind": "pickup", "id": "%s_%s_item_%s" % (aid, p["id"], it), "pos": [cx - 3, cy + 1], "sprite": I.sprite_of(it),
                                      "grant": {"item": it}, "text": I.describe(it)}))
    elif t == "switch_chain":
        for i in range(3):
            entities.append(_m(base, {"kind": "logs", "id": "%s_%s" % (aid, p["levers"][i]), "pos": [cx - 3 + i * 3, cy], "marker": "staff",
                                      "puzzle_action": {"kind": "pull", "index": i}, "text": "Lever %s." % ["one", "two", "three"][i]}))
    elif t == "plate_hold":
        entities.append(_m(base, {"kind": "logs", "id": "%s_%s" % (aid, p["plate"]), "pos": [cx, cy], "marker": "ring",
                                  "puzzle_action": {"kind": "place"}, "text": "A pressure plate."}))
        for it in p["items"]:
            entities.append(_m(base, {"kind": "pickup", "id": "%s_%s_item_%s" % (aid, p["id"], it), "pos": [cx - 3, cy + 1], "sprite": I.sprite_of(it),
                                      "grant": {"item": it}, "text": I.describe(it)}))
    elif t == "timed_gate":
        entities.append(_m(base, {"kind": "logs", "id": "%s_%s" % (aid, p["lever"]), "pos": [2, cy + 2], "marker": "staff",
                                  "puzzle_action": {"kind": "pull"}, "text": "A lever, and a rope that runs up into the dark."}))
        entities.append(_m(base, {"kind": "logs", "id": "%s_%s_gate" % (aid, p["id"]), "pos": [cx, oy], "marker": "door_stone",
                                  "puzzle_action": {"kind": "pass"}, "text": "A gate of iron bars." + (" Lifted — and counting." if st.get("open", False) else " Down.")}))
    elif t == "mosaic":
        for i in range(4):
            entities.append(_m(base, {"kind": "logs", "id": "%s_%s_tile%d" % (aid, p["id"], i), "pos": [cx - 3 + i * 2, cy], "marker": "stone_shard",
                                      "puzzle_action": {"kind": "tread", "index": i}, "text": "A %s stone, set in the floor." % ["red", "blue", "green", "grey"][i]}))
    elif t == "magic_target":
        spell = int(p["spell"])
        entities.append(_m(base, {"kind": "logs", "id": "%s_%s" % (aid, p["target"]), "pos": [cx, cy],
                                  "marker": "fire_0" if spell == 1 else ("rock" if spell == 6 else "mirror"),
                                  "puzzle_action": {"kind": "cast"}, "text": "The way is blocked by %s." % p["desc"]}))
    elif t == "two_levers":
        for i in range(2):
            entities.append(_m(base, {"kind": "logs", "id": "%s_%s" % (aid, p["levers"][i]), "pos": [cx - 2 + i * 4, cy], "marker": "staff",
                                      "puzzle_action": {"kind": "pull", "index": i}, "text": "The %s lever." % ["left", "right"][i]}))


# ---------------------------------------------------------------- headless play

class DungeonRun:
    """One visit to a dungeon: position, inventory, puzzle states. Pure data in `state` (JSON-able) so it saves with the world."""

    def __init__(self, dungeon: dict[str, Any], state: dict[str, Any] | None = None, inventory: list[str] | None = None) -> None:
        self.d = dungeon
        self.state = state if state is not None else {
            "pos": list(ENTRY), "puzzles": {}, "taken": [], "log": [], "solved_reward": False, "spawned": [], "steps": 0, "out": False}
        # the wizard's inventory is shared across dungeons: the caller passes the list that owns it
        self.inv: list[str] = inventory if inventory is not None else self.state.setdefault("inventory", [])
        self.spells = [0, 1, 6]

    # ---- queries
    def puzzle_state(self, p: dict) -> dict:
        key = "%s/%s" % (self.d["id"], p["id"])
        return self.state["puzzles"].setdefault(key, logic.fresh_state(p))

    def area(self) -> dict[str, Any]:
        return area_for(self.d, self.state["puzzles"], "world", [0, 0])

    def entity_at(self, pos: list[int]) -> list[dict]:
        return [e for e in self.area()["entities"] if list(e["pos"]) == list(pos) and e["id"] not in self.state["taken"]]

    def walkable(self, x: int, y: int) -> bool:
        a = self.area()
        if not (0 <= y < len(a["rows"]) and 0 <= x < W):
            return False
        if a["rows"][y][x] == "#":
            return False
        for e in a["entities"]:  # a door, lever, plate or sign is solid; a pickup or the exit is stepped on
            if list(e["pos"]) == [x, y] and e["kind"] in ("door", "logs", "sign"):
                return False
        return True

    # ---- actions
    def move(self, dx: int, dy: int) -> dict[str, Any]:
        x, y = self.state["pos"]
        nx, ny = x + dx, y + dy
        if abs(dx) + abs(dy) != 1 or not self.walkable(nx, ny):
            return {"status": "blocked", "pos": [x, y]}
        self.state["pos"] = [nx, ny]
        self.state["steps"] += 1
        room = self.room_of(ny)
        if room is not None:  # a step counts for the room's timed gate
            p = self.d["puzzles"][room]
            if p["type"] == "timed_gate":
                logic.act(p, self.puzzle_state(p), {"kind": "step"}, self._ctx())
        for e in self.entity_at([nx, ny]):
            if e["kind"] == "exit":
                self.state["out"] = True
                return {"status": "moved", "pos": [nx, ny], "exit": True}
        return {"status": "moved", "pos": [nx, ny]}

    def room_of(self, y: int) -> int | None:
        for r in range(4):
            if room_origin_y(r) <= y < room_origin_y(r) + ROOM_H:
                return r
        return None

    def _ctx(self) -> dict[str, Any]:
        return {"items": list(self.inv), "spells": list(self.spells)}

    def interact(self, entity_id: str, item: str | None = None, spell: int | None = None) -> dict[str, Any]:
        """Use an entity within one tile of the position (a pickup on the same tile also counts)."""
        area = self.area()
        ent = next((e for e in area["entities"] if e["id"] == entity_id and e["id"] not in self.state["taken"]), None)
        if ent is None:
            return {"status": "rejected", "reason": "no_such_entity"}
        px, py = self.state["pos"]
        ex, ey = ent["pos"]
        if abs(px - ex) + abs(py - ey) > 1:
            return {"status": "rejected", "reason": "too_far"}
        if "requires_dungeon_solved" in ent and not all(self.puzzle_state(p)["solved"] for p in self.d["puzzles"]):
            return {"status": "rejected", "reason": "locked", "text": "Nothing happens. Four rooms are still unanswered."}
        if ent["kind"] == "pickup":
            if len(self.inv) >= I.MAX_SLOTS:
                return {"status": "rejected", "reason": "inventory_full"}
            if "grant" in ent:
                self.inv.append(ent["grant"]["item"])
            if "dungeon_reward" in ent:
                self.state["solved_reward"] = True
            self.state["taken"].append(ent["id"])
            return {"status": "ok", "text": ent.get("text", ""), "granted": ent.get("grant", {}).get("item", "")}
        action = ent.get("puzzle_action")
        if action is None:
            return {"status": "ok", "text": ent.get("text", "")}
        p = next(q for q in self.d["puzzles"] if "%s/%s" % (self.d["id"], q["id"]) == ent["puzzle_key"])
        act = dict(action)
        if act["kind"] == "exchange":  # the pedestal: place the offered item if one is given, else lift the key
            act = {"kind": "place", "item": item} if item else {"kind": "take"}
        elif act["kind"] == "place" and item:
            act["item"] = item
        elif act["kind"] == "cast":
            act["spell"] = spell if spell is not None else -1
        st = self.puzzle_state(p)
        res = logic.act(p, st, act, self._ctx())
        for it in res["consume"]:
            if it in self.inv:
                self.inv.remove(it)
        if res["grant"]:
            self.inv.append(res["grant"])
        if res["spawn_enemy"]:
            self.state["spawned"].append(res["spawn_enemy"])
        if res["reset"]:
            pass  # the logic already reset progress/gate state
        self.state["log"].append({"entity": entity_id, "action": act, "text": res["text"], "solved_now": res["solved_now"]})
        return {"status": "ok", "text": res["text"], "solved_now": res["solved_now"], "result": res}

    def solved_all(self) -> bool:
        return all(self.puzzle_state(p)["solved"] for p in self.d["puzzles"])
