extends SceneTree

## Headed proof of the character system in the real wizard world: the people the simulation draws, a conversation with a story
## person (the right mouth moves, the wizard answers, both return to idle), soldiers, and screenshots of each.
## Needs the sim on HYBRID_SIM_PORT, started with HYBRID_FIXTURE=story HYBRID_ALLOW_SPAWN=1.
##
##   HYBRID_SIM_PORT=8801 HYBRID_SHOT_DIR=/some/dir godot --path godot_project --disable-vsync res://client/tests/run_hybrid_characters.gd

const Appearance = preload("res://client/characters/character_appearance.gd")
const Bus = preload("res://client/characters/character_bus.gd")
const Anim = preload("res://client/characters/character_anim.gd")

var _world: Node
var fails := 0


func _init() -> void:
	call_deferred("_run")


func check(cond: bool, what: String) -> void:
	if not cond:
		fails += 1
		print("FAIL: ", what)
	else:
		print("ok:   ", what)


func _ents() -> Array:
	return _world._snapshot.get("entities", [])


func _focus(tile: Vector2, zoom := 1.0) -> void:
	_world.camera_focus = (tile + Vector2(0.5, 0.5)) * _world.TPX
	_world._camera.zoom = Vector2(zoom, zoom)


func _shot(name: String) -> void:
	for _i in 4:
		await process_frame
	await RenderingServer.frame_post_draw
	var dir := OS.get_environment("HYBRID_SHOT_DIR")
	if dir == "":
		dir = "/tmp/hybrid_character_shots"
	DirAccess.make_dir_recursive_absolute(dir)
	var image: Image = get_root().get_viewport().get_texture().get_image()
	image.save_png(dir + "/%s.png" % name)
	print("SHOT ", name)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _run() -> void:
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(720, 1000))
	await _frames(30)
	if _world._snapshot.is_empty():
		print("HYBRID_CHARACTERS_FAIL no snapshot")
		quit(1)
		return
	_world._sim.op({"op": "speed", "scale": 4})
	_world._input_locked = true
	# ---- 1. the people of the simulation are drawn by the character system
	var player: Dictionary = _world._snapshot.get("player", {})
	var pt := Vector2(float(player.get("tx", 0)), float(player.get("ty", 0)))
	# the wizard first: the player stands among their faction's settlement
	var people := []
	for e in _ents():
		if str(e.get("class", "")) in ["worker", "carrier", "unit", "npc"] and not Appearance.is_animal_definition(str(e.get("definition", ""))):
			people.append(e)
	check(people.size() > 5, "the world has people to draw (%d)" % people.size())
	_focus(pt, 1.0)
	await _shot("01_wizard_and_settlement")
	await _frames(20)
	check(_world._art.crowd.count() > 0, "the crowd tracks %d people" % _world._art.crowd.count())
	check(Appearance.unmapped.is_empty(), "every person definition maps to an outfit (unmapped: %s)" % str(Appearance.unmapped.keys()))
	# the player is a Sprite2D with a character view, not a rectangle
	var view = _world._john.get_node_or_null("CharView")
	check(view != null, "the wizard is drawn by a character view")
	check(not _world._john.has_meta("placeholder") or not bool(_world._john.get_meta("placeholder")), "no geometric placeholder on the wizard")
	# ---- 2. workers in motion: pick a moving worker, follow it, require walking frames
	var walker := {}
	var tries := 0
	while walker.is_empty() and tries < 400:
		tries += 1
		await process_frame
		for e in _ents():
			if str(e.get("class", "")) in ["worker", "carrier"] and str(e.get("status", "")) == "moving" and _world._art.crowd.has(str(e.get("id", ""))):
				var an = _world._art.crowd.anim_of(str(e["id"]))
				if an != null and an.state == Anim.S.WALK:
					walker = e
					break
	check(not walker.is_empty(), "a worker is walking and its animation state is WALK")
	if not walker.is_empty():
		_focus(Vector2(float(walker["tx"]), float(walker["ty"])), 1.4)
		await _shot("02_worker_walking")
	var idle_seen := false
	for e in _ents():
		if str(e.get("class", "")) in ["worker", "carrier"] and str(e.get("status", "")) in ["idle", "blocked"] and _world._art.crowd.has(str(e.get("id", ""))):
			var an2 = _world._art.crowd.anim_of(str(e["id"]))
			if an2 != null and an2.state == Anim.S.IDLE:
				idle_seen = true
	check(idle_seen, "a standing worker is in IDLE")
	# ---- 3. a conversation
	var npc := {}
	for e in _ents():
		if str(e.get("class", "")) == "npc":
			npc = e
	check(not npc.is_empty(), "the story fixture put a person to talk to in the world")
	if not npc.is_empty():
		var nid := str(npc["id"])
		_world._john_pos = Vector2i(int(npc["tx"]) + 1, int(npc["ty"]))
		_world._john.position = Vector2(_world._john_pos) * _world.TPX + Vector2(0, -8 * _world.TILE_SCALE)
		_focus(Vector2(float(npc["tx"]), float(npc["ty"])), 1.6)
		_world._sim.op({"op": "pose", "tx": _world._john_pos.x, "ty": _world._john_pos.y, "facing": "left"})
		var pl: Dictionary = _world._snapshot.get("player", {})
		pl["tx"] = _world._john_pos.x
		pl["ty"] = _world._john_pos.y
		await _frames(10)
		var story = _world.story_ui
		check(not Bus.is_speaking(nid), "nobody speaks before the conversation")
		story.use_entity(npc)
		await _frames(6)
		check(story.dialog.visible, "the dialogue opens")
		check(Bus.is_speaking(nid), "the person starts speaking when their line appears")
		var an3 = _world._art.crowd.anim_of(nid)
		check(an3 != null and an3.state == Anim.S.TALK, "their figure plays the TALK animation (%s)" % (an3.state_name() if an3 != null else "none"))
		check(story.portrait.look != null and story.portrait.character_id == nid, "the portrait shows the same person")
		check(not Bus.is_speaking("john"), "the wizard is not speaking while the person is")
		await _frames(20)
		check(story.portrait.shown_poses.keys().any(func(k): return str(k).begins_with("talk")), "the portrait mouth moved (%s)" % str(story.portrait.shown_poses.keys()))
		await _shot("03_conversation_talk")
		# pick the first available answer
		var picked := false
		for c in story.choices_box.get_children():
			if c is Button and not (c as Button).disabled:
				(c as Button).pressed.emit()
				picked = true
				break
		check(picked, "an answer was available")
		await _frames(4)
		if picked:
			check(Bus.is_speaking("john"), "the wizard visibly answers")
			check(not Bus.is_speaking(nid), "while they answer, the other person is quiet")
			await _shot("04_wizard_answers")
			await _frames(110)
			check(Bus.is_speaking(nid) or story.dialog.visible, "then the person replies")
		story.close_dialog()
		await _frames(30)
		check(not Bus.is_speaking(nid) and not Bus.is_speaking("john"), "the conversation ends: nobody speaks")
		var an4 = _world._art.crowd.anim_of(nid)
		check(an4 != null and an4.state == Anim.S.IDLE, "and the person is idle again (%s)" % (an4.state_name() if an4 != null else "none"))
	# ---- 4. soldiers of several tribes
	var spawned := 0
	var base := pt
	for d in ["widelands.wl_soldier", "openra.e1", "openra.e3", "openra.medi", "openra.e6", "openra.spy", "dmb.clubman", "dmb.spearman"]:
		for fac in ["Red", "Blue"]:
			var r: Dictionary = _world._sim.op({"op": "spawn", "faction": fac, "definition": d, "tx": int(base.x) + 2 + spawned % 8, "ty": int(base.y) + 2 + spawned / 8})
			if str(r.get("status", "")) == "ok":
				spawned += 1
	print("spawned ", spawned)
	_world._sim.op({"op": "advance", "ms": 500, "sequence": 9000})
	await _frames(20)
	_focus(base + Vector2(5, 3), 1.2)
	await _shot("05_soldiers")
	var infantry := 0
	for e in _ents():
		if str(e.get("class", "")) == "unit" and _world._art.crowd.has(str(e.get("id", ""))):
			infantry += 1
	check(infantry > 0, "soldiers and infantry are drawn as people (%d)" % infantry)
	check(Appearance.unmapped.is_empty(), "still no unmapped definitions (%s)" % str(Appearance.unmapped.keys()))
	print("HYBRID_CHARACTERS_DONE fails=", fails)
	quit(1 if fails > 0 else 0)
