"""The inner voice: the apprentice's own strongest Aspect speaks up at the absurd moments (plan section 3, Disco Elysium's skills that talk back).

`data/narrative/dialogue/inner_voice.json` lists triggers: each has a condition over the same facts the villagers read (the behaviour ledger, the
common facts, the ladder), an Aspect that speaks (or "best": whichever of the apprentice's Aspects is highest), and lines (the first the first time,
`lines_alt` if it ever fires again, which only `repeat: true` triggers may). A trigger fires at most once per world per wizard, never within
`gap_ms` of the last one, never during a duel or a scene, and the ledger counts them (`inner_voice`). The session delivers it to that wizard alone
as a notice of kind `inner_voice`; the client shows it as a card spoken by the Aspect's name.
"""

from __future__ import annotations

from typing import Any

from wizard_rts.narrative import checks, events, graph, ledger, party, wizard

TEMPLATE = "inner_voice"
GAP_MS = 120_000


def bank() -> dict[str, Any]:
    return graph.load(TEMPLATE)


def state(world: Any) -> dict[str, Any]:
    return world.narrative.setdefault("voice", {"said": {}, "last_ms": {}})


def facts(world: Any) -> dict[str, Any]:
    from wizard_rts.narrative import conversation, mortality

    f = {**ledger.facts(world, mortality.me(world)), **conversation.common_facts(world)}
    f["lessons_done"] = len(wizard.wiz(world).get("lessons", {}))
    f["dead"] = 1 if mortality.is_dead(world, mortality.me(world)) else 0
    from wizard_rts.trial import run as trial

    f["in_trial"] = 1 if trial.inside(world, mortality.me(world)) else 0
    return f


def speaker(world: Any, aspect: str) -> str:
    if aspect and aspect != "best":
        return checks.LABELS.get(aspect, aspect.capitalize())
    scores = checks.scores(world)
    best = max(sorted(scores), key=lambda a: scores[a]) if scores else "wonder"
    return checks.LABELS.get(best, best.capitalize())


def _busy(world: Any) -> bool:
    from wizard_rts.narrative import campaign, duel_lease

    return duel_lease.active(world) is not None or campaign.active_scene(world) is not None


def tick(world: Any) -> None:
    """Once a game second, for every present human wizard: the first trigger whose condition holds and that may still speak."""
    from wizard_rts.narrative import mortality

    now = int(world.dmb.clock.get("game_ms", 0))
    st = state(world)
    for seat in (party.players(world, humans_only=True, present_only=True) if party.multi(world) else party.players(world)):
        key = str(seat)
        if now - int(st["last_ms"].get(key, -GAP_MS)) < GAP_MS or _busy(world):
            continue
        f = facts(world)
        said = st["said"].setdefault(key, {})
        ctx = {"template": TEMPLATE, "speaker": "voice", "facts": f, "name": "", "cast": {}}
        for trig in bank()["triggers"]:
            n = int(said.get(trig["id"], 0))
            if n and not trig.get("repeat"):
                continue
            if n >= int(trig.get("max", 2)):
                continue
            if not graph.holds(world, TEMPLATE, trig.get("when"), ctx):
                continue
            banks = [trig["lines"]] + list(trig.get("lines_alt", []))
            lines = graph._fmt(banks[min(n, len(banks) - 1)], ctx, world, TEMPLATE)
            who = speaker(world, trig.get("aspect", "best"))
            said[trig["id"]] = n + 1
            st["last_ms"][key] = now
            ledger.bump(world, "inner_voice", seat=key)
            events.log(world, "inner_voice", seat=key, trigger=trig["id"], aspect=who)
            mortality._announce(world, "inner_voice", to=key, trigger=trig["id"], aspect=who, text="\n\n".join(lines))
            break
