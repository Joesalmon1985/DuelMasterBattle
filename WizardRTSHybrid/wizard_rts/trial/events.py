"""The Trial's choice events (the book's decision points), ported from the legacy `story_events.gd` to the host: each is a function of the run and the
seat that returns a prompt with choices, or applies a choice. Everything is run state (`trial/run.py`), shared by every wizard in the run: the first
to cross the pit decides Throm's state for both; the riddle is answered once a run. Conditions are the legacy's: `wounded` (one cast fewer in the next
duel) and `poisoned` (recorded; the board's cast window is not part of the verified rules, so it is a note, not a handicap)."""

from __future__ import annotations

from typing import Any

from wizard_rts.narrative import events as nlog
from wizard_rts.narrative import ledger, wizard

Prompt = dict[str, Any]


def _opt(cid: str, text: str) -> dict[str, str]:
    return {"id": cid, "text": text}


def _flag(run: dict[str, Any], name: str, on: bool = True) -> None:
    if on:
        run["flags"][name] = True
    else:
        run["flags"].pop(name, None)


def has(run: dict[str, Any], name: str) -> bool:
    return bool(run["flags"].get(name))


def wound(world: Any, seat_rec: dict[str, Any], why: str) -> None:
    if "wounded" not in seat_rec["conditions"]:
        seat_rec["conditions"].append("wounded")
    wizard.wiz(world)["wounded"] = True
    nlog.log(world, "trial_wounded", why=why)


# ------------------------------------------------------------------ the old man's riddle (p.382; the number itself is unverified: the puzzle is self-contained)

def statue_riddle(world: Any, run: dict[str, Any], seat: dict[str, Any], choice: str | None) -> Prompt:
    if has(run, "riddle_answered"):
        if has(run, "riddle_right"):
            return {"text": "You read. Good. The lion-thing below hates the light for the same reason.", "choices": []}
        return {"text": "The stone keeps its own counsel. So do I, now.", "choices": []}
    if choice is None:
        return {"text": "A knight went first. She counted the steps from the door to this stone; she said it aloud so I would remember. Half as many again as the years I have stood here, and I have stood here a hundred.\n\nHow many steps did she count?",
                "choices": [_opt("100", "One hundred"), _opt("150", "One hundred and fifty"), _opt("200", "Two hundred")]}
    if choice not in ("100", "150", "200"):
        return {"status": "rejected", "reason": "choice_unavailable"}
    _flag(run, "riddle_answered")
    _flag(run, "riddle_answer_" + choice)
    if choice == "150":
        _flag(run, "riddle_right")
        wizard.learn_fact(world, "manticore_hates_light")
        ledger.bump(world, "trial_riddles_right", seat=seat["seat"])
        return {"text": "A hundred and fifty. She could count; it did not save her.\n\nSo I will tell you one thing for it. The lion-thing that guards the last door hates the light. Remember that when you weave against it.\n\nBeside him stands a knight in White Road armour, turned to stone mid-step. Serra went first. This is where first got her.", "choices": []}
    wound(world, seat, "riddle")
    return {"text": "No. Listen better; the Trial will not ask twice.\n\nHe raps your knuckles with his staff, hard enough to numb the hand. You are hurt: one cast fewer in your next duel.\n\nBeside him stands a knight in White Road armour, turned to stone mid-step. Serra went first. This is where first got her.", "choices": []}


# ------------------------------------------------------------------ Throm at the pit (p.22, 63, 184, 311, 323, 149)

def throm_pit(world: Any, run: dict[str, Any], seat: dict[str, Any], choice: str | None) -> Prompt:
    if has(run, "pit_crossed"):
        state = run["throm"]
        line = {"uneasy_ally": "The rope is tied off below. Throm went down first; the knots are his. Climb when you like.",
                "betrayed": "The rope hangs slack into the dark. Nobody is holding it. You crossed alone, and you will remember this.",
                "wounded": "The rope is tied off below. Throm is down there somewhere, favouring one arm."}.get(state, "The pit is crossed. The rope is tied off.")
        return {"text": line, "choices": []}
    if choice is None:
        return {"text": "A pit cuts the corridor. Far below, water moves. The far edge is a long jump, or a rope's length, if someone holds the rope.\n\nThrom: \"I hold the rope, or you hold it for me. Or we jump it together, and laugh.\"",
                "choices": [_opt("lowered", "Let him lower you"), _opt("lower_him", "Offer to lower him"), _opt("jump", "Jump together"), _opt("alone", "Climb down alone")]}
    if choice == "alone":
        wound(world, seat, "pit")
        _flag(run, "pit_fell")
        _flag(run, "pit_ally")
        run["throm"] = "uneasy_ally"
        lost = "torch" in seat["pockets"]
        if lost:
            seat["pockets"].remove("torch")
            _flag(run, "torch_lost")
        _flag(run, "pit_crossed")
        return {"text": "You take the wall alone. Halfway, the wall takes you. You land in the shallows, hard. You are hurt: one cast fewer in your next duel." + (" Your torch hisses out in the water and goes to the bottom." if lost else "") + "\n\nThrom: \"Hah. Wait there; I am coming down the sensible way.\"", "choices": []}
    if choice == "lower_him":
        _flag(run, "pit_throm_below")
        return {"text": "Throm: \"...Throm. My name is Throm. Take the rope, then. Tightly.\"\n\nYou lower Throm by the rope. He looks very small, and then he waves you off the edge.",
                "choices": [_opt("after_him", "Climb down after him"), _opt("leave_him", "Leave him")]}
    if choice in ("after_him", "leave_him"):
        if not has(run, "pit_throm_below"):
            return {"status": "rejected", "reason": "choice_unavailable"}
        _flag(run, "pit_crossed")
        if choice == "leave_him":
            _flag(run, "pit_betrayed")
            run["throm"] = "betrayed"
            ledger.bump(world, "trial_betrayals", seat=seat["seat"])
            return {"text": "You cross alone. Behind you, the rope goes still.\n\nYou will remember this.", "choices": []}
        _flag(run, "pit_ally")
        run["throm"] = "uneasy_ally"
        return {"text": "Throm: \"Hah. An honest villain would have left. Come on.\"", "choices": []}
    if choice == "jump":
        wound(world, seat, "pit")
        _flag(run, "pit_jump")
        _flag(run, "pit_ally")
        run["throm"] = "uneasy_ally"
        _flag(run, "pit_crossed")
        return {"text": "You jump together, land hard, and laugh until it hurts.\n\n(It hurts. You are hurt: one cast fewer in your next duel.)", "choices": []}
    if choice == "lowered":
        _flag(run, "pit_ally")
        run["throm"] = "uneasy_ally"
        _flag(run, "pit_crossed")
        return {"text": "Throm: \"Down you go, villager. I have held worse.\"", "choices": []}
    return {"status": "rejected", "reason": "choice_unavailable"}


# ------------------------------------------------------------------ the black book's vial (p.138)

def black_book(world: Any, run: dict[str, Any], seat: dict[str, Any], choice: str | None) -> Prompt:
    if has(run, "potion_used"):
        return {"text": "The vial is empty now.", "choices": []}
    if choice is None:
        return {"text": "Throm: \"Don't. Whatever it is, don't.\"", "choices": [_opt("drink", "Drink it"), _opt("rub", "Rub it on your wounds"), _opt("leave", "Leave it")]}
    if choice == "drink":
        _flag(run, "potion_used")
        if "poisoned" not in seat["conditions"]:
            seat["conditions"].append("poisoned")
        return {"text": "It tastes of ink and lightning. Your hands shake. You are poisoned: your next casts will come slower than you would like.", "choices": []}
    if choice == "rub":
        _flag(run, "potion_used")
        if "wounded" in seat["conditions"]:
            seat["conditions"].remove("wounded")
            wizard.wiz(world).pop("wounded", None)
            return {"text": "It burns cold. Where it touches, the skin knits. The hurt is gone.", "choices": []}
        return {"text": "It burns cold. Where it touches, the skin knits a little, though there was nothing much to knit.", "choices": []}
    if choice == "leave":
        return {"text": "You stopper the vial and leave it. Some things stay unknown.", "choices": []}
    return {"status": "rejected", "reason": "choice_unavailable"}


EVENTS = {"statue_riddle": statue_riddle, "throm_pit": throm_pit, "black_book": black_book}
