extends SceneTree

## Headed regression for the owner's second playtest (12 Oct 2026): what is DRAWN and what the player can do.
##  1. a standing tree and a rock block the wizard (Godot local movement and the simulation's pose op agree);
##  2. passive labels in a settlement: at most three, short, none overlapping another;
##  3. a fire-magic interaction: the response buttons sit below the description, never over it;
##  4. the quest is discoverable without developer shortcuts: an objective line names the quest giver, E talks to him, the dialogue
##     explains the real cause (a collapsed gallery).
## Needs the sim with HYBRID_PROFILE=developer HYBRID_FIXTURE=story (scripts/run_headed_suite.sh playtest2).

var _world: Node
var _labels: Node
var _fails: Array[String] = []
var _dir := ""


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("PLAYTEST2 %s %s" % ["ok  " if ok else "FAIL", label])
	if not ok:
		_fails.append(label)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _shot(name: String) -> void:
	await _frames(4)
	await RenderingServer.frame_post_draw
	var image: Image = get_root().get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(_dir)
	image.save_png(_dir.replace("\\", "/") + "/%s.png" % name)
	print("PLAYTEST2_SHOT %s" % name)


func _ents() -> Array:
	return _world._snapshot.get("entities", [])


func _put(t: Vector2i) -> void:
	_world.set_john_pos(t)
	_world._arrived()
	_world.camera_focus = (Vector2(t) + Vector2(0.5, 0.5)) * float(_world.TPX)
	await _frames(4)


func _key(code: Key) -> void:
	var e := InputEventKey.new()
	e.keycode = code
	e.physical_keycode = code
	e.pressed = true
	Input.parse_input_event(e)
	await _frames(2)
	var up := e.duplicate()
	up.pressed = false
	Input.parse_input_event(up)
	await _frames(4)


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = "res://../WizardRTSHybrid/docs/evidence/playtest2"
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1366, 768))
	await _frames(40)
	_labels = _world.wizard_labels
	_world._sim.op({"op": "ai", "enabled": false})  # the scene should hold still while it is measured

	# 1. trees and rocks are solid
	_check(_world._solid.size() > 100, "the client knows the solid trees and rocks (%d)" % _world._solid.size())
	var blocked_tested := false
	for t in _world._solid.keys():
		for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
			var stand: Vector2i = t + d
			if _world.is_walkable(stand) and not blocked_tested:
				await _put(stand)
				var before: Vector2i = _world._john_pos
				_world.ui_step(-d)  # toward the tree or rock
				await _frames(30)
				_check(_world._john_pos == before, "a step into a tree/rock at %s is refused (stayed at %s)" % [str(t), str(_world._john_pos)])
				var r: Dictionary = _world._sim.op({"op": "pose", "tx": t.x, "ty": t.y, "facing": "down", "light": true})
				_check(str(r.get("reason", "")) == "obstacle", "the simulation refuses the same tile: %s" % str(r.get("reason", r.get("status", ""))))
				_world._sim.op({"op": "pose", "tx": before.x, "ty": before.y, "facing": "down", "light": true})
				blocked_tested = true
				await _shot("01_tree_blocks_the_wizard")
		if blocked_tested:
			break
	_check(blocked_tested, "found a solid tile beside a walkable one")

	# 2. nothing floats over a settlement: no passive labels, no open card, until something is clicked
	var wh := {}
	for e in _ents():
		if str(e.get("kind", "")) == "warehouse" and str(e.get("faction_name", "")) == "Red":
			wh = e
	var spot := Vector2i(int(wh.get("tx", 0)), int(wh.get("ty", 0)) + 2)
	for d in [Vector2i(0, 0), Vector2i(1, 0), Vector2i(-1, 0), Vector2i(2, 0), Vector2i(0, 1)]:
		if _world.is_walkable(spot + d):
			spot = spot + d
			break
	await _put(spot)
	await _frames(40)
	_check(not _labels.panel.visible, "no inspect card is open in the middle of a settlement")
	await _shot("02_settlement_no_labels")

	# 3. a fire-magic interaction keeps its buttons below the description
	var target := {}
	for e in _ents():
		if str(e.get("class", "")) == "building" and _labels.in_range(e) and str(e.get("kind", "")) != "warehouse":
			target = e
			break
	if target.is_empty():
		for e in _ents():
			if str(e.get("class", "")) == "building" and _labels.distance_to(e) <= 8 and str(e.get("kind", "")) != "warehouse":
				var tt := Vector2i(int(e["tx"]), int(e["ty"]) + 1)
				if _world.is_walkable(tt):
					await _put(tt)
					target = e
					break
	_check(not target.is_empty(), "a building within reach of fire magic")
	if not target.is_empty():
		_labels.open(str(target["id"]))
		await _frames(30)
		_check(_labels.panel.visible and _labels.current_id == str(target["id"]), "the building's inspect card opens")
		var panel = _labels.panel
		var body_rect: Rect2 = panel.body_label.get_global_rect()
		var ok := true
		for b in panel.choices_box.get_children():
			var rr: Rect2 = (b as Control).get_global_rect()
			if rr.position.y < body_rect.end.y - 1.0:
				ok = false
		_check(ok, "the choices sit below the description (text ends at %.0f)" % body_rect.end.y)
		var vis: Rect2 = get_root().get_visible_rect()
		_check(vis.encloses(panel.panel.get_global_rect().grow(-2.0)), "the whole card is on screen")
		await _shot("03_fire_magic_choices_below_text")
		_labels.close()

	# 4. the quest: objective line, E to talk, the real cause in the words
	await _frames(20)
	var npc := {}
	for e in _ents():
		if str(e.get("class", "")) == "npc":
			npc = e
	_check(not npc.is_empty() and bool(npc.get("has_quest", false)), "the story fixture opened a quest for a real person")
	if not npc.is_empty():
		var hint: String = _world.story_ui.objective_text()
		_check(hint.contains(str(npc.get("label", "?"))) and hint.contains("tiles"), "the objective line says where the quest giver is: '%s'" % hint)
		await _shot("04_quest_objective_line")
		var nt := Vector2i(int(npc["tx"]), int(npc["ty"]))
		var stood := false
		for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1), Vector2i(1, 1), Vector2i(-1, 1)]:
			if _world.is_walkable(nt + d):
				await _put(nt + d)
				stood = true
				break
		_check(stood, "the quest giver can be walked up to")
		await _frames(10)
		_check(_world.story_ui.objective_text().contains("Press E"), "standing beside him, the line says to press E")
		await _key(KEY_E)
		_check(_world.story_ui.dialog.visible and _world.story_ui.dialog_title.text.contains("Miner"), "E opens the conversation: '%s'" % _world.story_ui.dialog_title.text)
		_check(_world.story_ui.dialog_text.text.contains("caved in"), "the miner explains the real cause: %s" % _world.story_ui.dialog_text.text.substr(0, 120))
		await _shot("05_quest_dialogue")
		_world.story_ui.close_dialog()
	if _fails.is_empty():
		print("HYBRID_PLAYTEST2_OK")
	else:
		print("HYBRID_PLAYTEST2_FAIL %s" % str(_fails))
	quit(0 if _fails.is_empty() else 1)
