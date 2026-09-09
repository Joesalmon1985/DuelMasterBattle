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
		await _w.say("", "And he walks on.\n\n— THE TRIAL BEGINS —\n\n(John carries Water and a one-slot weave into the dark. The dungeon opens in the next chapter; Ashwell, the road and the gate remain yours to wander.)")
		adv.save()
	else:
		await _w.say("Rollkeeper", "Then stand clear of the doors. The offer stands until sunset.")
	_w.lock_input(false)


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
			if eid == "ashby_lesson1" and not adv.flag("first_win_told"):
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
