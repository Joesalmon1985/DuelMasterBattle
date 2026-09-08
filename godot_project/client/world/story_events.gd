extends RefCounted
class_name StoryEvents

## Scripted sequences for the first adventure. Each event is an async function
## driving the Overworld's cutscene helpers. World progression after battles is
## handled here too (never inside the battle UI).

var _w  # Overworld


func setup(world) -> void:
	_w = world


func _adv() -> Node:
	return _w.get_node("/root/Adventure")


func run_event(id: String) -> void:
	match id:
		"opening_fight":
			await opening_fight()


func opening_text() -> void:
	_w.lock_input(true)
	await _w.say("", "You are a woodcutter called John.")
	await _w.say("", "You should probably cut some wood.")
	_w.lock_input(false)


func opening_fight() -> void:
	var adv := _adv()
	_w.lock_input(true)
	var jp: Vector2i = _w.john_pos()
	await _w.say("", "The birds stop.")
	await _w.flash(Color(0.9, 0.95, 1.0), 0.25)
	await _w.shake(8.0, 0.5)
	# Wizards arrive from the north path.
	_w.spawn_actor("blue", "blue_mage", Vector2i(7, 0), "down")
	_w.spawn_actor("red", "red_mage", Vector2i(9, 0), "down")
	_w.face_john("up")
	await _w.move_actor("blue", Vector2i(6, 6), 0.9)
	await _w.move_actor("red", Vector2i(10, 6), 0.9)
	_w.face_actor("blue", "right")
	_w.face_actor("red", "left")
	await _w.say("", "Two figures fall out of the sky in a wrapping of lightning. One in blue. One in red.\n\nThey do not see you. They are busy.")
	# Exchange of bolts.
	for i in range(3):
		await _w.bolt(Vector2i(10, 6), Vector2i(6, 6), Color(1.0, 0.35, 0.2), 0.3)
		await _w.shake(4.0, 0.15)
		await _w.bolt(Vector2i(6, 6), Vector2i(10, 6), Color(0.3, 0.6, 1.0), 0.3)
		await _w.wait(0.15)
	await _w.say("Red wizard", "You are slow, Halvard.")
	await _w.bolt(Vector2i(10, 6), Vector2i(6, 6), Color(1.0, 0.4, 0.1), 0.25)
	await _w.bolt(Vector2i(10, 6), Vector2i(6, 6), Color(1.0, 0.2, 0.1), 0.2)
	await _w.flash(Color(1.0, 0.5, 0.2), 0.3)
	await _w.shake(10.0, 0.5)
	await _w.move_actor("blue", Vector2i(6, 8), 0.4)
	_w.actor("blue").rotation_degrees = 90
	_w.actor("blue").position += Vector2(_w.TPX, 0)
	await _w.say("", "The trees around you are burning.")
	_w.face_actor("red", "up")
	await _w.say("Red wizard", "Keep the stick. Burn with it.")
	await _w.move_actor("red", Vector2i(9, 0), 0.8)
	_w.remove_actor("red")
	await _w.say("", "The Red wizard walks north into the smoke and is gone.")
	# John approaches the Blue wizard.
	_w.face_john("left")
	await _w.say("Blue wizard", "...You. Woodcutter. Come here.")
	await _w.say("Blue wizard", "I have not got long. Take the staff. Do not ask me what it is — you'll find out the wet way.")
	await _w.say("Blue wizard", "He weaves four. I wove four. You'll weave one, and that has to be enough to start.")
	await _w.say("", "His hand opens. The staff rolls into the grass at your feet.")
	adv.set_flag("opening_done")
	_w.remove_actor("blue")
	_w.rebuild()
	await _w.say("", "The forest is on fire, and you have been given something you do not understand.\n\nMaybe pick it up.")
	adv.save()
	_w.lock_input(false)


## Called by the Overworld after returning from a battle.
func on_battle_result(r: Dictionary) -> void:
	var adv := _adv()
	var req: Dictionary = r.get("request", {})
	var outcome := str(r.get("outcome", ""))
	var enemy_name := str(DmbBestiary.get_data(str(req.get("enemy_id", "flame_wisp")))["display_name"])
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
			if eid == "wisp_h1" and not adv.flag("first_win_told"):
				adv.set_flag("first_win_told")
				await _w.say("", "The wisp bursts into steam. That was a battle, then: your spell against its Ward, and its Ward gave.\n\nThe next ones will hide better.")
			elif str(req.get("drops", "")) != "":
				await _w.say("", "%s falls apart. Something is left where it stood." % enemy_name)
			elif eid == "beat_red_wizard" or str(req.get("on_win_flag", "")) == "beat_red_wizard":
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
		var enemy := DmbBestiary.get_data(str(req.get("enemy_id", "flame_wisp")))
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
