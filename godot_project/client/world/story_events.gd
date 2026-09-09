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
		"duel_cutscene":
			await duel_cutscene()
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
		"mirror_smash":
			await mirror_smash()
		"boulder_run":
			await boulder_run()
		"trog_ritual":
			await trog_ritual()
		"igbut_door":
			await igbut_door()


func opening_text() -> void:
	_w.lock_input(true)
	await _w.say("", "Trial Day in Ashwell.")
	await _w.say("", "You are John. You cut wood. The whole country has come to watch other people die famous.")
	_w.lock_input(false)


func duel_cutscene() -> void:
	var adv := _adv()
	_w.lock_input(true)
	await _w.say("", "Shouting, down by the road.")
	_w.spawn_actor("blue", "blue_mage", Vector2i(1, 8), "right")
	_w.spawn_actor("red", "red_mage", Vector2i(13, 8), "left")
	_w.face_john("down")
	await _w.move_actor("blue", Vector2i(6, 8), 0.9)
	await _w.move_actor("red", Vector2i(11, 8), 0.9)
	_w.face_actor("blue", "right")
	_w.face_actor("red", "left")
	await _w.say("", "Two travelling wizards have fallen to arguing the way wizards do.\n\nOne in blue. One in red. The whole village is watching from a safe distance.")
	for i in range(3):
		await _w.bolt(Vector2i(11, 8), Vector2i(6, 8), Color(1.0, 0.35, 0.2), 0.3)
		await _w.shake(4.0, 0.15)
		await _w.bolt(Vector2i(6, 8), Vector2i(11, 8), Color(0.3, 0.6, 1.0), 0.3)
		await _w.wait(0.15)
	await _w.say("Red Wizard", "You are slow, Halvard.")
	await _w.bolt(Vector2i(11, 8), Vector2i(6, 8), Color(1.0, 0.4, 0.1), 0.25)
	await _w.bolt(Vector2i(11, 8), Vector2i(6, 8), Color(1.0, 0.2, 0.1), 0.2)
	await _w.flash(Color(1.0, 0.5, 0.2), 0.3)
	await _w.shake(10.0, 0.5)
	await _w.move_actor("blue", Vector2i(6, 9), 0.4)
	_w.actor("blue").rotation_degrees = 90
	_w.actor("blue").position += Vector2(_w.TPX, 0)
	await _w.say("", "The blue wizard goes down hard in the dust of the road.")
	_w.face_actor("red", "down")
	await _w.say("Red Wizard", "Don't stare, villager. You'll see worse before sunset.")
	await _w.move_actor("red", Vector2i(18, 8), 0.8)
	_w.remove_actor("red")
	await _w.say("", "The Red Wizard walks on toward the Trial grounds, and is gone.")
	_w.face_john("right")
	await _w.say("Blue wizard", "...You. Woodcutter. Come here.")
	await _w.say("Blue wizard", "Halvard. That's the name for the roll. Take the staff — it carries my seal, and my place.")
	await _w.say("Blue wizard", "Water first. It always answered me easiest.")
	await _w.say("Blue wizard", "Enter if you want. Don't enter because a dying fool told you to.")
	await _w.say("", "His hand opens. The staff rolls into the dust at your feet.")
	adv.set_flag("duel_seen")
	_w.remove_actor("blue")
	_w.rebuild()
	await _w.say("", "The road is quiet. The staff is waiting.\n\nMaybe pick it up.")
	adv.save()
	_w.lock_input(false)


func gate_choice() -> void:
	var adv := _adv()
	_w.lock_input(true)
	if adv.flag("entered_trial"):
		await _w.say("Rollkeeper", "Sunset. Be ready. The doors only open once.")
		_w.lock_input(false)
		return
	await _w.say("Rollkeeper", "Names for the roll. ...John? John the woodcutter? Halvard's seal — it's genuine.")
	await _w.say("Rollkeeper", "Halvard's place is vacant, and you carry his seal. So: do you enter the Trial?")
	var choice: String = await _w._dialogue.choose_async("Do you enter the Trial?", ["Enter the Trial", "Not yet"])
	if choice == "Enter the Trial":
		adv.set_flag("entered_trial")
		await _w.flash(Color(0.9, 0.85, 1.0), 0.4)
		await _w.say("", "The Rollkeeper writes JOHN in the book, and the ink does not come off.")
		await _w.shake(6.0, 0.6)
		await _w.say("", "The enormous doors begin to close behind the contestants.")
		await _w.say("", "For the first time since leaving Ashwell, turning around is no longer an option.")
		await _w.say("", "Ahead, somewhere in the dark, somebody screams.")
		await _w.say("Red Wizard", "Oh, good. The villager. Try to die somewhere I can see.")
		await _w.say("", "And he walks on.\n\n— THE TRIAL BEGINS —")
		adv.start_run()
		_w.load_area("dd_entrance", Vector2i(10, 11), "up")
		await _w.say("", "Crystal light. Six boxes on a stone table — five already taken.\n\nThe doors shut behind you.")
		adv.save()
	else:
		await _w.say("Rollkeeper", "Then stand clear of the doors. The offer stands until sunset.")
	_w.lock_input(false)


## P2 dungeon scenes. These run inside the caller's input lock (npc/pickup
## interaction), so they never lock/unlock themselves. Only gate_choice (a
## trigger event) owns the lock.
func statue_riddle() -> void:
	var adv := _adv()
	if adv.run_flag("riddle_answered"):
		await _w.say("Old man", "The stone keeps its own counsel. So do I, now.")
		return
	await _w.say("Old man", "One hundred? One hundred and fifty? Two hundred?")
	var answer: String = await _w._dialogue.choose_async("Answer the old man?", ["100", "150", "200"])
	adv.set_run_flag("riddle_answer_" + answer)
	adv.set_run_flag("riddle_answered")
	# The canonical correct answer is not yet verified against the book (p.382);
	# every answer continues, so no run can be bricked by a guess here.
	await _w.say("Old man", "Hm. The stone keeps its own counsel.")
	await _w.say("", "Beside him stands a knight in White Road armour, turned to stone mid-step.\n\nSerra went first. This is where first got her.")


func throm_pit() -> void:
	# p.22 (choices) → p.63 / p.184 (→ p.323 / p.149) / p.311, as run flags.
	var adv := _adv()
	if adv.run_flag("pit_crossed"):
		return
	await _w.say("Throm", "Deep water down there. I hold the rope, or you hold it for me. Or we jump it together, and laugh.")
	var choice: String = await _w._dialogue.choose_async("The pit?", ["Let him lower you", "Offer to lower him", "Jump together"])
	if choice == "Offer to lower him":
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
	await _w.say("Dwarf", "Procedure complete. The stone is yours.")
	adv.learn_spell(3)
	adv.grow_weave(3)
	adv.set_run_flag("trial_ready")
	await _w.say("", "The Dwarf presses a grey stone into your hand. It is patient.\n\nYou have learned STONE magic.\nYour weave can now hold THREE spells.")
	await _w._show_progression_card({"spell": 3, "weave": 3})
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
	var adv := _adv()
	var choice: String = await _w._dialogue.choose_async("The wrong eye?", ["Take it", "Leave it"])
	if choice == "Take it":
		adv.add_condition("wounded")
		await _w.say("", "It comes away — and something in the idol's gaze comes with it.\n\n(WOUNDED: −1 cast in your next duel. It was glass. Flawed glass.)")
	else:
		adv.set_run_flag("picked_false_eye", false)
		await _w.say("", "You leave it where it lies.")
		_w.rebuild()


func false_diamond() -> void:
	# p.218: risk your life for the wrong jewel, or don't.
	var adv := _adv()
	var choice: String = await _w._dialogue.choose_async("The fallen warrior's jewel?", ["Take it", "Leave it"])
	if choice == "Take it":
		adv.add_condition("wounded")
		await _w.say("", "The floor opens its eye. You keep the jewel and lose blood.\n\n(WOUNDED. It is glass. It was always glass.)")
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
	if adv.run_flag("picked_dd_torch"):
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
	var choice: String = await _w._dialogue.choose_async("Boulder?", ["Run!", "Hold ground"])
	if choice == "Run!":
		await _w.say("", "You run like the Trial is behind you. It is. The boulder agrees to miss.")
	else:
		adv.add_condition("wounded")
		await _w.say("", "You hold your ground. The ground holds. You don't.\n\n(WOUNDED: −1 cast in your next duel.)")


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
			await _w.say("", "The door bites. (WOUNDED: −1 cast in your next duel.)")
	await _w.say("", "The third blast takes you off your feet. The dark takes the rest.")
	adv.fail_run("lock")
	_w.load_area("trial_gate", Vector2i(9, 6), "down")
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
			elif eid == "ashby_lesson1" and not adv.flag("first_win_told"):
				adv.set_flag("first_win_told")
				await _w.say("Ashby", "There. That was a battle: your spell against my Ward, and my Ward gave.\n\nThe next ones will hide better.")
			elif eid == "ashby_lesson2":
				await _w.say("Ashby", "You read it. That's the whole game, John — read the Ward, then break it.\n\nThe road north will teach you the rest. If you go.")
			elif str(req.get("drops", "")) != "":
				await _w.say("", "%s falls apart. Something is left where it stood." % enemy_name)
			elif str(req.get("on_win_flag", "")) == "beat_red_wizard":
				pass
			else:
				await _w.say("", "%s is broken. The path is clearer." % enemy_name)
		if str(req.get("on_win_flag", "")) == "beat_red_wizard":
			await _w.say("", "The Red wizard's Ward shatters. He stares at his own hands for a long moment.")
			await _w.say("Red wizard", "...A woodcutter. With Halvard's stick.")
			await _w.say("Red wizard", "Count yourself lucky I have somewhere to be.")
			await _w.say("", "He goes. The hill is quiet.\n\nYou are John. You were a woodcutter. You weave four.\n\n— END OF THE FIRST CHAPTER —\n\nThe forest, the village and every creature in it remain yours to wander.")
	elif outcome == "defeat":
		if str(req.get("area", "")).begins_with("dd_"):
			# Death in the dungeon ends the run, not the game.
			adv.fail_run("battle")
			_w.load_area("trial_gate", Vector2i(9, 6), "down")
			await _w.say("", "The dark takes you, %s.\n\nYou wake at the gate with the taste of crystal in your mouth. The run is over — gems, wounds and all. What you learned, you keep." % enemy_name)
			adv.save()
			_w.lock_input(false)
			return
		var john: DmbProgression = adv.progression
		var enemy := DmbBestiary.get_data(str(req.get("enemy_id", "giant_fly")))
		if john.weave_size < int(enemy["ward_size"]):
			await _w.say("", "%s takes you apart. You never had the reach — your weave holds %d, their Ward has %d slots.\n\nYou wake in the grass, singed and alive. Get stronger, then come back." % [enemy_name, john.weave_size, int(enemy["ward_size"])])
		else:
			await _w.say("", "%s breaks your Ward first. You wake in the grass, singed and alive.\n\nYou can try again — their Ward will be different." % enemy_name)
	elif outcome == "stalemate":
		await _w.say("", "Both of you run dry. %s slinks back into place. Try again when you're ready." % enemy_name)
	else:
		await _w.say("", "You step back from %s." % enemy_name)
	adv.save()
	_w.lock_input(false)
