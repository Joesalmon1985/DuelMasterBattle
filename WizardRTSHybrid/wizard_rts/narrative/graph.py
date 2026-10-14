"""A small dialogue-graph runtime (execution plan B.4's `graph.py` v0): talk and choice nodes with `requires`/`forbids`/`sets` and effects.

A template (`data/narrative/dialogue/<name>.json`) has `speakers`, each with `nodes`. A node has `variants` (the first whose `when` holds gives
the lines shown on entry; a variant with a receipt id applies its `sets`/`clears`/`effects` once) and `choices`. A choice has `when`, `lines`,
`sets`, `clears`, `effects` and an optional `goto` node. Flags live per template in `world.narrative["graph"]`; effects are the narrow, typed,
narrative-only registry below (the world-effect registry arrives in E.5). E.1 replaces this with the full runtime and keeps this API.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from wizard_rts.narrative import config, duel_lease, events, wizard

DIALOGUE = Path(__file__).resolve().parents[1] / "data" / "narrative" / "dialogue"
HUB = "hub"


@lru_cache(maxsize=None)
def load(template: str) -> dict[str, Any]:
    return json.loads((DIALOGUE / f"{template}.json").read_text())


def state(world: Any) -> dict[str, Any]:
    return world.narrative.setdefault("graph", {"flags": {}, "receipts": {}, "node": {}})


def flags(world: Any, template: str) -> dict[str, int]:
    return state(world)["flags"].setdefault(template, {})


def has(world: Any, template: str, flag: str) -> bool:
    return flag in flags(world, template)


def set_flag(world: Any, template: str, flag: str) -> None:
    flags(world, template).setdefault(flag, int(world.dmb.clock.get("game_ms", 0)))


def unlocked(world: Any) -> bool:
    """Dynamic stories unlock when every essential lesson is done OR `unlock_after_ms` of game time has passed (plan 2.4)."""
    essential = config.get("tutorial", "essential", [])
    return all(wizard.lesson_done(world, l) for l in essential) or int(world.dmb.clock.get("game_ms", 0)) >= int(config.get("narrative", "unlock_after_ms", 0))


def holds(world: Any, template: str, when: dict[str, Any] | None) -> bool:
    if not when:
        return True
    f = flags(world, template)
    if any(x not in f for x in when.get("requires", [])) or any(x in f for x in when.get("forbids", [])):
        return False
    if any(not wizard.lesson_done(world, l) for l in when.get("lessons", [])):
        return False
    if any(wizard.lesson_done(world, l) for l in when.get("not_lessons", [])):
        return False
    if "unlocked" in when and bool(when["unlocked"]) != unlocked(world):
        return False
    return True


# ------------------------------------------------------------------ effects: typed, narrative-only, with receipts

def _learn(world: Any, ctx: dict, eff: dict) -> dict:
    wizard.learn(world, list(eff["spells"]), eff.get("weave_size"))
    events.log(world, "spells_learned", spells=wizard.spells(world), weave_size=wizard.wiz(world)["weave_size"])
    return {}


def _lesson(world: Any, ctx: dict, eff: dict) -> dict:
    if wizard.complete_lesson(world, eff["lesson"]):
        events.log(world, "lesson_done", lesson=eff["lesson"])
    return {}


def _begin_duel(world: Any, ctx: dict, eff: dict) -> dict:
    r = duel_lease.begin(world, eff["opponent"], purpose=eff["purpose"], fixed_ward=eff.get("fixed_ward"))
    if r["status"] != "started":
        return {"duel_error": r.get("reason", "")}
    world.narrative["conversations"].pop(ctx["speaker_pid"], None)
    return {"duel_lease": r}


def _note(world: Any, ctx: dict, eff: dict) -> dict:
    wizard.wiz(world)["journal_notes"].append({"game_ms": int(world.dmb.clock.get("game_ms", 0)), "text": eff["text"], "source": ctx["template"]})
    return {}


EFFECTS: dict[str, Callable[[Any, dict, dict], dict]] = {"learn_spell": _learn, "complete_lesson": _lesson, "begin_duel": _begin_duel, "journal_note": _note}
REPEATABLE = {"begin_duel"}  # every other effect is applied once per (template, id)


def apply(world: Any, ctx: dict[str, Any], rid: str, block: dict[str, Any]) -> dict[str, Any]:
    """Apply a variant's or choice's `sets`, `clears` and `effects`. Once-only effects keep a receipt under `rid`."""
    t = ctx["template"]
    extras: dict[str, Any] = {}
    for f in block.get("sets", []):
        set_flag(world, t, f)
    for f in block.get("clears", []):
        flags(world, t).pop(f, None)
    receipts = state(world)["receipts"]
    for i, eff in enumerate(block.get("effects", [])):
        key = f"{t}/{rid}/{i}"
        if eff["kind"] not in REPEATABLE:
            if key in receipts:
                continue
            receipts[key] = int(world.dmb.clock.get("game_ms", 0))
        extras.update(EFFECTS[eff["kind"]](world, ctx, eff))
    return extras


# ------------------------------------------------------------------ talking

def _node(world: Any, template: str, speaker: str) -> dict[str, Any]:
    nodes = load(template)["speakers"][speaker]["nodes"]
    return nodes[state(world)["node"].get(f"{template}/{speaker}", HUB)]


def _fmt(lines: list[str], ctx: dict[str, Any]) -> list[str]:
    return [l.format(name=ctx["name"]) for l in lines]


def view(world: Any, ctx: dict[str, Any]) -> dict[str, Any]:
    """The speaker's current node: the entry lines of its first matching variant (applying it once) and the choices that are open."""
    t, sp = ctx["template"], ctx["speaker"]
    node = _node(world, t, sp)
    lines: list[str] = []
    extras: dict[str, Any] = {}
    for v in node.get("variants", []):
        if holds(world, t, v.get("when")):
            lines = _fmt(v["lines"], ctx)
            extras = apply(world, ctx, f"v:{v['id']}", v) if "id" in v else {}
            break
    choices = [{"id": c["id"], "text": c["text"], "available": True} for c in node.get("choices", []) if holds(world, t, c.get("when"))]
    return {"lines": lines, "choices": choices, "extras": extras}


def talk(world: Any, ctx: dict[str, Any]) -> dict[str, Any]:
    state(world)["node"][f"{ctx['template']}/{ctx['speaker']}"] = HUB
    return view(world, ctx)


def choose(world: Any, ctx: dict[str, Any], choice_id: str) -> dict[str, Any] | None:
    t, sp = ctx["template"], ctx["speaker"]
    node = _node(world, t, sp)
    choice = next((c for c in node.get("choices", []) if c["id"] == choice_id and holds(world, t, c.get("when"))), None)
    if choice is None:
        return None
    extras = apply(world, ctx, f"c:{choice['id']}", choice)
    state(world)["node"][f"{t}/{sp}"] = choice.get("goto", HUB)
    out = view(world, ctx) if not extras.get("duel_lease") else {"lines": [], "choices": [], "extras": {}}
    out["text"] = "\n".join(_fmt(choice.get("lines", []), ctx))
    out["extras"] = {**extras, **out["extras"]}
    return out
