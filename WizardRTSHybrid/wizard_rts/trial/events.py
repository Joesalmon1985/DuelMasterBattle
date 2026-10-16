"""The Trial's choice events (the book's decision points), ported from the legacy `story_events.gd` to the host: each is a function of the run and the
seat that returns a prompt with choices, or applies a choice. Everything is run state (`trial/run.py`), shared by every wizard in the run: the first
to cross the pit decides Throm's state for both; the riddle is answered once a run; the Dwarf's tests are passed once a run. Conditions are the
legacy's: `wounded` (one cast fewer in the next duel) and `poisoned` (recorded; the board's cast window is not part of the verified rules, so it is a
note, not a handicap). A prompt may carry `fight` (an entity id and the enemy to face: the choice began a duel, `run.choose` opens the lease) or
`champion` (the door opened: `run.choose` walks the champion out). The canon status of every branch is in `docs/TRIAL_CANON_STATUS.md`."""

from __future__ import annotations

import random
from typing import Any

from wizard_rts.narrative import events as nlog
from wizard_rts.narrative import ledger, wizard

Prompt = dict[str, Any]
STONE, LIGHT, SHADOW, VINE = 3, 4, 5, 6


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


def _zone_state(run: dict[str, Any], zid: str) -> dict[str, Any]:
    return run["zones"].setdefault(zid, {"taken": [], "defeated": [], "doors": []})


def defeated(run: dict[str, Any], zid: str, eid: str) -> bool:
    return eid in _zone_state(run, zid)["defeated"]


def take_entity(run: dict[str, Any], zid: str, eid: str) -> None:
    """A pickup decided by a choice (the false eye, the false diamond, the chest): taken for everyone once chosen."""
    zs = _zone_state(run, zid)
    if eid not in zs["taken"]:
        zs["taken"].append(eid)
    run["flags"]["picked_" + eid] = True


def _pocket(seat: dict[str, Any], item: str) -> bool:
    from wizard_rts.trial.run import MAX_POCKETS

    if len(seat["pockets"]) >= MAX_POCKETS:
        return False
    seat["pockets"].append(item)
    return True


def _rejected() -> Prompt:
    return {"status": "rejected", "reason": "choice_unavailable"}


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
        return _rejected()
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
            return _rejected()
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
    return _rejected()


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
    return _rejected()


# ------------------------------------------------------------------ the Dwarf Trialmaster: lock-in, the dice, the cobra (p.60, 365, 290, 191, 84; the attack branch 179 is unverified)

def _dice_prompt() -> Prompt:
    return {"text": "Dwarf: \"Two dice in the cup. When they land: the same as eight, less, or more?\"",
            "choices": [_opt("same", "The same as eight"), _opt("less", "Less than eight"), _opt("more", "More than eight")]}


def _cobra_prompt(lead: str) -> Prompt:
    return {"text": (lead + "\n\n" if lead else "") + "Dwarf: \"Last: the basket. Hold its gaze, or snatch it. Choose.\"",
            "choices": [_opt("gaze", "Hold its gaze"), _opt("snatch", "Snatch it")]}


def dwarf_meet(world: Any, run: dict[str, Any], seat: dict[str, Any], choice: str | None) -> Prompt:
    if has(run, "trial_done"):
        return {"text": "Dwarf: \"The way is open. Go, and don't thank me.\"", "choices": []}
    if has(run, "trial_ready"):
        return {"text": "Dwarf: \"The cobra is ready. He waits in the arena. Finish it.\"", "choices": []}
    if choice is None:
        if not has(run, "trial_started"):
            opts = [_opt("accept", "Accept the test")]
            if has(run, "pit_ally"):
                opts.append(_opt("attack", "Attack with Throm"))
            who = "Alone, and still breathing." if has(run, "pit_betrayed") else "Locked in, both of you."
            return {"text": f"Dwarf: \"{who} Only one continues; that is the procedure. The Trialmaster at your service: locked doors are my speciality.\"", "choices": opts}
        if not has(run, "trial_dice"):
            return _dice_prompt()
        return _cobra_prompt("")
    if choice in ("accept", "attack"):
        if has(run, "trial_started"):
            return _rejected()
        if choice == "attack" and not has(run, "pit_ally"):
            return _rejected()
        _flag(run, "trial_started")
        if choice == "attack":  # p.179 exists in the book; its consequence is not verified: the Dwarf is ready for it (placeholder, as the legacy had it)
            wound(world, seat, "dwarf")
            p = _dice_prompt()
            p["text"] = "Dwarf: \"Oh, we do this every Trial.\"\n\nSomething clicks. Throm sits down suddenly, holding his head. \"We do it MY way,\" the Dwarf says. You are hurt: one cast fewer in your next duel.\n\n" + p["text"]
            return p
        p = _dice_prompt()
        p["text"] = "Dwarf: \"Through here. Mind the cobra.\"\n\n" + p["text"]
        return p
    if choice in ("same", "less", "more"):
        if not has(run, "trial_started") or has(run, "trial_dice"):
            return _rejected()
        rng = random.Random(f"{run['id']}:{seat['seat']}:dice")
        roll = rng.randint(1, 6) + rng.randint(1, 6)
        won = (choice == "same" and roll == 8) or (choice == "less" and roll < 8) or (choice == "more" and roll > 8)
        _flag(run, "trial_dice")
        run["flags"]["dice_roll"] = roll
        lead = f"The cup lifts: {roll}. " + ("\"Hm. Luck or arithmetic.\"" if won else "\"Wrong. But you understood the question, which is the point.\"")
        return _cobra_prompt("Dwarf: " + lead)
    if choice in ("gaze", "snatch"):
        if not has(run, "trial_dice"):
            return _rejected()
        if choice == "snatch":
            wound(world, seat, "cobra")
            lead = "Fast, but fangs graze your wrist. You are hurt: one cast fewer in your next duel."
        else:
            lead = "You hold its gaze until it looks away first. The Dwarf writes something down."
        _flag(run, "trial_cobra")
        _flag(run, "trial_ready")
        _flag(run, "dwarf_map")
        wizard.learn(world, [STONE])  # the Dwarf's test teaches Stone (the palette mapping of the canon table)
        wizard.learn_fact(world, "dwarf_map")
        text = (lead + "\n\nDwarf: \"Procedure complete. You've earned the map, the part of it I'm allowed to give.\"\n\nHe unrolls a scrap of oiled hide: the lower Trial, in a hand that has drawn it many times. "
                "Three gems marked. A door marked that wants Emerald, Sapphire and Diamond. And a passage from this very room, west, that is not on anyone else's map.\n\n"
                "Watching him weave the lock shut, you learn a fourth colour: Stone.")
        if has(run, "pit_betrayed") or run["throm"] in ("dead", "betrayed"):
            _flag(run, "trial_done")
            text += "\n\nDwarf: \"Alone, and still standing. The concealed way is yours: west, when you're ready.\""
        else:
            text += "\n\nDwarf: \"The cobra is ready. He waits in the arena. Finish it.\" Throm is dragged in, and his eyes do not know you."
        return {"text": text, "choices": []}
    return _rejected()


# ------------------------------------------------------------------ the dying elf (p.281, 399, 192)

def elf_rescue(world: Any, run: dict[str, Any], seat: dict[str, Any], choice: str | None) -> Prompt:
    if not defeated(run, "dd_grotto", "boa_grotto1"):
        return {"text": "Dying elf: \"...help... the snake... first...\"", "choices": []}
    if has(run, "elf_gone"):
        return {"text": "She is gone. The hollow smells of bread and dust.", "choices": []}
    if choice is None:
        return {"text": "The snake loosens. The elven woman breathes, barely. She is fading.", "choices": [_opt("stay", "Stay with her"), _opt("take", "Take the charm and go")]}
    if choice not in ("stay", "take"):
        return _rejected()
    _flag(run, "elf_gone")
    _flag(run, "diamond_clue")
    wizard.learn_fact(world, "diamond_is_cold")
    ledger.bump(world, "trial_mercies" if choice == "stay" else "trial_haste", seat=seat["seat"])
    if choice == "stay":
        return {"text": "You hold her hand while she tells you: the final door wants gems, and one of them is a diamond. The real one is cold.\n\nDying elf: \"Take the charm. Take the bread. ...Tell the trees I was brave.\"", "choices": []}
    return {"text": "You take the charm. Her voice follows you out: the final door wants gems, one is a diamond, and the real one is cold.", "choices": []}


# ------------------------------------------------------------------ the idol's false eye (p.239, 34, 89)

def false_eye(world: Any, run: dict[str, Any], seat: dict[str, Any], choice: str | None) -> Prompt:
    if has(run, "picked_false_eye"):
        return {"text": "A socket, empty, and a room full of dead birds.", "choices": []}
    if choice is None:
        return {"text": "The east eye glitters. Bigger. Greener. The scratched warnings around the base were about this one.", "choices": [_opt("take", "Take it"), _opt("leave", "Leave it")]}
    if choice == "leave":
        return {"text": "You leave it where it lies.", "choices": []}
    if choice != "take":
        return _rejected()
    take_entity(run, "dd_idol", "false_eye")
    _flag(run, "idol_alarmed")
    _pocket(seat, "glass_eye")
    if not defeated(run, "dd_idol", "guard_idol2"):
        return {"text": "It comes away in your hand, glass, flawed glass, and every bird on the idol turns its head at once.\n\nThe second guardian does not wait to be found. It finds you.", "choices": [],
                "fight": ["guard_idol2", "flying_guardian"]}
    return {"text": "Nothing else moves. You are holding a piece of green glass in a room full of dead birds.", "choices": []}


# ------------------------------------------------------------------ the false diamond beside the fallen warrior (p.218, 65, 252)

def false_diamond(world: Any, run: dict[str, Any], seat: dict[str, Any], choice: str | None) -> Prompt:
    if has(run, "picked_false_diamond"):
        return {"text": "The warrior lies where he fell. The floor beside him has an eye, and it is closed again.", "choices": []}
    if choice is None:
        lead = "You remember the elf: the real one is cold. This one has been lying under a lamp.\n\n" if (has(run, "diamond_clue") or wizard.knows_fact(world, "diamond_is_cold")) else ""
        return {"text": lead + "A diamond beside a fallen warrior, just lying there. Every instinct says trap.", "choices": [_opt("take", "Take it"), _opt("leave", "Leave it")]}
    if choice == "leave":
        return {"text": "You leave it where it lies.", "choices": []}
    if choice != "take":
        return _rejected()
    take_entity(run, "dd_vaults", "false_diamond")
    _flag(run, "vault_alarm")
    wound(world, seat, "false_diamond")
    _pocket(seat, "glass_diamond")
    return {"text": "The floor opens its eye. A blade you never see draws a line across your arm, and somewhere behind you an iron bolt shoots home.\n\nYou are hurt: one cast fewer in your next duel. The jewel is glass. The inner vault has locked itself; the Basket man's rope is now the only way in.", "choices": []}


# ------------------------------------------------------------------ the prisoner in the service tunnels (report section 6)

def free_prisoner(world: Any, run: dict[str, Any], seat: dict[str, Any], choice: str | None) -> Prompt:
    if has(run, "prisoner_free"):
        return {"text": "Starved man: \"Go. Stones. It loves... no. It HATES the green. Vine. Its eyes water.\"", "choices": []}
    if choice is None:
        return {"text": "Starved man: \"...failed... they took my eyes... no, my boots...\"", "choices": [_opt("free", "Free him"), _opt("leave", "Leave him")]}
    if choice == "leave":
        return {"text": "You leave him. The dark keeps him.", "choices": []}
    if choice != "free":
        return _rejected()
    _flag(run, "prisoner_free")
    _flag(run, "blood_weakness")
    wizard.learn_fact(world, "bloodbeast_hates_vine")
    ledger.bump(world, "trial_mercies", seat=seat["seat"])
    return {"text": "You cut his bonds. He presses something into your hand, bitter herbs, and babbles about the beast below.\n\nStarved man: \"Go. Stones. It loves... no. It HATES the green. Vine. Its eyes water.\"\n\n(The Bloodbeast's Ward will not hold Vine.)", "choices": []}


# ------------------------------------------------------------------ Poison Ivy's toll (CSV)

def ivy_toll(world: Any, run: dict[str, Any], seat: dict[str, Any], choice: str | None) -> Prompt:
    if has(run, "ivy_paid"):
        return {"text": "Poison Ivy: \"Paid in full. Walk soft, sweetling.\"", "choices": []}
    if choice is None:
        opts = []
        if "torch" in seat["pockets"]:
            opts.append(_opt("torch", "Offer the torch"))
        opts += [_opt("leave", "Leave"), _opt("attack", "Attack")]
        return {"text": "Poison Ivy: \"Tribute, sweetling. Something useful, or thorns.\"", "choices": opts}
    if choice == "torch":
        if "torch" not in seat["pockets"]:
            return _rejected()
        seat["pockets"].remove("torch")
        _flag(run, "ivy_paid")
        return {"text": "Poison Ivy: \"A torch? For me? ...Walk soft, sweetling. Walk soft.\"", "choices": []}
    if choice == "leave":
        return {"text": "You leave her thorns alone.", "choices": []}
    if choice == "attack":
        return {"text": "The thorns come up all at once.", "choices": [], "fight": ["dd_ivy", "poison_ivy"]}
    return _rejected()


# ------------------------------------------------------------------ the Basket man's lift (the legacy's loop between the service tunnels and the inner vault)

def basket_ride(world: Any, run: dict[str, Any], seat: dict[str, Any], choice: str | None) -> Prompt:
    if not (has(run, "ivy_paid") or has(run, "prisoner_free")):
        return {"text": "Basket man: \"Rope's for staff and for people Ivy likes. You're neither, yet. Sort her out, or sort out the poor sod in the cell, and we'll talk.\"", "choices": []}
    if not has(run, "basket_ok"):
        _flag(run, "basket_ok")
        return {"text": "Basket man: \"Heard what you did. Right. The rope goes up to the vault's back room and comes down again; use the shaft at the south wall whenever you like. Don't tell the Dwarf.\"", "choices": []}
    return {"text": "Basket man: \"Shaft's at the south wall. Up or down, same fare: none.\"", "choices": []}


# ------------------------------------------------------------------ the mirrors (CSV: the environmental solution first)

def mirror_smash(world: Any, run: dict[str, Any], seat: dict[str, Any], choice: str | None) -> Prompt:
    if defeated(run, "dd_mirror", "demon_mirror1"):
        return {"text": "Silver dust, and a frame with nothing in it.", "choices": []}
    if choice is None:
        return {"text": "Tall mirrors, silver-backed. Something moves in them a breath after you do.", "choices": [_opt("smash", "Smash them"), _opt("leave", "Leave them")]}
    if choice == "leave":
        return {"text": "You leave the glass its dignity.", "choices": []}
    if choice != "smash":
        return _rejected()
    _zone_state(run, "dd_mirror")["defeated"].append("demon_mirror1")
    _flag(run, "mirrors_smashed")
    ledger.bump(world, "trial_wits", seat=seat["seat"])
    return {"text": "Silver rain. The thing in the glass never finishes stepping out.\n\n(The Mirror Demon is broken without a duel. Something bright lies in the frame.)", "choices": []}


# ------------------------------------------------------------------ the boulder (the grub tunnels)

def boulder_run(world: Any, run: dict[str, Any], seat: dict[str, Any], choice: str | None) -> Prompt:
    if has(run, "boulder_done"):
        return {"text": "The groove in the floor ends at a boulder that has stopped arguing." if has(run, "boulder_braced") else "Dust settles in the groove. Whatever rolled has rolled.", "choices": []}
    if choice is None:
        opts = [_opt("run", "Run!")]
        if wizard.knows(world, STONE):
            opts.append(_opt("brace", "Brace with Stone"))
        opts.append(_opt("hold", "Hold ground"))
        return {"text": "The tunnel exhales dust. Uphill, something heavy decides.", "choices": opts}
    if choice not in ("run", "brace", "hold") or (choice == "brace" and not wizard.knows(world, STONE)):
        return _rejected()
    _flag(run, "boulder_done")
    if choice == "run":
        return {"text": "You run like the Trial is behind you. It is. The groove in the floor runs straight; you don't. The boulder agrees to miss.", "choices": []}
    if choice == "brace":
        _flag(run, "boulder_braced")
        ledger.bump(world, "trial_wits", seat=seat["seat"])
        return {"text": "You lay Stone across the groove and lean on it. The boulder arrives, argues, and loses. Behind it, the side tunnel is open and full of somebody's abandoned kit.", "choices": []}
    wound(world, seat, "boulder")
    return {"text": "You hold your ground. The ground holds. You don't.\n\nYou are hurt: one cast fewer in your next duel.", "choices": []}


# ------------------------------------------------------------------ the trapped chest (the brief's trade-off, not a dice roll)

def trapped_chest(world: Any, run: dict[str, Any], seat: dict[str, Any], choice: str | None) -> Prompt:
    if has(run, "chest_done"):
        return {"text": "The chest stands open, its blades spent. The gold is gone." if has(run, "chest_gold") else "The chest stands open, its blades spent.", "choices": []}
    if choice is None:
        opts = []
        if wizard.knows(world, STONE):
            opts.append(_opt("jam", "Jam the lid with Stone"))
        opts += [_opt("side", "Open it from the side"), _opt("headon", "Open it head-on"), _opt("leave", "Leave it")]
        return {"text": "An iron-bound chest, lid a finger's width open. Gold glints inside. So does something else, at floor height.", "choices": opts}
    if choice == "leave":
        return {"text": "You leave the gold to whatever guards it.", "choices": []}
    if choice not in ("jam", "side", "headon") or (choice == "jam" and not wizard.knows(world, STONE)):
        return _rejected()
    _flag(run, "chest_done")
    _flag(run, "chest_gold")
    take_entity(run, "dd_grub", "trapped_chest")
    _pocket(seat, "gold")
    if choice == "jam":
        ledger.bump(world, "trial_wits", seat=seat["seat"])
        return {"text": "You lay a knot of Stone across the hinge. The lid heaves once against it and gives up. Inside: gold, and a row of blades folded flat like a fan.", "choices": []}
    if choice == "side":
        return {"text": "You stand where the floor is unscratched and lift the lid with the butt of your staff. Blades whicker out across the place you are not standing.\n\nThe gold is real.", "choices": []}
    wound(world, seat, "chest")
    return {"text": "Teeth. The chest had teeth, and the marks on the floor had told you exactly where.\n\nYou are hurt: one cast fewer in your next duel. The gold is real, at least.", "choices": []}


# ------------------------------------------------------------------ the troglodytes (CSV)

def trog_ritual(world: Any, run: dict[str, Any], seat: dict[str, Any], choice: str | None) -> Prompt:
    if has(run, "trog_rite") or has(run, "trog_ran") or defeated(run, "dd_troglodytes", "dd_trog_elder"):
        return {"text": "Ritual elder: \"Danced. Witnessed. Go with wet feet, stranger.\"" if has(run, "trog_rite") else "The drums have stopped. The tribe keeps its distance.", "choices": []}
    if choice is None:
        return {"text": "Ritual elder: \"The rite, stranger. Dance it, run it, or bleed it. The tribe does not mind which.\"",
                "choices": [_opt("join", "Join the ritual"), _opt("run", "Run the arrow"), _opt("attack", "Attack")]}
    if choice == "join":
        _flag(run, "trog_rite")
        return {"text": "You dance badly and sincerely. The tribe approves of sincerity.", "choices": []}
    if choice == "run":
        _flag(run, "trog_ran")
        return {"text": "Bridges, drums, black water, and then, impossibly, quiet.", "choices": []}
    if choice == "attack":
        return {"text": "Their champion steps out of the drumming.", "choices": [], "fight": ["dd_trog_elder", "trog_champion"]}
    return _rejected()


# ------------------------------------------------------------------ Igbut's door (p.364, 62, 241, 400, 31, 376, 3): the gem lock as positional deduction

ORDERS = {"ESD": "Emerald, Sapphire, Diamond", "EDS": "Emerald, Diamond, Sapphire", "SED": "Sapphire, Emerald, Diamond",
          "SDE": "Sapphire, Diamond, Emerald", "DES": "Diamond, Emerald, Sapphire", "DSE": "Diamond, Sapphire, Emerald"}
CORRECT = "SED"
GEMS = {"E": "emerald", "S": "sapphire", "D": "diamond"}


def igbut_door(world: Any, run: dict[str, Any], seat: dict[str, Any], choice: str | None) -> Prompt:
    if has(run, "dungeon_complete"):
        return {"text": "Igbut: \"The door is open. Fang is waiting, Champion.\"", "choices": []}
    if choice is None:
        return {"text": "Igbut: \"Three gems, contestant. Emerald. Sapphire. Diamond. The door does the rest.\"", "choices": [_opt("face", "Face the door"), _opt("later", "Not yet")]}
    if choice == "later":
        return {"text": "Igbut: \"It waits. It is good at waiting.\"", "choices": []}
    gems = set(seat["gems"])
    if choice == "face":
        if not {"emerald", "sapphire", "diamond"} <= gems:
            return {"text": "Igbut: \"The gnome counts on his fingers. Counts again.\"\n\nIgbut: \"Emerald. Sapphire. Diamond. THREE are required, contestant. The Trial does not bargain.\"", "choices": []}
        return {"text": "Igbut: \"Three sockets. Three gems. Place them true, and mind the bite.\"", "choices": [_opt(k, v) for k, v in ORDERS.items()]}
    if choice not in ORDERS:
        return _rejected()
    if not {"emerald", "sapphire", "diamond"} <= gems:
        return _rejected()
    key = f"igbut_strikes:{seat['seat']}"
    if choice == CORRECT:
        _flag(run, "dungeon_complete")
        run["flags"]["champion"] = seat["seat"]
        run["flags"].pop(key, None)
        ledger.bump(world, "trial_champion", seat=seat["seat"])
        wizard.learn_fact(world, "champion_of_the_trial")
        return {"text": "The sockets drink the gems. The door sighs open.\n\nIgbut: \"Ha! Walk through, Champion...\"\n\nA crossbow sings from the dark Sukumvit built. Igbut does not finish.\n\nYou walk past him into daylight, and Fang roars your name.\n\nCHAMPION OF THE TRIAL", "choices": [], "champion": True}
    placed = sum(1 for i in range(3) if choice[i] == CORRECT[i])
    strikes = int(run["flags"].get(key, 0)) + 1
    run["flags"][key] = strikes
    if strikes < 3:
        wound(world, seat, "igbut")
        return {"text": f"Igbut: \"{placed} placed true, {3 - placed} displaced.\"\n\nThe door bites. You are hurt: one cast fewer in your next duel.", "choices": [_opt(k, v) for k, v in ORDERS.items()]}
    run["flags"].pop(key, None)
    for g in ("emerald", "sapphire", "diamond"):
        if g in seat["gems"]:
            seat["gems"].remove(g)
    _flag(run, "gems_scattered")
    zs = _zone_state(run, "dd_igbut")
    for g in ("emerald", "sapphire", "diamond"):
        if "scattered_" + g in zs["taken"]:
            zs["taken"].remove("scattered_" + g)
        run["flags"].pop("picked_scattered_" + g, None)
    return {"text": f"Igbut: \"{placed} placed true, {3 - placed} displaced.\"\n\nThe third blast throws the gems out of your hands and across the floor. The sockets grind shut.\n\nIgbut, from behind the plinth: \"They reopen. They always reopen. Pick up your stones, contestant.\"", "choices": []}


EVENTS = {"statue_riddle": statue_riddle, "throm_pit": throm_pit, "black_book": black_book, "dwarf_meet": dwarf_meet, "elf_rescue": elf_rescue,
          "false_eye": false_eye, "false_diamond": false_diamond, "free_prisoner": free_prisoner, "ivy_toll": ivy_toll, "basket_ride": basket_ride,
          "mirror_smash": mirror_smash, "boulder_run": boulder_run, "trapped_chest": trapped_chest, "trog_ritual": trog_ritual, "igbut_door": igbut_door}
