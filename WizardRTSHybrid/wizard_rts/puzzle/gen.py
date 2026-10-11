"""Port of DmbPuzzleGen (godot_project/sim/world/puzzle_gen.gd): a dungeon's four puzzles from a seed.

Same templates, same RNG calls in the same order (GodotRng), same text. Parity with the GDScript output is tested in
tests/test_puzzle_parity.py against fixtures exported by the real code (client/tests/export_puzzle_parity.gd).
"""

from __future__ import annotations

from typing import Any

from wizard_rts.puzzle.rng import GodotRng

TEMPLATES = ["offerings", "exchange", "switch_chain", "plate_hold", "timed_gate", "mosaic", "magic_target", "two_levers"]
LOCAL_ITEMS = ["clay_idol", "brass_gear", "tallow_candle", "mirror_shard", "black_seed"]
WORLD_SPELLS = [1, 6, 0]  # Water, Vine, Fire
SPELL_TARGETS = {
    1: ["a brazier roaring far too hot for the room", "Douse it", "The fire dies with a hiss. Behind the smoke, the way is open."],
    6: ["a chasm too wide to jump", "Bridge it with Vine", "Roots knot across the gap and hold. Mostly."],
    0: ["a wall of old ice", "Melt it", "The ice runs to water and the water runs away. Cold stone, and a door."],
}
WORDS = ["first", "second", "third", "fourth"]


def generate(d: dict[str, Any]) -> list[dict[str, Any]]:
    rng = GodotRng(int(d["seed"]))
    pool = list(TEMPLATES)
    pool.remove("offerings")
    picks: list[str] = []
    for _ in range(3):
        t = pool[rng.randi_range(0, len(pool) - 1)]
        pool.remove(t)
        picks.append(t)
    dep_pos = rng.randi_range(1, 3)
    picks.insert(dep_pos, "offerings")
    return [_make(picks[i], "p%d" % (i + 1), rng, d if picks[i] == "offerings" else {}, i) for i in range(4)]


def _shuffle(a: list, rng: GodotRng) -> None:
    for i in range(len(a) - 1, 0, -1):
        j = rng.randi_range(0, i)
        a[i], a[j] = a[j], a[i]


def _order_words(order: list[int]) -> str:
    return ", then ".join(WORDS[i] for i in order)


def _source_hint(dep: dict[str, Any]) -> str:
    need = dep["needs"]
    if str(need["from"]) == "settlement":
        return "the people of the steading that raised this place carry such marks"
    return "carved in the heart of the %s" % str(need["from"]).replace("_", " ")


def _make(kind: str, pid: str, rng: GodotRng, dep: dict[str, Any], room: int) -> dict[str, Any]:
    p: dict[str, Any] = {"id": pid, "type": kind, "room": room}
    if kind == "offerings":
        local = LOCAL_ITEMS[rng.randi_range(0, len(LOCAL_ITEMS) - 1)]
        need = str(dep["needs"]["item"])
        p["title"] = "The Two Offerings"
        # the imported item is shown to the niche and kept: several dungeons may depend on the same source
        p["slots"] = [{"id": pid + "_s0", "item": local}, {"id": pid + "_s1", "item": need, "keep": True}]
        p["items"] = [local]
        p["clue"] = "Two niches, two shapes cut into the stone. One shape is in this room. The other was made somewhere else — %s." % _source_hint(dep)
    elif kind == "exchange":
        fodder = LOCAL_ITEMS[rng.randi_range(0, len(LOCAL_ITEMS) - 1)]
        p["title"] = "Fair Exchange"
        p["pedestal"] = pid + "_ped"
        p["gives"] = "iron_key"
        p["accepts"] = list(LOCAL_ITEMS)
        p["items"] = [fodder]
        p["clue"] = "The key sits on a plate that hums. Lift it and the door seals. Something else of weight must take its place."
    elif kind == "switch_chain":
        order = [0, 1, 2]
        _shuffle(order, rng)
        p["title"] = "The Switch Chain"
        p["levers"] = [pid + "_l0", pid + "_l1", pid + "_l2"]
        p["order"] = order
        p["clue"] = "Three levers. Scratched beside them: '%s'. A wrong pull resets them all." % _order_words(order)
        p["n"] = 3
    elif kind == "plate_hold":
        p["title"] = "Hold the Plate"
        p["plate"] = pid + "_plate"
        p["items"] = ["grey_stone"]
        p["clue"] = "A plate in the floor. Stand on it and the door grinds open; step off and it slams. Something has to stay behind."
    elif kind == "timed_gate":
        p["title"] = "The Timed Gate"
        p["lever"] = pid + "_lever"
        p["steps"] = 9
        p["clue"] = "Pull the lever and the gate lifts — and counts. Nine steps, no more. Then it drops."
    elif kind == "mosaic":
        order = [0, 1, 2, 3]
        _shuffle(order, rng)
        p["title"] = "The Mosaic Floor"
        p["tiles"] = 4
        p["order"] = order
        p["clue"] = "Four coloured stones set in the floor. The mural says: %s. Tread them so, or start again." % _order_words(order)
    elif kind == "magic_target":
        spell = WORLD_SPELLS[rng.randi_range(0, len(WORLD_SPELLS) - 1)]
        t = SPELL_TARGETS[spell]
        p["title"] = "The Room Answers Magic"
        p["target"] = pid + "_target"
        p["spell"] = spell
        p["desc"] = t[0]
        p["prompt"] = t[1]
        p["result"] = t[2]
        p["clue"] = "The way on is blocked by %s. No lever. No key. This room wants a wizard." % t[0]
    elif kind == "two_levers":
        p["title"] = "Left Lever, Right Lever"
        p["levers"] = [pid + "_left", pid + "_right"]
        p["correct"] = rng.randi_range(0, 1)
        liar = rng.randi_range(0, 1) == 0
        said = p["correct"] if not liar else 1 - p["correct"]
        p["liar"] = liar
        p["clue"] = "A carved face says: 'Pull the %s.' Beneath it, in another hand: '%s'" % (
            "left" if said == 0 else "right", "The face lies." if liar else "The face is honest, for once.")
        p["wrong_enemy"] = "flame_imp"
    return p
