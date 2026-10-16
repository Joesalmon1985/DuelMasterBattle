"""Aspect checks in conversation: the existing `AspectService` (`sim/dmb/narrative/aspects.py`) used as it is, never a second skill system.

A choice with a `check` is decided by the real Aspect score of the apprentice (`player`), plus the evidence the apprentice has gathered
(`evidence`: [{when, mod}] summed and capped at 2 by the service), plus the speaker's relationship band to the apprentice (-1, 0, +1), against a
named threshold (easy 2, demanding 4, exceptional 6). Nothing is random: the same state gives the same result. A failed check records a retry
fingerprint of (aspect, score, evidence, relationship, context); asking again with nothing new is *blocked* (the service's rule), and anything that
really changed (a higher score, new evidence, a better relationship) is a new attempt. The outcome of the latest attempt is kept so a repeated
conversation shows what happened and never pays an effect twice (effects carry receipts, `graph.apply`).
"""

from __future__ import annotations

from typing import Any

from sim.dmb.narrative.aspects import AspectService

from wizard_rts.narrative import config, wizard

ACTOR = "player"  # the host's wizard; every other wizard acts under its seat id (party.as_player sets `narrative["actor"]`)


def actor(world: Any) -> str:
    return world.narrative.get("actor", ACTOR)
LABELS = {"reason": "Reason", "empathy": "Empathy", "authority": "Authority", "guile": "Guile", "resolve": "Resolve", "curiosity": "Curiosity", "wonder": "Wonder"}


def service(world: Any) -> AspectService:
    svc = AspectService(world.dmb)
    w = wizard.wiz(world)
    if not w.get("aspects_init"):  # an apprentice is not a blank: the starting scores come from the configuration, once
        scores = svc.ensure_scores(actor(world))
        for aspect, value in sorted(config.get("campaign", "start_aspects", {}).items()):
            scores[aspect] = max(0, min(5, int(value)))
        svc._store()["scores"][actor(world)] = scores
        w["aspects_init"] = True
    return svc


def scores(world: Any) -> dict[str, int]:
    return service(world).ensure_scores(actor(world))


def table(world: Any) -> dict[str, Any]:
    return world.narrative.setdefault("checks", {})


def relationship(world: Any, pid: str | None) -> int:
    if not pid or pid not in world.dmb.people:
        return 0
    return int(world.dmb.people[pid].get("relationship_map", {}).get(actor(world), 0))


def _evidence(world: Any, ctx: dict[str, Any], check: dict[str, Any]) -> tuple[int, list[str]]:
    from wizard_rts.narrative import graph

    mod, hits = 0, []
    for i, e in enumerate(check.get("evidence", [])):
        if graph.holds(world, ctx["template"], e.get("when"), ctx):
            mod += int(e.get("mod", 1))
            hits.append(e.get("id", str(i)))
    return min(2, mod), hits


def key(ctx: dict[str, Any], rid: str) -> str:
    return f"{ctx['template']}/{ctx.get('speaker_pid', '')}/{rid}"


def run(world: Any, ctx: dict[str, Any], rid: str, check: dict[str, Any]) -> dict[str, Any]:
    """Decide the check with the real rules. Result: passed, blocked (a repeat with nothing new), and the figures the player is shown."""
    svc = service(world)
    ev, hits = _evidence(world, ctx, check)
    k = key(ctx, rid)
    prior = table(world).get(k)
    if prior is not None and prior["passed"]:
        return {**prior, "again": True, "blocked": False}  # a passed check stays passed: nothing is rolled twice
    res = svc.check(check["aspect"], threshold=check.get("threshold", "demanding"), evidence_mod=ev, relationship_score=relationship(world, ctx.get("speaker_pid")),
                    quest_predicates={"check": k, "evidence": hits}, actor_id=actor(world))
    out = {"passed": bool(res["passed"]), "blocked": bool(res.get("blocked")), "aspect": res["aspect_id"], "score": res["score"], "evidence": res["evidence_mod"],
           "relationship": res["relationship_mod"], "total": res["total"], "threshold": res["threshold"], "game_ms": int(world.dmb.clock.get("game_ms", 0)), "again": False}
    if not out["blocked"]:
        table(world)[k] = {kk: out[kk] for kk in out if kk not in ("blocked", "again")}
    return out


def retry_blocked(world: Any, ctx: dict[str, Any], rid: str, check: dict[str, Any]) -> bool:
    """Would asking again change nothing? (Read-only: the same fingerprint the service would compute.)"""
    k = key(ctx, rid)
    prior = table(world).get(k)
    if prior is None or prior["passed"]:
        return False
    svc = service(world)
    ev, hits = _evidence(world, ctx, check)
    from sim.dmb.people.registry import relationship_band

    fp = svc.retry_fingerprint(aspect_id=check["aspect"], score=svc.get_score(check["aspect"], actor_id=actor(world)), evidence_mod=ev,
                               relationship_mod=relationship_band(relationship(world, ctx.get("speaker_pid"))), quest_predicates={"check": k, "evidence": hits})
    return fp in svc._store()["failed_fingerprints"]


def label(check: dict[str, Any]) -> str:
    return f"[{LABELS[check['aspect']]}]"


def change_once(world: Any, aspect: str, delta: int, change_id: str) -> dict[str, Any]:
    return service(world).apply_change_once(aspect, delta, change_id=change_id, actor_id=actor(world))
