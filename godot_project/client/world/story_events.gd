extends RefCounted
class_name StoryEvents

## Scripted sequences for the Trial-Day chapter (P1). Each event is an async
## function driving the Overworld's cutscene helpers. World progression after
## battles is handled here too (never inside the battle UI).

var _w  # Overworld


func setup(world) -> void:
	_w = world


func _adv() -> Node:
	return _w.get_node("/root/Adventure")


func run_event(id: String) -> void:
	match id:
		"red_intercept":
			await red_intercept()
		"ashby_training":
			await ashby_training()
		"gate_choice":
			await gate_choice()
		"statue_riddle":
			await statue_riddle()
		"throm_pit":
			await throm_pit()
		"black_book":
			await black_book()
		"dwarf_meet":
			await dwarf_meet()
		"elf_rescue":
			await elf_rescue()
		"false_eye":
			await false_eye()
		"false_diamond":
			await false_diamond()
		"free_prisoner":
			await free_prisoner()
		"ivy_toll":
			await ivy_toll()
		"basket_ride":
			await basket_ride()
		"trapped_chest":
			await trapped_chest()
		"mirror_smash":
			await mirror_smash()
		"boulder_run":
			await boulder_run()
		"trog_ritual":
			await trog_ritual()
		"igbut_door":
			await igbut_door()
		"jane_wake":
			await jane_wake()


# ---------------------------------------------------------------------------------
# PROLOGUE (brief §1–§4). You are Halvard. Briefly.
# ---------------------------------------------------------------------------------

func prologue_open() -> void:
	_w.lock_input(true)
	await narrate("Trial Day in Ashwell.")
	await narrate("You are Halvard. You are a great wizard — the kind people have prints of.")
	await narrate("Today you will walk up that hill, enter the Trial, survive it, and become very, very famous. This story has been waiting for a protagonist of your quality.")
	await narrate("Take a moment. Let them look at you. Then head for the road.")
	_w.lock_input(false)


func red_intercept() -> void:
	var adv := _adv()
	_w.lock_input(true)
	await narrate("Shouting, down by the road. Someone is saying your name the way a debt collector says it.")
	_w.spawn_actor("red", "red_mage", Vector2i(18, 8), "left")
	await _w.move_actor("red", Vector2i(_w.john_pos().x + 3, 8), 0.9)
	# Brief §3: the one on the left faces right, the one on the right faces left —
	# set from positions, then read back by the flow test from the textures.
	_w.face_each_other("john", "red")
	await _w.say("Red Wizard", "Halvard. You look older. You look like a man who has been telling the same story for twenty years.")
	await _w.say("Red Wizard", "Three knots. Show me you still remember how.")
	await narrate("He is not asking. You are a great wizard; this is the part of the day where you prove it.")
	adv.save()
	await _w.start_battle_request({
		"id": "halvard_vs_red", "enemy_id": "red_wizard_prologue", "kind": "wizard",
		"policy": adv.POLICY_PROLOGUE, "forced_defeat_by_cast": 3,
		"player_combatant": halvard_combatant(),
		"intro": "The Red Wizard. Three slots, and a smile like an unpaid bill.\n\nYou are Halvard. Choose your Ward and cast — you have done this a thousand times.",
	})


## The prologue's player: enough magic for a real duel, three slots, no mods.
static func halvard_combatant() -> Dictionary:
	return {
		"id": "halvard", "display_name": "Halvard", "archetype": "blue_mage", "kind": "player",
		"weave_size": 3, "attack_pool": [1, 0, 3], "ward_size": 3, "ward_pool": [1, 0, 3],
		"allow_repeats": true, "max_casts": 10, "min_cast_seconds": 5.0, "max_cast_seconds": 60.0,
	}


## After the Red Wizard wins: Halvard dies, and the narrator starts again.
func _prologue_defeat(adv: Node, _req: Dictionary) -> void:
	_w.spawn_actor("red", "red_mage", Vector2i(12, 8), "left")
	_w.face_each_other("john", "red")
	await _w.bolt(Vector2i(12, 8), _w.john_pos(), Color(1.0, 0.3, 0.1), 0.25)
	await _w.flash(Color(1.0, 0.5, 0.2), 0.3)
	await _w.shake(10.0, 0.5)
	await narrate("Halvard goes down in the dust of the road, and does not get up.")
	await narrate("He was a great wizard. That part was true. It just wasn't the part that mattered today.")
	_w.face_actor("red", "down")
	await _w.say("Red Wizard", "Don't stare, villager. You'll see worse before sunset.")
	await _w.move_actor("red", Vector2i(18, 8), 0.8)
	_w.remove_actor("red")
	await narrate("...")
	await narrate("Okay. That didn't work.")
	await narrate("Let's try again.")
	# Protagonist swap: the body and the staff appear where Halvard stood; John
	# starts one tile east of them, unarmed and unmagical.
	adv.set_flag("halvard_dead")
	adv.advance_phase("john_intro")
	_w.load_area("village", Vector2i(11, 8), "left")
	await narrate("You are John. You are a mighty woodcutter, in the sense that you cut wood and are fairly large. You have watched a man die in the road, and you have not moved.")
	await narrate("You are, apparently, going to do the Trial instead.")
	await narrate("Go and pick up that blue man's staff.")
	adv.save()


# ---------------------------------------------------------------------------------
# ASHBY (brief §6–§8): three training duels, one NPC, no penalties.
# ---------------------------------------------------------------------------------

func ashby_training() -> void:
	var adv := _adv()
	if adv.story_phase() == "john_intro":
		adv.advance_phase("ashby_training")
	if adv.flag("ashby_training_complete"):
		await _w.say("Ashby", "Come back when you want to lose gracefully. Or win — I'm told it happens.")
		var again: String = await _w._dialogue.choose_async("Spar with Ashby?", ["Spar", "Not now"])
		if again == "Spar":
			await _w.start_battle_request({
				"id": "ashby_spar", "enemy_id": "ashby_lesson3", "kind": "wizard", "training": true,
				"intro": "Ashby, sleeves rolled. Two against two, for practice.",
			})
		return
	if not adv.flag("ashby_duel1_done"):
		await _w.say("Ashby", "Halvard's staff. In the hand of a man who smells of sawdust. I have had stranger Tuesdays.")
		await _w.say("Ashby", "Water, and one knot. That isn't wizardry yet. But it is enough for me to show you what a Ward is.")
		await _w.say("Ashby", "I'll hide one spell. You cast the one you have. Watch what happens.")
		await _w.start_battle_request({
			"id": "ashby_duel1", "enemy_id": "ashby_lesson1", "kind": "wizard", "training": true,
			"on_win_flag": "ashby_duel1_done", "on_defeat_flag": "ashby_duel1_done",
			"intro": "Ashby's first lesson. One slot, one spell.\n\nChoose a Ward. Cast. Read the result.",
		})
		return
	if not adv.flag("ashby_duel2_done"):
		await _w.say("Ashby", "Good. Now let me show you what a real wizard does, so you don't go up that hill thinking you've seen one.")
		await _w.say("Ashby", "Two knots. Two slots. Same rules.")
		await _w.start_battle_request({
			"id": "ashby_duel2", "enemy_id": "ashby_lesson2", "kind": "wizard", "training": true,
			"on_win_flag": "ashby_duel2_done", "on_defeat_flag": "ashby_duel2_done",
			"grant_on_defeat": {"spell": 6, "weave": 2, "text": "Ashby puts a green seed in your palm and closes your fingers over it.\n\n\"One spell and one knot were never going to be enough. Nobody told you. I'm telling you.\"\n\nYou have learned VINE magic.\nYour weave can now hold TWO spells."},
			"intro": "Ashby's second lesson. Two slots of Water and Vine, hidden.\n\nYour one Water cannot reach a complete two-slot Ward. Cast anyway. See why.",
		})
		return
	if not adv.flag("ashby_duel3_done"):
		await _w.say("Ashby", "Again. Properly, this time. Two against two.")
		await _w.say("Ashby", "Win or lose, you'll have learned what I can teach you standing in a yard.")
		await _w.start_battle_request({
			"id": "ashby_duel3", "enemy_id": "ashby_lesson3", "kind": "wizard", "training": true,
			"on_win_flag": "ashby_duel3_done", "on_defeat_flag": "ashby_duel3_done",
			"intro": "Ashby's third lesson. A fair fight: two slots each, Water and Vine on both sides.\n\nWhoever reads faster.",
		})
		return


## Ashby reacts to each result; training never resets or punishes.
func _ashby_after(adv: Node, encounter_id: String, outcome: String) -> void:
	match encounter_id:
		"ashby_duel1":
			if outcome == "victory":
				await _w.say("Ashby", "There. Your spell against my Ward, and my Ward gave. That's a battle.")
			else:
				await _w.say("Ashby", "Hm. One slot, and you missed it. Never mind — the point was to see it happen, and you saw it.")
		"ashby_duel2":
			if outcome == "victory":
				await _w.say("Ashby", "...You broke it. With one knot. I'm going to pretend I meant that to be possible.")
			else:
				await _w.say("Ashby", "You see it now. A bigger weave isn't more damage. It's REACH — I could touch a Ward you couldn't.")
		"ashby_duel3", "ashby_spar":
			if outcome == "victory":
				await _w.say("Ashby", "Ha! Well. Don't let it go to your head. Do let it go to your feet — the road's that way.")
			else:
				await _w.say("Ashby", "Close. Closer than I'd like, frankly. You'll do.")
	if encounter_id == "ashby_duel3" and not adv.flag("ashby_training_complete"):
		adv.set_flag("ashby_training_complete")
		adv.advance_phase("pre_trial")
		await _w.say("Ashby", "That's everything a yard can teach. The Burnt Wood east of the road will teach the rest, if you let it.")
		await _w.say("Ashby", "The red pendant out there — it isn't jewellery. Neither is the golem. Bring back four kinds of magic and three knots, or don't go up that hill.")


func gate_choice() -> void:
	var adv := _adv()
	_w.lock_input(true)
	if adv.flag("entered_trial"):
		await _w.say("Rollkeeper", "Sunset. Be ready. The doors only open once.")
		_w.lock_input(false)
		return
	await _w.say("Rollkeeper", "Names for the roll. ...John? John the woodcutter? Halvard's seal — it's genuine.")
	# Brief §14: the Trial does not take the underpowered. Diegetic refusal.
	if not adv.trial_ready():
		var known: int = adv.progression.spells_known.size()
		var knots: int = adv.progression.weave_size
		await _w.say("Rollkeeper", "Four kinds of magic and three knots. That is the floor, not the ceiling — the Trial does not admit anyone below it, and I do not write down the names of the dead in advance.")
		if known < 4:
			await _w.say("Rollkeeper", "You carry %d kind%s. The Burnt Wood east of the road has been generous to people who came back from it." % [known, "" if known == 1 else "s"])
		if knots < 3:
			await _w.say("Rollkeeper", "And you weave %d. A golem's heart would fix that, if you can take one." % knots)
		await _w.say("Rollkeeper", "Come back before sunset. Or don't. Both are allowed.")
		_w.lock_input(false)
		return
	await _w.say("Rollkeeper", "Halvard's place is vacant, and you carry his seal. Four kinds, three knots — the floor, met. So: do you enter the Trial?")
	var choice: String = await _w._dialogue.choose_async("Do you enter the Trial?", ["Enter the Trial", "Not yet"])
	if choice == "Enter the Trial":
		adv.set_flag("entered_trial")
		adv.advance_phase("trial")
		await _w.flash(Color(0.9, 0.85, 1.0), 0.4)
		await narrate("The Rollkeeper writes JOHN in the book, and the ink does not come off.")
		await _w.shake(6.0, 0.6)
		await narrate("The enormous doors begin to close behind the contestants.")
		await narrate("For the first time since leaving Ashwell, turning around is no longer an option. You notice this the way you notice a missing step: afterwards.")
		await narrate("Ahead, somewhere in the dark, somebody screams.")
		await _w.say("Red Wizard", "Oh, good. The villager. Try to die somewhere I can see.")
		await narrate("And he walks on.\n\n— THE TRIAL BEGINS —")
		adv.start_run()
		_w.load_area("dd_entrance", Vector2i(10, 11), "up")
		await narrate("Crystal light. Six boxes on a stone table — five already taken.\n\nThe doors shut behind you.")
		adv.save()
	else:
		await _w.say("Rollkeeper", "Then stand clear of the doors. The offer stands until sunset.")
	_w.lock_input(false)


## P2 dungeon scenes. These run inside the caller's input lock (npc/pickup
## interaction), so they never lock/unlock themselves. Only gate_choice (a
## trigger event) owns the lock.
func statue_riddle() -> void:
	# The old man's number-riddle (brief §24). The answer is derivable from
	# what John can see: the statue's base is inscribed (dd_statue_sign, p.382
	# gated: the book's own number is NEEDS_PAGE_IMAGE_CHECK, so the puzzle is
	# self-contained and does not assert canon).
	var adv := _adv()
	if adv.run_flag("riddle_answered"):
		if adv.run_flag("riddle_right"):
			await _w.say("Old man", "You read. Good. The lion-thing below hates the light for the same reason.")
		else:
			await _w.say("Old man", "The stone keeps its own counsel. So do I, now.")
		return
	await _w.say("Old man", "A knight went first. She counted the steps from the door to this stone — she said it aloud so I'd remember. Half as many again as the years I've stood here, and I have stood here a hundred.")
	await _w.say("Old man", "How many steps did she count? One hundred? One hundred and fifty? Two hundred?")
	var answer: String = await _w._dialogue.choose_async("Answer the old man?", ["100", "150", "200"])
	adv.set_run_flag("riddle_answer_" + answer)
	adv.set_run_flag("riddle_answered")
	if answer == "150":
		adv.set_run_flag("riddle_right")
		adv.add_knowledge("The old man: the Manticore below hates the light. Its Ward will not hold Light.")
		await _w.say("Old man", "A hundred and fifty. She could count; it didn't save her.")
		await _w.say("Old man", "So I'll tell you one thing for it. The lion-thing that guards the last door hates the light. Remember that when you weave against it.")
	else:
		adv.add_condition("wounded")
		await _w.say("Old man", "No. Listen better — the Trial won't ask twice.")
		await _w.say("", "He raps your knuckles with his staff, hard enough to numb the hand. You are WOUNDED: −1 cast in your next duel.")
	await _w.say("", "Beside him stands a knight in White Road armour, turned to stone mid-step.\n\nSerra went first. This is where first got her.")


func throm_pit() -> void:
	# p.22 (choices) → p.63 / p.184 (→ p.323 / p.149) / p.311, as run flags.
	var adv := _adv()
	if adv.run_flag("pit_crossed"):
		return
	await _w.say("", "A pit cuts the corridor. Far below, water moves. The far edge is a long jump — or a rope's length, if someone holds the rope.")
	await _w.say("Throm", "I hold the rope, or you hold it for me. Or we jump it together, and laugh.")
	var choice: String = await _w._dialogue.choose_async("The pit?", ["Let him lower you", "Offer to lower him", "Jump together", "Climb down alone"])
	if choice == "Climb down alone":
		# Brief §25: a hazard with a consequence that is not a battle defeat.
		adv.add_condition("wounded")
		adv.set_run_flag("pit_fell")
		adv.set_run_flag("pit_ally")
		adv.set_contestant("throm", "uneasy_ally")
		var lost_torch: bool = adv.run_flag("picked_dd_torch") and not adv.run_flag("torch_lost")
		if lost_torch:
			adv.set_run_flag("torch_lost")
		await _w.say("", "You take the wall alone. Halfway, the wall takes you. You land in the shallows, hard.\n\nYou are WOUNDED: −1 cast in your next duel." + ("\n\nYour torch hisses out in the water and goes to the bottom." if lost_torch else ""))
		await _w.say("Throm", "Hah. Wait there — I'm coming down the sensible way.")
	elif choice == "Offer to lower him":
		await _w.say("Throm", "...Throm. My name is Throm. Take the rope, then. Tightly.")
		await _w.say("", "You lower Throm by the rope. He looks very small, and then he waves you off the edge.")
		var second: String = await _w._dialogue.choose_async("Throm waits below.", ["Climb down after him", "Leave him"])
		if second == "Leave him":
			adv.set_run_flag("pit_betrayed")
			adv.set_contestant("throm", "betrayed")
			await _w.say("", "You cross alone. Behind you, the rope goes still.\n\nYou will remember this.")
		else:
			adv.set_run_flag("pit_ally")
			adv.set_contestant("throm", "uneasy_ally")
			await _w.say("Throm", "Hah. An honest villain would've left. Come on.")
	elif choice == "Jump together":
		adv.add_condition("wounded")
		adv.set_run_flag("pit_jump")
		adv.set_run_flag("pit_ally")
		adv.set_contestant("throm", "uneasy_ally")
		await _w.say("", "You jump together, land hard, and laugh until it hurts.\n\n(It hurts. You are WOUNDED: −1 cast in your next duel.)")
	else:
		adv.set_run_flag("pit_ally")
		adv.set_contestant("throm", "uneasy_ally")
		await _w.say("Throm", "Down you go, villager. I have held worse.")
	adv.set_run_flag("pit_crossed")


func black_book() -> void:
	# p.138: the unknown potion. Throm wants nothing to do with it.
	var adv := _adv()
	if adv.run_flag("potion_used"):
		return
	await _w.say("Throm", "Don't. Whatever it is, don't.")
	var choice: String = await _w._dialogue.choose_async("The vial?", ["Drink it", "Rub it on your wounds", "Leave it"])
	if choice == "Drink it":
		adv.add_condition("poisoned")
		adv.set_run_flag("potion_used")
		await _w.say("", "It tastes of ink and lightning. Your hands shake.\n\nYou are POISONED: your next duel starts slower (+2s minimum cast).")
	elif choice == "Rub it on your wounds":
		adv.set_run_flag("potion_used")
		await _w.say("", "It burns cold. Where it touches, the skin knits — a little.")
	else:
		await _w.say("", "You stopper the vial and leave it. Some things stay unknown.")


## P3 Trialmaster scenes (p.60, 365). Choice-owned; no lock handling here.
func dwarf_meet() -> void:
	var adv := _adv()
	if adv.run_flag("trial_done"):
		return
	if adv.run_flag("trial_ready"):
		return
	var allied: bool = adv.run_flag("pit_ally")
	var options := ["Accept the test"]
	if allied:
		options.append("Attack with Throm")
	await _w.say("Dwarf", "Locked in, both of you. Only one continues — that is the procedure.")
	var choice: String = await _w._dialogue.choose_async("The locked chamber?", options)
	if choice == "Attack with Throm":
		# p.179 branch exists in the book; its consequence is not yet verified
		# (see dd_passages). Placeholder: the Dwarf is ready for it.
		adv.add_condition("wounded")
		await _w.say("Dwarf", "Oh, we do this every Trial.")
		await _w.say("", "Something clicks. Throm sits down suddenly, holding his head.\n\n\"We do it MY way,\" the Dwarf says. (You are WOUNDED: −1 cast in your next duel.)")
	await _w.say("Dwarf", "Through here. Mind the cobra.")
	adv.set_run_flag("trial_started")
	await _dwarf_dice(adv)
	await _dwarf_cobra(adv)


func _dwarf_dice(adv: Node) -> void:
	await _w.say("Dwarf", "Two dice in the cup. When they land: the same as eight, less, or more?")
	var guess: String = await _w._dialogue.choose_async("Predict the roll?", ["Same as 8", "Less than 8", "More than 8"])
	var roll := randi_range(2, 12)
	var won := (guess == "Same as 8" and roll == 8) or (guess == "Less than 8" and roll < 8) or (guess == "More than 8" and roll > 8)
	if won:
		await _w.say("Dwarf", "The cup lifts: %d. Hm. Luck or arithmetic." % roll)
	else:
		await _w.say("Dwarf", "The cup lifts: %d. Wrong. But you understood the question, which is the point." % roll)
	adv.set_run_flag("trial_dice")


func _dwarf_cobra(adv: Node) -> void:
	await _w.say("Dwarf", "Last: the basket. Hold its gaze, or snatch it. Choose.")
	var choice: String = await _w._dialogue.choose_async("The cobra?", ["Hold its gaze", "Snatch it"])
	if choice == "Snatch it":
		adv.add_condition("wounded")
		await _w.say("", "Fast — but fangs graze your wrist. (WOUNDED: −1 cast in your next duel.)")
	else:
		await _w.say("", "You hold its gaze until it looks away first. The Dwarf writes something down.")
	await _w.say("Dwarf", "Procedure complete. You've earned the map — the part of it I'm allowed to give.")
	adv.set_run_flag("trial_ready")
	adv.set_run_flag("dwarf_map")
	adv.add_knowledge("The Dwarf's map: past the idol, the grotto and the vaults; the way down is west.")
	await narrate("The Dwarf unrolls a scrap of oiled hide: the lower Trial, in a hand that has drawn it many times. Three gems marked. A door marked. And a passage from this very room, west, that is not on anyone else's map.")
	await narrate("(Your journal now knows: the door wants Emerald, Sapphire and Diamond; the concealed Trialmaster passage links west to the Lower Route.)")
	_w.rebuild()
	if adv.run_flag("pit_betrayed"):
		adv.set_run_flag("trial_done")
		await _w.say("Dwarf", "Alone, and still standing. The concealed way is yours — west, when you're ready.")


## P4 grotto + jewel scenes (p.281, 218). Choice-owned; no lock handling here.
func elf_rescue() -> void:
	# p.281: rescue first, clue second. Order-free: the charm works either way.
	var adv := _adv()
	if not adv.marked("defeated", "boa_grotto1"):
		await _w.say("Dying elf", "...the snake... first...")
		return
	if adv.run_flag("elf_gone"):
		return
	var choice: String = await _w._dialogue.choose_async("She is fading.", ["Stay with her", "Take the charm and go"])
	adv.set_flag("diamond_clue")
	adv.set_run_flag("elf_gone")
	if choice == "Stay with her":
		await _w.say("", "You hold her hand while she tells you: the final door wants gems, and one of them is a diamond.")
		await _w.say("Dying elf", "Take the charm. Take the bread. ...Tell the trees I was brave.")
	else:
		await _w.say("", "You take the charm. Her voice follows you out: the final door wants gems — one is a diamond.")
	_w.rebuild()


func false_eye() -> void:
	# Hazard with a clue (idol base: WEST EYE) and a route consequence: the wrong
	# eye wakes the second guardian early rather than dealing an arbitrary wound.
	var adv := _adv()
	var choice: String = await _w._dialogue.choose_async("The east eye?", ["Take it", "Leave it"])
	if choice == "Take it":
		adv.set_run_flag("idol_alarmed")
		await _w.say("", "It comes away in your hand — glass, flawed glass — and every bird on the idol turns its head at once.")
		if not adv.marked("defeated", "guard_idol2"):
			await _w.say("", "The second guardian does not wait to be found. It finds you.")
			await _w.start_battle_request({"id": "guard_idol2", "enemy_id": "flying_guardian", "kind": "creature",
				"intro": "The second guardian unfolds from the idol's shoulder, already screaming."})
		else:
			await _w.say("", "Nothing else moves. You are holding a piece of green glass in a room full of dead birds.")
	else:
		adv.set_run_flag("picked_false_eye", false)
		await _w.say("", "You leave it where it lies.")
		_w.rebuild()


func false_diamond() -> void:
	# p.218: risk your life for the wrong jewel, or don't. The elf's clue ("the
	# real one is cold") is the tell; the warrior's jewel is warm from the vault
	# lamps. Taking it costs the sapphire box its lock — the vault seals.
	var adv := _adv()
	if adv.flag("diamond_clue"):
		await _w.say("", "You remember the elf: the real one is cold. This one has been lying under a lamp.")
	var choice: String = await _w._dialogue.choose_async("The fallen warrior's jewel?", ["Take it", "Leave it"])
	if choice == "Take it":
		adv.set_run_flag("vault_alarm")
		adv.add_condition("wounded")
		await _w.say("", "The floor opens its eye. A blade you never see draws a line across your arm, and somewhere behind you an iron bolt shoots home.\n\n(WOUNDED: −1 cast in your next duel. The jewel is glass. The inner vault has locked itself — the Basket man's rope is now the only way in.)")
	else:
		adv.set_run_flag("picked_false_diamond", false)
		await _w.say("", "You leave it where it lies.")
		_w.rebuild()


## P5 service + gallery scenes. Choice-owned; no lock handling here.
func free_prisoner() -> void:
	var adv := _adv()
	if adv.run_flag("prisoner_free"):
		return
	var choice: String = await _w._dialogue.choose_async("The starved man?", ["Free him", "Leave him"])
	if choice == "Free him":
		adv.set_run_flag("prisoner_free")
		adv.set_run_flag("blood_weakness")
		adv.add_knowledge("The prisoner: the Bloodbeast is afraid of green things. Its Ward will not hold Vine.")
		await _w.say("", "You cut his bonds. He presses something into your hand — bitter herbs — and babbles about the beast below.")
		await _w.say("Starved man", "Go. Stones. It loves... no. It HATES the green. Vine. Its eyes water.")
		await _w.say("", "(Bloodbeast weakness learned: no Vine in its Ward.)")
	else:
		await _w.say("", "You leave him. The dark keeps him.")


func ivy_toll() -> void:
	var adv := _adv()
	if adv.run_flag("ivy_paid"):
		return
	var options := ["Leave", "Attack"]
	if adv.run_flag("picked_dd_torch") and not adv.run_flag("torch_lost"):
		options.push_front("Offer the torch")
	await _w.say("Poison Ivy", "Tribute, sweetling. Something useful, or thorns.")
	var choice: String = await _w._dialogue.choose_async("Ivy's toll?", options)
	if choice == "Offer the torch":
		adv.set_run_flag("ivy_paid")
		await _w.say("Poison Ivy", "A torch? For me? ...Walk soft, sweetling. Walk soft.")
	elif choice == "Attack":
		await _w.start_battle_request({
			"enemy_id": "poison_ivy", "encounter_id": "ivy_fight1", "kind": "wizard",
			"area": "dd_service", "player_mods": adv.player_mods(), "ward_ban": [],
		})
	else:
		await _w.say("", "You leave her thorns alone.")


## Service ↔ Inner Vault lift (loop 2). The Basket man works for whoever has
## dealt fairly with his floor: Ivy paid, or the prisoner freed.
func basket_ride() -> void:
	var adv := _adv()
	if not (adv.run_flag("ivy_paid") or adv.run_flag("prisoner_free")):
		await _w.say("Basket man", "Rope's for staff and for people Ivy likes. You're neither, yet. Sort her out, or sort out the poor sod in the cell, and we'll talk.")
		return
	if not adv.run_flag("basket_ok"):
		adv.set_run_flag("basket_ok")
		adv.add_knowledge("The Basket man's lift runs between the Service Tunnels and the inner vault.")
		await _w.say("Basket man", "Heard what you did. Right. The rope goes up to the vault's back room and comes down again — use the shaft at the south wall whenever you like. Don't tell the Dwarf.")
	else:
		await _w.say("Basket man", "Shaft's at the south wall. Up or down, same fare: none.")


func mirror_smash() -> void:
	# Environmental solution first; the duel stays for the proud.
	var adv := _adv()
	if adv.marked("defeated", "demon_mirror1"):
		return
	var choice: String = await _w._dialogue.choose_async("The mirrors?", ["Smash them", "Leave them"])
	if choice == "Smash them":
		adv.mark("defeated", "demon_mirror1")
		adv.set_run_flag("mirrors_smashed")
		await _w.say("", "Silver rain. The thing in the glass never finishes stepping out.\n\n(The Mirror Demon is broken without a duel.)")
		_w.rebuild()
	else:
		await _w.say("", "You leave the glass its dignity.")


func boulder_run() -> void:
	var adv := _adv()
	if adv.run_flag("boulder_done"):
		return
	adv.set_run_flag("boulder_done")
	await _w.say("", "The tunnel exhales dust. Uphill, something heavy decides.")
	var options := ["Run!", "Hold ground"]
	if adv.progression.knows(3):
		options.insert(1, "Brace with Stone")
	var choice: String = await _w._dialogue.choose_async("Boulder?", options)
	if choice == "Run!":
		await _w.say("", "You run like the Trial is behind you. It is. The groove in the floor runs straight; you don't. The boulder agrees to miss.")
	elif choice == "Brace with Stone":
		adv.set_run_flag("boulder_braced")
		adv.add_knowledge("A Stone knot across the groove stopped the boulder. The side tunnel behind it is passable now.")
		await _w.say("", "You lay Stone across the groove and lean on it. The boulder arrives, argues, and loses. Behind it, the side tunnel is open and full of somebody's abandoned kit.")
	else:
		adv.add_condition("wounded")
		await _w.say("", "You hold your ground. The ground holds. You don't.\n\n(WOUNDED: −1 cast in your next duel.)")


## Trapped chest (brief §25): a trade-off, not a dice roll. Stone magic can
## jam the mechanism; otherwise the marks on the floor tell you to stand aside.
func trapped_chest() -> void:
	var adv := _adv()
	if adv.run_flag("chest_done"):
		return
	var options := ["Open it from the side", "Open it head-on", "Leave it"]
	if adv.progression.knows(3):
		options.push_front("Jam the lid with Stone")
	var choice: String = await _w._dialogue.choose_async("The chest?", options)
	if choice == "Leave it":
		await _w.say("", "You leave the gold to whatever guards it.")
		return
	adv.set_run_flag("chest_done")
	adv.set_run_flag("picked_trapped_chest")
	if choice == "Jam the lid with Stone":
		adv.set_run_flag("chest_gold")
		adv.add_knowledge("Stone magic jams mechanisms. Remember that at the next lid, lever or door.")
		await _w.say("", "You lay a knot of Stone across the hinge. The lid heaves once against it and gives up. Inside: gold, and a row of blades folded flat like a fan.")
	elif choice == "Open it from the side":
		adv.set_run_flag("chest_gold")
		await _w.say("", "You stand where the floor is unscratched and lift the lid with the butt of your staff. Blades whicker out across the place you are not standing.\n\nThe gold is real.")
	else:
		adv.add_condition("wounded")
		await _w.say("", "Teeth. The chest had teeth, and the marks on the floor had told you exactly where.\n\n(WOUNDED: −1 cast in your next duel. The gold is real, at least.)")
	_w.rebuild()


func trog_ritual() -> void:
	var adv := _adv()
	if adv.run_flag("trog_rite"):
		return
	var choice: String = await _w._dialogue.choose_async("The tribe waits.", ["Join the ritual", "Run the arrow", "Attack"])
	if choice == "Join the ritual":
		adv.set_run_flag("trog_rite")
		await _w.say("", "You dance badly and sincerely. The tribe approves of sincerity.")
	elif choice == "Run the arrow":
		adv.set_run_flag("trog_ran")
		await _w.say("", "Bridges, drums, black water — and then, impossibly, quiet.")
	else:
		await _w.start_battle_request({
			"enemy_id": "trog_champion", "encounter_id": "trog_champ1", "kind": "wizard",
			"area": "dd_troglodytes", "player_mods": adv.player_mods(), "ward_ban": [],
		})


## P6 final door (p.364, 62, 241, 400). Choice-owned; locks like gate_choice.
func igbut_door() -> void:
	var adv := _adv()
	_w.lock_input(true)
	if adv.flag("dungeon_complete"):
		await _w.say("Igbut", "The door is open. Fang is waiting, Champion.")
		_w.lock_input(false)
		return
	var choice: String = await _w._dialogue.choose_async("The black door?", ["Face the door", "Not yet"])
	if choice != "Face the door":
		_w.lock_input(false)
		return
	var gems: Array = adv.run_state().get("gems", [])
	if not ("emerald" in gems and "sapphire" in gems and "diamond" in gems):
		await _w.say("Igbut", "The gnome counts on his fingers. Counts again.")
		await _w.say("Igbut", "Emerald. Sapphire. Diamond. THREE are required, contestant. The Trial does not bargain.")
		_w.lock_input(false)
		return
	await _w.say("Igbut", "Three sockets. Three gems. Place them true, and mind the bite.")
	await _gem_lock(adv)
	_w.lock_input(false)


func _gem_lock(adv: Node) -> void:
	# p.62 as positional deduction: six orders, aggregate true/displaced feedback.
	var correct := ["Sapphire", "Emerald", "Diamond"]
	var orders := [
		"Emerald, Sapphire, Diamond", "Emerald, Diamond, Sapphire",
		"Sapphire, Emerald, Diamond", "Sapphire, Diamond, Emerald",
		"Diamond, Emerald, Sapphire", "Diamond, Sapphire, Emerald",
	]
	var strikes := 0
	while strikes < 3:
		var pick: String = await _w._dialogue.choose_async("Place the gems?", orders)
		if pick == "Sapphire, Emerald, Diamond":
			await _w.say("", "The sockets drink the gems. The door sighs open.")
			await _w.say("Igbut", "Ha! Walk through, Champion—")
			await _w.flash(Color(1.0, 0.9, 0.6), 0.4)
			await _w.shake(8.0, 0.5)
			await _w.say("", "A crossbow sings from the dark Sukumvit built. Igbut does not finish.")
			await _w.say("", "You walk past him into daylight, and Fang roars your name.\n\n— CHAMPION OF THE TRIAL —")
			adv.set_flag("dungeon_complete")
			_w.load_area("trial_gate", Vector2i(9, 6), "down")
			adv.save()
			return
		strikes += 1
		var tried: Array = pick.split(", ")
		var placed := 0
		for i in range(3):
			if tried[i] == correct[i]:
				placed += 1
		var present := 0
		for gm in tried:
			if gm in correct:
				present += 1
		await _w.say("Igbut", "%d placed true, %d displaced." % [placed, present - placed])
		if strikes < 3:
			adv.add_condition("wounded")
			await narrate("The door bites. (WOUNDED: −1 cast in your next duel.)")
	# D5: a failed lock is not a battle defeat. The door spits the gems back and
	# seals its sockets; you must gather them off the floor before trying again.
	await _w.flash(Color(0.9, 0.3, 0.2), 0.3)
	await _w.shake(6.0, 0.4)
	await narrate("The third blast throws the gems out of your hands and across the floor. The sockets grind shut.\n\nIgbut, from behind the plinth: \"They reopen. They always reopen. Pick up your stones, contestant.\"")
	for gm in ["emerald", "sapphire", "diamond"]:
		if gm in adv.run_state().get("gems", []):
			adv.run_state()["gems"].erase(gm)
	adv.set_run_flag("gems_scattered")
	for gm in ["emerald", "sapphire", "diamond"]:
		adv.set_run_flag("picked_scattered_" + gm, false)
	_w.rebuild()
	adv.save()


## Called by the Overworld after returning from a battle.
func on_battle_result(r: Dictionary) -> void:
	var adv := _adv()
	var req: Dictionary = r.get("request", {})
	var outcome := str(r.get("outcome", ""))
	var enemy_name := str(DmbBestiary.get_data(str(req.get("enemy_id", "giant_fly")))["display_name"])
	_w.lock_input(true)
	if outcome == "victory":
		if req.get("on_win_flag", "") != "":
			adv.set_flag(str(req["on_win_flag"]))
		if req.get("on_win_run_flag", "") != "":
			adv.set_run_flag(str(req["on_win_run_flag"]))
		var grant: Dictionary = req.get("grant_on_win", {})
		if not grant.is_empty():
			if grant.has("spell"):
				adv.learn_spell(int(grant["spell"]))
			if grant.has("weave"):
				adv.grow_weave(int(grant["weave"]))
			_w.rebuild()
			await _w.say("", str(grant.get("text", "")))
			await _w._show_progression_card(grant)
		else:
			_w.rebuild()
			var eid := str(req.get("encounter_id", ""))
			if eid == "boa_grotto1":
				await _w.say("", "The snake loosens. The elven woman breathes — barely.")
			elif eid == "red_settle" or str(req.get("on_win_flag", "")) == "beat_red_wizard":
				await _w.say("Red Wizard", "...A woodcutter. With half the Trial behind him.")
				await _w.say("", "He's gone before the dust settles. The rivalry will have to wait for daylight.")
			elif eid == "trog_champ1":
				await _w.say("", "Their champion falls. The tribe backs off, drumming — respect, or arithmetic.")
			elif eid == "throm_arena":
				adv.set_contestant("throm", "dead")
				await _w.say("", "Throm falls. The delirium goes out of him like water, and for a moment he knows you.")
				await _w.say("Throm", "...Good fight, villager.")
				await _w.say("", "The Dwarf approaches with a loaded crossbow, and does not lower it.")
				await _w.say("Dwarf", "Only I know the way onward. West, when you're ready.")
			elif eid == "troll_lower1":
				adv.set_contestant("throm", "wounded")
				await _w.say("", "Your troll goes down. Throm finishes his — but his arm hangs wrong.\n\n\"Keep walking,\" he says. \"Don't look at it.\"")
				await _w.say("", "Something glints where your troll fell.")
			elif eid.begins_with("ashby_"):
				await _ashby_after(adv, eid, "victory")
			elif str(req.get("drops", "")) != "":
				await narrate("%s falls apart. Something is left where it stood." % enemy_name)
			elif str(req.get("on_win_flag", "")) == "beat_red_wizard":
				pass
			else:
				await narrate("%s is broken. The path is clearer." % enemy_name)
		if str(req.get("on_win_flag", "")) == "beat_red_wizard":
			await narrate("The Red Wizard's Ward shatters. He stares at his own hands for a long moment.")
			await _w.say("Red Wizard", "...A woodcutter. With Halvard's stick.")
			await _w.say("Red Wizard", "Count yourself lucky I have somewhere to be.")
			await narrate("He goes. The hill is quiet.")
	elif outcome == "defeat" or outcome == "fled":
		await _on_defeat(adv, req, outcome, enemy_name)
	elif outcome == "stalemate":
		await narrate("Both of you run dry. %s slinks back into place." % enemy_name)
	else:
		await narrate("You step back from %s." % enemy_name)
	adv.save()
	_w.lock_input(false)


## Defeat dispatch by battle-result policy (brief §22–§27). The UI has already
## reported; this is the only place that decides what losing means.
func _on_defeat(adv: Node, req: Dictionary, outcome: String, enemy_name: String) -> void:
	var policy := str(adv.last_battle_result.get("policy", adv.battle_policy_for(req)))
	match policy:
		adv.POLICY_PROLOGUE:
			await _prologue_defeat(adv, req)
		adv.POLICY_TRAINING:
			await _training_defeat(adv, req, enemy_name)
		_:
			# Fleeing a serious battle counts as a defeat; declining never reaches here.
			await _story_defeat(adv, req, enemy_name)


## Training losses teach and return John to the lesson. No reset, no penalty.
func _training_defeat(adv: Node, req: Dictionary, _enemy_name: String) -> void:
	var grant: Dictionary = req.get("grant_on_defeat", {})
	if not grant.is_empty():
		if grant.has("spell"):
			adv.learn_spell(int(grant["spell"]))
		if grant.has("weave"):
			adv.grow_weave(int(grant["weave"]))
		_w.rebuild()
		if grant.has("text"):
			await narrate(str(grant["text"]))
		await _w._show_progression_card(grant)
	if str(req.get("on_defeat_flag", "")) != "":
		adv.set_flag(str(req["on_defeat_flag"]))
	await _ashby_after(adv, str(req.get("encounter_id", "")), "defeat")


## Real defeats: once, John is left for dead and wakes where he fell; the second
## time the story leaves the Trial for Jane (placeholder chapter, Phase 8).
func _story_defeat(adv: Node, req: Dictionary, enemy_name: String) -> void:
	var result := str(adv.record_story_defeat())
	if result == "left_for_dead":
		var eid := str(req.get("encounter_id", ""))
		if eid != "":
			adv.mark("watching", eid)
		_w.rebuild()
		await narrate("%s does not finish you. It doesn't have to. You go down, and the dark takes its time.\n\nLater — you can't say how much later — you are still here, on the same stone, and it is still watching you. Whatever it decided, it was not 'finish him'." % enemy_name)
		return
	await narrate("This time nothing decides to wait.")
	await _w.fade_out(0.6)
	_w.load_area("jane_placeholder", Vector2i(4, 4), "down")
	adv.save()
	await jane_wake()


## Narrator voice (brief §5). Every narrator line goes through here so the
## blank-speaker convention lives in one place.
func narrate(text: String) -> void:
	await _w.say("", text)


## PLACEHOLDER for the future Jane chapter (brief §24). Deliberately minimal.
func jane_wake() -> void:
	var adv := _adv()
	if adv.flag("jane_placeholder_seen"):
		return
	adv.set_flag("jane_placeholder_seen")
	_w.lock_input(true)
	await narrate("You wake because somebody is arguing with a kettle.")
	await narrate("This is not the Trial. This is not Ashwell. The ceiling has beams, and the beams have herbs hanging from them, and none of that was true a moment ago.")
	await narrate("A woman named Jane has apparently decided you are not allowed to die.\n\nThat is going to complicate things.")
	await narrate("— TO BE CONTINUED —\n\n(The wider world begins here. It has not been built yet.)")
	adv.save()
	_w.lock_input(false)
