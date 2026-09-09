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
			if eid == "troll_lower1":
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
