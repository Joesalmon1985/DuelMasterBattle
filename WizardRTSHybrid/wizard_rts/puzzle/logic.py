"""Port of DmbPuzzleLogic (godot_project/sim/world/puzzle_logic.gd): the pure puzzle state machine.

`act` takes a puzzle record, its mutable state and an action and returns what happened; it never touches an inventory or a map.
Parity with the GDScript is tested in tests/test_puzzle_parity.py.
"""

from __future__ import annotations

from typing import Any

from wizard_rts.puzzle import items as I


def fresh_state(p: dict[str, Any]) -> dict[str, Any]:
    st: dict[str, Any] = {"solved": False}
    t = p["type"]
    if t == "offerings":
        st["filled"] = {}
    elif t == "exchange":
        st["key_taken"] = False
        st["placed"] = ""
    elif t in ("switch_chain", "mosaic"):
        st["progress"] = 0
    elif t == "plate_hold":
        st["held_by"] = ""
    elif t == "timed_gate":
        st["open"] = False
        st["steps_left"] = 0
    elif t == "two_levers":
        st["wrong_pulls"] = 0
    return st


def _solve(st: dict, r: dict, text: str) -> None:
    st["solved"] = True
    r["solved_now"] = True
    r["text"] = text


def _slot(p: dict, sid: str) -> dict:
    for s in p.get("slots", []):
        if str(s["id"]) == sid:
            return s
    return {}


def act(p: dict[str, Any], st: dict[str, Any], action: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """ctx: {"items": [item ids], "spells": [spell ids]}. Mutates `st`; returns the result record."""
    r: dict[str, Any] = {"text": "", "solved_now": False, "consume": [], "grant": "", "spawn_enemy": "", "reset": False}
    if st.get("solved", False):
        r["text"] = "This room has already given what it had."
        return r
    have = ctx.get("items", [])
    kind = str(action.get("kind", ""))
    t = p["type"]
    if t == "offerings":
        if kind == "place":
            sid, item = str(action.get("slot", "")), str(action.get("item", ""))
            slot = _slot(p, sid)
            if not slot:
                r["text"] = "There is no niche there."
            elif sid in st["filled"]:
                r["text"] = "That niche is already filled."
            elif item not in have:
                r["text"] = "You do not have that."
            elif str(slot["item"]) != item:
                r["text"] = "%s does not fit the shape cut here." % I.name_of(item)
            else:
                st["filled"][sid] = item
                if slot.get("keep", False):
                    r["text"] = "You hold %s to the niche. The stone recognises it — and lets you keep it." % I.name_of(item)
                else:
                    r["consume"] = [item]
                    r["text"] = "%s settles into the stone like it was carved for it." % I.name_of(item)
                if len(st["filled"]) == len(p["slots"]):
                    _solve(st, r, "Both niches full. Somewhere below, a counterweight lets go, and the far door opens.")
        elif kind == "inspect":
            sid = str(action.get("slot", ""))
            slot = _slot(p, sid)
            if slot:
                r["text"] = "A niche shaped for %s." % I.name_of(str(slot["item"])) if sid not in st["filled"] else "Filled."
    elif t == "exchange":
        if kind == "take":
            if st["key_taken"]:
                r["text"] = "The plate is bare."
            else:
                st["key_taken"] = True
                r["grant"] = str(p["gives"])
                if st["placed"] == "":
                    r["text"] = "You lift the key. The plate rises a finger's width and the door drops shut with a boom."
                else:
                    _solve(st, r, "You lift the key. The plate holds — %s keeps it down. The door stays open." % I.name_of(str(st["placed"])))
        elif kind == "place":
            item = str(action.get("item", ""))
            if item not in have:
                r["text"] = "You do not have that."
            elif item not in p["accepts"]:
                r["text"] = "Too light. The plate does not notice."
            elif st["placed"] != "":
                r["text"] = "Something already sits there."
            else:
                st["placed"] = item
                r["consume"] = [item]
                if st["key_taken"]:
                    _solve(st, r, "The plate sinks under %s. Chains rattle, and the door lifts again." % I.name_of(item))
                else:
                    r["text"] = "%s rests beside the key. The plate does not move." % I.name_of(item)
    elif t in ("switch_chain", "mosaic"):
        step_kind = "pull" if t == "switch_chain" else "tread"
        if kind == step_kind:
            i = int(action.get("index", -1))
            order = p["order"]
            prog = int(st["progress"])
            if i == int(order[prog]):
                st["progress"] = prog + 1
                if st["progress"] == len(order):
                    _solve(st, r, "The last one. Stone slides on stone, and the way is open.")
                else:
                    r["text"] = "Something below clicks and holds. %d of %d." % (st["progress"], len(order))
            else:
                st["progress"] = 0
                r["reset"] = True
                r["text"] = "A dull thud. Everything resets." if step_kind == "pull" else "The stones dim. Start again."
    elif t == "plate_hold":
        if kind == "place":
            item = str(action.get("item", ""))
            if item not in have:
                r["text"] = "You do not have that."
            elif item not in p["items"]:
                r["text"] = "Too light. The plate lifts as soon as you let go."
            else:
                st["held_by"] = item
                r["consume"] = [item]
                _solve(st, r, "%s sits on the plate. It sinks. The door grinds open and, this time, stays." % I.name_of(item))
        elif kind == "step_on":
            r["text"] = "The plate sinks and the door lifts. You step off to go to it — and it slams. Of course it does."
    elif t == "timed_gate":
        if kind == "pull":
            st["open"] = True
            st["steps_left"] = int(p["steps"])
            r["text"] = "The gate lifts. It has started counting."
        elif kind == "step":
            if st["open"]:
                st["steps_left"] = int(st["steps_left"]) - 1
                if int(st["steps_left"]) <= 0:
                    st["open"] = False
                    r["reset"] = True
                    r["text"] = "The gate drops."
        elif kind == "pass":
            if st["open"]:
                _solve(st, r, "You are through as it falls. It clips your heel.")
            else:
                r["text"] = "The gate is down."
    elif t == "magic_target":
        if kind == "cast":
            s = int(action.get("spell", -1))
            if s not in ctx.get("spells", []):
                r["text"] = "You do not know that magic."
            elif s == int(p["spell"]):
                _solve(st, r, str(p["result"]))
            else:
                r["text"] = "%s does nothing useful to %s." % (I.essence_name(s), str(p["desc"]))
    elif t == "two_levers":
        if kind == "pull":
            i = int(action.get("index", -1))
            if i == int(p["correct"]):
                _solve(st, r, "The right one. The door opens without complaint.")
            else:
                st["wrong_pulls"] = int(st["wrong_pulls"]) + 1
                r["spawn_enemy"] = str(p["wrong_enemy"])
                r["text"] = "The wrong one. A grille in the ceiling opens, and something drops through it."
    return r


def solution(p: dict[str, Any]) -> list[dict[str, Any]]:
    """The shortest action list that solves `p` given a full inventory."""
    t = p["type"]
    if t == "offerings":
        return [{"kind": "place", "slot": s["id"], "item": s["item"]} for s in p["slots"]]
    if t == "exchange":
        return [{"kind": "place", "item": p["items"][0]}, {"kind": "take"}]
    if t == "switch_chain":
        return [{"kind": "pull", "index": i} for i in p["order"]]
    if t == "mosaic":
        return [{"kind": "tread", "index": i} for i in p["order"]]
    if t == "plate_hold":
        return [{"kind": "place", "item": "grey_stone"}]
    if t == "timed_gate":
        return [{"kind": "pull"}, {"kind": "pass"}]
    if t == "magic_target":
        return [{"kind": "cast", "spell": p["spell"]}]
    if t == "two_levers":
        return [{"kind": "pull", "index": p["correct"]}]
    return []
