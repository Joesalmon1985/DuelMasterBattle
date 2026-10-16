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

from wizard_rts.narrative import checks, config, duel_lease, events, ledger, personas, wizard

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


def _fact_ok(facts: dict[str, Any], cond: dict[str, Any]) -> bool:
    v = facts.get(cond["name"])
    if v is None:
        return False
    if "gte" in cond and not (v >= cond["gte"]):
        return False
    if "lte" in cond and not (v <= cond["lte"]):
        return False
    if "eq" in cond and v != cond["eq"]:
        return False
    if cond.get("truthy") and not v:
        return False
    if cond.get("falsy") and v:
        return False
    return True


def holds(world: Any, template: str, when: dict[str, Any] | None, ctx: dict[str, Any] | None = None) -> bool:
    """A variant's or choice's condition: flags of this template (`requires`/`forbids`), lessons, the unlock, a quest's state, and facts about the
    speaker and the world (`facts`: [{name, gte|lte|eq|truthy|falsy}], read from the simulation by `occupations.facts_for`)."""
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
    if "quest" in when:
        from wizard_rts.narrative import quests

        if quests.status(world, when["quest"]["id"]) not in when["quest"]["in"]:
            return False
    ctx = ctx or {}
    facts = ctx.get("facts", {})
    if not all(_fact_ok(facts, c) for c in when.get("facts", [])):
        return False
    if "role" in when and facts.get("role") not in when["role"]:
        return False
    return _holds_narrative(world, template, when, ctx)


def _holds_narrative(world: Any, template: str, when: dict[str, Any], ctx: dict[str, Any]) -> bool:
    """The conditions that read the apprentice and the campaign: `stage`, `knows` (what the speaker knows of the attack), `persona`, `relationship`,
    `aspect`, `player_worldview`, `fact`/`not_fact` (what the apprentice has learned) and `check` (the state of an earlier check with this person)."""
    pid = ctx.get("speaker_pid")
    if "stage" in when or "knows" in when:
        from wizard_rts.narrative import campaign

        if "stage" in when and campaign.stage(world) not in when["stage"]:
            return False
        if "knows" in when and campaign.knowledge(world, pid) not in when["knows"]:
            return False
    if "persona" in when:
        if not pid or pid not in world.dmb.people:
            return False
        p = personas.persona(world, pid)
        spec = when["persona"]
        if "primary" in spec and p["primary"] not in spec["primary"] or "secondary" in spec and p["secondary"] not in spec["secondary"]:
            return False
        if "any" in spec and p["primary"] not in spec["any"] and p["secondary"] not in spec["any"]:
            return False
        if "trait" in spec and not set(spec["trait"]) & set(p["traits"]):
            return False
        if "mentor" in spec and p["mentor"] not in spec["mentor"] or "magic" in spec and p["magic"] not in spec["magic"]:
            return False
    if "relationship" in when:
        r = checks.relationship(world, pid)
        rel = when["relationship"]
        if "gte" in rel and r < rel["gte"] or "lte" in rel and r > rel["lte"]:
            return False
    if "aspect" in when and checks.scores(world)[when["aspect"]["id"]] < when["aspect"]["gte"]:
        return False
    if "player_worldview" in when and wizard.worldview_primary(world) not in when["player_worldview"]:
        return False
    if any(not wizard.knows_fact(world, f) for f in when.get("fact", [])) or any(wizard.knows_fact(world, f) for f in when.get("not_fact", [])):
        return False
    if "check" in when:
        prior = checks.table(world).get(checks.key(ctx, when["check"]["id"]))
        state = "untried" if prior is None else ("passed" if prior["passed"] else "failed")
        if state != when["check"]["state"]:
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
    return {"duel_lease": r}


def _note(world: Any, ctx: dict, eff: dict) -> dict:
    wizard.wiz(world)["journal_notes"].append({"game_ms": int(world.dmb.clock.get("game_ms", 0)), "text": eff["text"].format_map(placeholders(ctx)),
                                               "source": ctx["template"]})
    return {}


def _aspect(world: Any, ctx: dict, eff: dict) -> dict:
    checks.change_once(world, eff["aspect"], int(eff["delta"]), ctx["_key"])
    return {}


def _worldview(world: Any, ctx: dict, eff: dict) -> dict:
    wizard.apply_worldview_choice(world, ctx["_key"], eff["code"])
    return {}


def _relationship(world: Any, ctx: dict, eff: dict) -> dict:
    pid = ctx.get("speaker_pid")
    if eff.get("who"):  # another member of the quest's cast (the judge's decision moves the cutter's and the planter's opinion of the apprentice)
        from wizard_rts.narrative import quests

        bound = (quests.rec(world, ctx["template"]) or {}).get("bindings", {}).get(eff["who"])
        pid = bound["pid"] if bound else None
    if pid in world.dmb.people:
        bump_relationship(world, pid, int(eff["delta"]))
    return {}


def _fact(world: Any, ctx: dict, eff: dict) -> dict:
    wizard.learn_fact(world, eff["id"])
    return {}


def bump_relationship(world: Any, pid: str, delta: int) -> int:
    from sim.dmb.people.registry import PeopleService

    cur = checks.relationship(world, pid)
    PeopleService(world.dmb).set_relationship(pid, checks.actor(world), cur + delta)
    return checks.relationship(world, pid)


def _ledger(world: Any, ctx: dict, eff: dict) -> dict:
    """Count a behaviour (`key`) for the world and for the wizard acting now: what people say later reads it back as a fact."""
    from wizard_rts.narrative import mortality, party

    ledger.bump(world, str(eff["key"]), seat=mortality.me(world) if party.order(world) else None, n=int(eff.get("n", 1)))
    return {}


def _ware_delta(world: Any, ctx: dict, eff: dict) -> dict:
    """A ware leaves (n < 0) or reaches (n > 0) the home settlement's warehouse through the economy's own move, into or out of the `narrative:consumed`
    bin, so the ware ledger still balances: the mason's granite, the mentor's log. Nothing is created from nothing."""
    from wizard_rts import economy
    from wizard_rts.narrative import pests

    found = pests.home(world)
    if found is None:
        return {"ware_error": "no_home"}
    _sid, b = found
    good, n = str(eff["good"]), int(eff.get("n", -1))
    ok = economy.move_good(world, b["id"], "narrative:consumed", good, -n) if n < 0 else economy.move_good(world, "narrative:consumed", b["id"], good, n)
    events.log(world, "ware_delta", good=good, n=n, ok=ok, template=ctx.get("template", ""))
    return {"ware": {"good": good, "n": n, "ok": ok}}


def _pests_complained(world: Any, ctx: dict, eff: dict) -> dict:
    from wizard_rts.narrative import mortality, pests

    pests.complained(world, mortality.me(world))
    return {}


def _challenge_stranger(world: Any, ctx: dict, eff: dict) -> dict:
    """The apprentice answers the stranger's judgement with a challenge: the scene's end opens the lethal duel for this wizard alone (campaign.scene_next)."""
    wizard.wiz(world)["lethal"] = "challenged"
    return {}


EFFECTS: dict[str, Callable[[Any, dict, dict], dict]] = {"learn_spell": _learn, "complete_lesson": _lesson, "begin_duel": _begin_duel, "journal_note": _note,
                                                         "aspect": _aspect, "worldview": _worldview, "relationship": _relationship, "fact": _fact, "ledger": _ledger,
                                                         "challenge_stranger": _challenge_stranger, "ware_delta": _ware_delta, "pests_complained": _pests_complained}
REPEATABLE = {"begin_duel", "ledger", "pests_complained"}  # every other effect is applied once per (template, id)


def apply(world: Any, ctx: dict[str, Any], rid: str, block: dict[str, Any]) -> dict[str, Any]:
    """Apply a variant's or choice's `sets`, `clears` and `effects`. Once-only effects keep a receipt under `rid`."""
    t = ctx["template"]
    extras: dict[str, Any] = {}
    for f in block.get("sets", []):
        set_flag(world, t, f)
    for f in block.get("clears", []):
        flags(world, t).pop(f, None)
    receipts = state(world)["receipts"]
    pid = ctx.get("speaker_pid")
    for i, eff in enumerate(block.get("effects", [])):
        # global by default (the quests); `"scope": "person"` makes the receipt per speaker (the same line said by two people pays twice, once each)
        key = f"{t}/{pid}/{rid}/{i}" if eff.get("scope") == "person" and pid else f"{t}/{rid}/{i}"
        if eff["kind"] not in REPEATABLE:
            if key in receipts:
                continue
            receipts[key] = int(world.dmb.clock.get("game_ms", 0))
        extras.update(EFFECTS[eff["kind"]](world, {**ctx, "_key": key}, eff))
    return extras


def run_block(world: Any, ctx: dict[str, Any], rid: str, block: dict[str, Any]) -> dict[str, Any]:
    """Run one authored block (a choice, a topic, a scene response): its own `sets`/`effects` and lines, then, if it has a `check`, the real Aspect
    check and the `pass`, `fail` or `blocked` branch (each with lines, `sets` and `effects`). Effects are once-only, so repeating it pays nothing twice."""
    t = ctx["template"]
    extras = apply(world, ctx, rid, block)
    lines = _fmt(block.get("lines", []), ctx, world, t)
    out: dict[str, Any] = {"lines": lines, "extras": extras, "check": None, "ends": bool(block.get("ends"))}
    if "check" in block:
        res = checks.run(world, ctx, rid, block["check"])
        branch_id = "blocked" if res["blocked"] else ("pass" if res["passed"] else "fail")
        branch = block.get(branch_id) or {"lines": ["You have nothing new to add."] if branch_id == "blocked" else []}
        extras.update(apply(world, ctx, f"{rid}:{branch_id}", branch))
        out["lines"] = lines + _fmt(branch.get("lines", []), ctx, world, t)
        out["ends"] = out["ends"] or bool(branch.get("ends"))
        out["check"] = {"aspect": res["aspect"], "label": checks.LABELS[res["aspect"]], "passed": res["passed"], "blocked": res["blocked"], "score": res["score"],
                        "evidence": res["evidence"], "relationship": res["relationship"], "total": res["total"], "threshold": res["threshold"], "again": res["again"]}
    return out


# ------------------------------------------------------------------ replies that express a belief (worldview responses)

def response_choices(world: Any, ctx: dict[str, Any], prefix: str, responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The apprentice's possible answers to what was just said, minus those the speaker has already been given an answer to (one answer per topic)."""
    if responded(world, ctx, prefix):
        return []
    out = []
    for r in responses:
        if not holds(world, ctx["template"], r.get("when"), ctx):
            continue
        rid = f"{prefix}/{r['id']}"
        text = r["text"].format_map(placeholders(ctx))
        avail = True
        if "check" in r:
            text = f"{checks.label(r['check'])} {text}"
            avail = not checks.retry_blocked(world, ctx, rid, r["check"])
        out.append({"id": f"resp:{prefix}:{r['id']}", "text": text, "available": avail})
    return out


def responded(world: Any, ctx: dict[str, Any], prefix: str) -> bool:
    return f"{ctx.get('speaker_pid')}/{prefix}" in state(world).setdefault("responded", {})


def respond(world: Any, ctx: dict[str, Any], prefix: str, responses: list[dict[str, Any]], resp_id: str) -> dict[str, Any] | None:
    """The apprentice gives one answer. A `worldview` code applies the established delta once for this answer; the speaker takes it according to their own
    persona (agree, neutral, disagree: `personas.affinity`), which picks their reply from `reply` and moves their opinion of the apprentice."""
    r = next((x for x in responses if x["id"] == resp_id and holds(world, ctx["template"], x.get("when"), ctx)), None)
    if r is None or responded(world, ctx, prefix):
        return None
    rid = f"{prefix}/{r['id']}"
    block = dict(r)
    if "worldview" in r:
        block["effects"] = list(r.get("effects", [])) + [{"kind": "worldview", "code": r["worldview"], "scope": "global"}]
    out = run_block(world, ctx, rid, block)
    pid = ctx.get("speaker_pid")
    state(world).setdefault("responded", {})[f"{pid}/{prefix}"] = resp_id
    reply_key = "neutral"
    if "worldview" in r and pid in world.dmb.people:
        reply_key = personas.reaction(personas.persona(world, pid), r["worldview"])
        rel = {"agree": 4, "neutral": 0, "disagree": -3}[reply_key]
        key = f"rel/{pid}/{rid}"
        if rel and key not in state(world)["receipts"]:
            state(world)["receipts"][key] = int(world.dmb.clock.get("game_ms", 0))
            bump_relationship(world, pid, rel)
    reply = r.get("reply", {})
    lines = reply.get(reply_key) or reply.get("neutral") or reply.get("default") or []
    out["reply"] = _fmt(lines, ctx, world, ctx["template"])
    out["reaction"] = reply_key
    return out


# ------------------------------------------------------------------ talking

def _node(world: Any, template: str, speaker: str) -> dict[str, Any]:
    nodes = load(template)["speakers"][speaker]["nodes"]
    return nodes[state(world)["node"].get(f"{template}/{speaker}", HUB)]


class _Env(dict):
    def __missing__(self, key: str) -> str:
        return "..."  # an unknown placeholder never crashes a conversation (test_narrative_content checks every line against the known names)


def placeholders(ctx: dict[str, Any]) -> dict[str, Any]:
    return _Env({"name": ctx["name"], **ctx.get("cast", {}), **ctx.get("facts", {})})


def _fmt(lines: list[Any], ctx: dict[str, Any], world: Any = None, template: str = "") -> list[str]:
    """Format lines with the placeholders (the speaker's name, the cast's names, facts about the world). A line may be {"text", "when"} and is then
    only spoken while its condition holds (this is how a line stays true to the world)."""
    env = placeholders(ctx)
    out = []
    for l in lines:
        if isinstance(l, dict):
            if world is not None and not holds(world, template, l.get("when"), ctx):
                continue
            l = l["text"]
        out.append(l.format_map(env))
    return out


def view(world: Any, ctx: dict[str, Any]) -> dict[str, Any]:
    """The speaker's current node: the entry lines of its first matching variant (applying it once) and the choices that are open."""
    t, sp = ctx["template"], ctx["speaker"]
    node = _node(world, t, sp)
    lines: list[str] = []
    extras: dict[str, Any] = {}
    for v in node.get("variants", []):
        if holds(world, t, v.get("when"), ctx):
            lines = _fmt(v["lines"], ctx, world, t)
            extras = apply(world, ctx, f"v:{v['id']}", v) if "id" in v else {}
            break
    choices = []
    for c in node.get("choices", []):
        if not holds(world, t, c.get("when"), ctx) or (c.get("once") and has(world, t, "done:" + c["id"])):
            continue
        text, avail = c["text"].format_map(placeholders(ctx)), True
        if "check" in c:
            text = f"{checks.label(c['check'])} {text}"
            avail = not checks.retry_blocked(world, ctx, f"c:{c['id']}", c["check"])
        choices.append({"id": c["id"], "text": text, "available": avail})
    return {"lines": lines, "choices": choices, "extras": extras}


def talk(world: Any, ctx: dict[str, Any]) -> dict[str, Any]:
    state(world)["node"][f"{ctx['template']}/{ctx['speaker']}"] = HUB
    return view(world, ctx)


def choose(world: Any, ctx: dict[str, Any], choice_id: str) -> dict[str, Any] | None:
    t, sp = ctx["template"], ctx["speaker"]
    node = _node(world, t, sp)
    choice = next((c for c in node.get("choices", []) if c["id"] == choice_id and holds(world, t, c.get("when"), ctx)), None)
    if choice is None or (choice.get("once") and has(world, t, "done:" + choice_id)):
        return None
    if "check" in choice and checks.retry_blocked(world, ctx, f"c:{choice['id']}", choice["check"]):
        return None  # nothing has changed since the last failed attempt
    ran = run_block(world, ctx, f"c:{choice['id']}", choice)
    extras = ran["extras"]
    if choice.get("once"):
        set_flag(world, t, "done:" + choice_id)
    state(world)["node"][f"{t}/{sp}"] = choice.get("goto", HUB)
    ends = ran["ends"] or bool(extras.get("duel_lease"))  # the conversation's end is declared by the data (or by a duel starting), never guessed from a label
    out = view(world, ctx) if not ends else {"lines": [], "choices": [], "extras": {}}
    out["text"] = "\n".join(ran["lines"])
    out["extras"] = {**extras, **out["extras"]}
    out["ends"] = ends
    if ran["check"]:
        out["check"] = ran["check"]
    return out
