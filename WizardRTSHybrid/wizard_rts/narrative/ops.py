"""The wizard ops the narrative layer adds to `story.WIZARD_OPS` (execution plan B.2 to B.4): duel reports, closing a conversation, the opening."""

from __future__ import annotations

from typing import Any

from wizard_rts.narrative import campaign, conversation, duel_lease, tutorial, wizard

OPS = ("duel_resolve", "duel_checkpoint", "end_talk", "opening_done", "journal", "call_out", "inspect_building", "inspect_person", "scene_next", "scene_choose", "resurrect", "pest_fight",
       "trial_enter", "trial_move", "trial_interact", "trial_choose", "trial_leave", "trial_view")
FOUGHT = ("victory", "defeat", "clash", "stalemate")


def handle(world: Any, message: dict[str, Any]) -> dict[str, Any]:
    if "narrative" not in world.__dict__:
        return {"status": "rejected", "reason": "no_narrative"}
    op = str(message.get("op", ""))
    if op == "duel_checkpoint":
        return duel_lease.checkpoint(world, str(message.get("duel_id", "")), dict(message.get("checkpoint", {})))
    if op == "duel_resolve":
        return resolve(world, message)
    if op == "end_talk":
        return {"status": "ok", "ended": conversation.end(world, str(message.get("npc", "")) or None, str(message.get("reason", "closed")))}
    if op == "call_out":
        return conversation.call_out(world, str(message.get("npc", "")))
    if op == "scene_next":
        out = campaign.scene_next(world)
        if "duel_lease" in out:
            out["duel_lease"]["payload"]["duel"]["speaker"] = ""
        return out
    if op == "scene_choose":
        return campaign.scene_choose(world, str(message.get("choice", "")))
    if op == "inspect_person":
        return conversation.inspect_person(world, str(message.get("npc", "")))
    if op == "inspect_building":
        return conversation.inspect_building(world, str(message.get("building", "")))
    if op == "opening_done":
        wizard.wiz(world)["opening_seen"] = True
        return {"status": "ok"}
    if op == "journal":
        return {"status": "ok", "journal": tutorial.snapshot(world)}
    if op == "resurrect":
        from wizard_rts.narrative import mortality

        return mortality.resurrect_begin(world, mortality.me(world), str(message.get("target", "")))
    if op == "pest_fight":
        from wizard_rts.narrative import pests

        return pests.fight(world, str(message.get("target", "")))
    if op.startswith("trial_"):
        from wizard_rts.trial import run as trial

        if op == "trial_enter":
            return trial.enter(world)
        if op == "trial_move":
            return trial.move(world, int(message.get("dx", 0)), int(message.get("dy", 0)), message.get("facing"))
        if op == "trial_interact":
            return trial.interact(world, str(message.get("entity", "")))
        if op == "trial_choose":
            return trial.choose(world, str(message.get("entity", "")), str(message.get("choice", "")))
        if op == "trial_leave":
            return trial.leave(world)
        if op == "trial_view":
            return {"status": "ok", "view": trial.view(world)}
    return {"status": "rejected", "reason": "unknown_op"}


def resolve(world: Any, message: dict[str, Any]) -> dict[str, Any]:
    """Godot reports a finished duel: verify it, record it, and let the teacher answer (`follow_up` is the next dialogue to show)."""
    lid = str(message.get("duel_id", ""))
    rec = world.dmb.leases.get(lid)
    if rec is None or rec.get("kind") != duel_lease.KIND:
        return {"status": "rejected", "reason": "missing_duel"}
    if str(message.get("outcome", "")) not in FOUGHT:  # fled, closed, or anything that is not a finished duel: the lesson does not count
        out = duel_lease.abandon(world, str(message.get("outcome", "abandoned")))
        if rec["purpose"] == duel_lease.LETHAL:
            return out  # leaving the stranger's duel was the end of the apprentice (campaign.on_duel_void already ran)
        pid = rec.get("speaker") or tutorial.state(world)["teacher"]
        out["follow_up"] = {"status": "ok", "npc": pid, "name": world.dmb.people[pid]["name"], "lines": ["Leaving so soon? Come back when you are ready."], "choices": []} if pid else None
        return out
    out = duel_lease.resolve(world, lid, message)
    if out["status"] == "resolved":
        if rec["purpose"] == duel_lease.LETHAL:
            out["campaign"] = campaign.on_duel_resolved(world, rec, out)  # a victory goes on; anything else ends the game (decided in campaign.py)
        elif str(rec["purpose"]).startswith("pest:"):
            from wizard_rts.narrative import pests

            out["pest"] = pests.on_duel_resolved(world, rec, out)
        elif str(rec["purpose"]).startswith("trial:"):
            from wizard_rts.trial import run as trial

            out["trial"] = trial.on_duel_resolved(world, rec, out)
        else:
            out["follow_up"] = tutorial.on_duel_resolved(world, rec, out)
    return out
