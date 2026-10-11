extends SceneTree

## Headed Wizard Mode interaction test with real mouse events: labels at a distance describe, up close they offer Fire; fire destroys
## the intended tree, a building (through the burning lifecycle) and a unit by stable id; destroyed things leave labels and selection;
## walking and Wizard/God mode switching still work. Needs the sim on HYBRID_SIM_PORT with HYBRID_ALLOW_SPAWN=1.

var _world: Node
var _labels: Node
var _fails: Array[String] = []
var _dir := ""


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("WIZARD %s %s" % ["ok  " if ok else "FAIL", label])
	if not ok:
		_fails.append(label)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _win(pos: Vector2) -> Vector2:
	return pos * (Vector2(DisplayServer.window_get_size()) / get_root().get_visible_rect().size)


func _mouse(vpos: Vector2, pressed: bool) -> void:
	var pos := _win(vpos)
	var e := InputEventMouseButton.new()
	e.position = pos
	e.global_position = pos
	e.button_index = MOUSE_BUTTON_LEFT
	e.pressed = pressed
	e.button_mask = 1 if pressed else 0
	Input.parse_input_event(e)


func _shot(name: String) -> void:
	await _frames(4)
	await RenderingServer.frame_post_draw
	var image: Image = get_root().get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(_dir)
	image.save_png(_dir.replace("\\", "/") + "/%s.png" % name)
	print("WIZARD_SHOT %s" % name)


func _ents() -> Array:
	return _world._snapshot.get("entities", [])


func _by_id(id: String) -> Dictionary:
	for e in _ents():
		if str(e.get("id", "")) == id:
			return e
	return {}


## Put the camera on the entity and click its picture with a real mouse press and release.
func _click_entity(id: String, dy := 0.35) -> void:
	var e := _by_id(id)
	var wp: Vector2 = (Vector2(float(e["tx"]), float(e["ty"])) + Vector2(0.5, dy)) * float(_world.TPX)
	_world.camera_focus = wp
	await _frames(3)
	var sp: Vector2 = _world.get_canvas_transform() * wp
	var m := InputEventMouseMotion.new()
	m.position = _win(sp)
	m.global_position = _win(sp)
	Input.parse_input_event(m)
	await _frames(1)
	_mouse(sp, true)
	await _frames(1)
	_mouse(sp, false)
	await _frames(6)


func _teleport_next_to(id: String) -> bool:
	var e := _by_id(id)
	for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1), Vector2i(2, 0), Vector2i(0, 2), Vector2i(-2, 0), Vector2i(0, -2), Vector2i(2, 1), Vector2i(-2, 1)]:
		var t: Vector2i = Vector2i(int(e["tx"]), int(e["ty"])) + d
		if _world.is_walkable(t):
			_world.set_john_pos(t)
			_world._arrived()  # the same path a finished step takes: tell the simulation where he stands
			await _frames(3)
			return true
	return false


func _wait_sim(cond: Callable, seconds := 30.0) -> bool:
	var t0 := Time.get_ticks_msec()
	while not cond.call():
		await process_frame
		if (Time.get_ticks_msec() - t0) / 1000.0 > seconds:
			return false
	return true


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = "res://../WizardRTSHybrid/docs/evidence/wizard"
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	await _frames(40)
	_labels = _world.wizard_labels
	_check(_labels != null, "wizard labels attached")
	_world._sim.op({"op": "speed", "scale": 1})
	_world._camera.zoom = Vector2(1.0, 1.0)
	_world.camera_focus = Vector2.INF
	await _frames(20)
	var me: Vector2i = _world._john_pos
	_check(_labels.labels().size() > 0, "passive labels appear around the wizard (%d)" % _labels.labels().size())
	_check(_labels.labels().size() <= 6 + 1, "labels stay uncluttered (%d)" % _labels.labels().size())
	await _shot("01_wizard_labels")

	# ---- a distant tree: click describes, never offers fire
	var far_tree := ""
	for e in _ents():
		if str(e.get("class", "")) == "tree" and str(e.get("stage", "")) == "old" and _labels.distance_to(e) >= 10 and _labels.distance_to(e) <= 24:
			far_tree = str(e["id"])
			break
	_check(far_tree != "", "found a distant old tree")
	await _click_entity(far_tree, -0.45)
	var lbl = _labels.label_for(far_tree)
	_check(lbl != null and lbl.interaction_state() == "OBSERVATION", "clicking a distant tree shows its description (state %s)" % (lbl.interaction_state() if lbl != null else "none"))
	_check(lbl != null and lbl.display_text().to_lower().contains("tree"), "the description names the tree: '%s'" % (lbl.display_text() if lbl != null else ""))
	var far_reply: Dictionary = _world._sim.op({"op": "fire", "target": far_tree})
	_check(str(far_reply.get("reason", "")) == "too_far" and not _by_id(far_tree).is_empty(), "the simulation refuses fire from far away (%s)" % str(far_reply.get("reason", "")))
	await _shot("02_far_tree_description")

	# ---- a distant building describes too
	var far_building := ""
	for e in _ents():
		if str(e.get("class", "")) == "building" and _labels.distance_to(e) >= 10 and _labels.distance_to(e) <= 30 and not bool(e.get("destroyed", false)):
			far_building = str(e["id"])
			break
	await _click_entity(far_building, -0.3)
	var blbl = _labels.label_for(far_building)
	_check(blbl != null and blbl.interaction_state() == "OBSERVATION", "clicking a distant building shows its description")

	# ---- approach the tree: Fire unlocks
	_check(await _teleport_next_to(far_tree), "walked next to the tree")
	await _click_entity(far_tree, -0.45)
	lbl = _labels.label_for(far_tree)
	for _k in 8:
		print("WIZARD_TRACE state=%s text='%s' buttons=%d" % [lbl.interaction_state(), lbl.display_text().replace("\n", " | "), lbl._response_buttons.size()])
		await _frames(2)
	_check(lbl != null and lbl.interaction_state() == "RESPONSES", "clicking the tree up close offers choices (state %s)" % (lbl.interaction_state() if lbl != null else "none"))
	await _shot("03_near_tree_choices")
	var other_tree := ""
	for e in _ents():
		if str(e.get("class", "")) == "tree" and str(e["id"]) != far_tree and _labels.distance_to(e) <= 3:
			other_tree = str(e["id"])
			break
	await _frames(20)
	lbl.press_response(0)
	await _frames(5)
	_check(_by_id(far_tree).is_empty(), "Fire destroyed the intended tree")
	_check(other_tree == "" or not _by_id(other_tree).is_empty(), "a neighbouring tree was left alone")
	_check(_labels.label_for(far_tree) == null, "the burned tree's label is gone")
	await _shot("04_tree_burned")

	# ---- a building, through the burning lifecycle
	var target := ""
	for e in _ents():
		if str(e.get("definition", "")) == "widelands.quarry" and str(e.get("faction_name", "")) == "Red":
			target = str(e["id"])
	_check(await _teleport_next_to(target), "walked next to a building")
	var te := _by_id(target)
	var twp: Vector2 = (Vector2(float(te["tx"]), float(te["ty"])) + Vector2(0.5, -0.3)) * float(_world.TPX)
	_world.camera_focus = twp
	await _frames(3)
	var pk: Dictionary = _labels.pick(_world.get_canvas_transform() * twp)
	print("WIZARD_TRACE pick at building centre -> %s (want %s) john=%s bld=%s,%s" % [pk.get("id", "none"), target, _world._john_pos, te["tx"], te["ty"]])
	await _click_entity(target, -0.3)
	var tl = _labels.label_for(target)
	for _k in 4:
		print("WIZARD_TRACE building label=%s state=%s dist=%d text='%s'" % [tl != null, tl.interaction_state() if tl != null else "-", _labels.distance_to(_by_id(target)), tl.display_text().replace("\n", " | ") if tl != null else ""])
		await _frames(3)
	_check(tl != null and tl.interaction_state() == "RESPONSES", "the building offers fire up close")
	await _frames(20)
	tl.press_response(0)
	await _frames(4)
	_check(bool(_by_id(target).get("destroyed", false)), "the building is destroyed in the simulation and burning")
	await _shot("05_building_burning")
	_check(await _wait_sim(func(): return _by_id(target).is_empty(), 30.0), "the ruin is removed after its burn")
	_check(_labels.label_for(target) == null, "no label remains for the building")

	# ---- a nearby military unit
	var me2: Vector2i = _world._john_pos
	var spawn: Dictionary = _world._sim.op({"op": "spawn", "faction": "Blue", "definition": "openra.e1", "tx": me2.x + 1, "ty": me2.y})
	if str(spawn.get("status", "")) != "ok":
		spawn = _world._sim.op({"op": "spawn", "faction": "Blue", "definition": "openra.e1", "tx": me2.x - 1, "ty": me2.y})
	_check(str(spawn.get("status", "")) == "ok", "spawned a unit beside the wizard")
	var uid := str(spawn.get("id", ""))
	var ad: Dictionary = _world._sim.op({"op": "advance", "ms": 100, "sequence": 999999})
	_world._apply_snapshot(ad.get("snapshot", {}))
	await _click_entity(uid, 0.35)
	var ul = _labels.label_for(uid)
	_check(ul != null and ul.interaction_state() == "RESPONSES", "a nearby unit offers fire (state %s)" % (ul.interaction_state() if ul != null else "none"))
	await _frames(20)
	if ul != null:
		ul.press_response(0)
	await _frames(4)
	var urow := _by_id(uid)
	_check(urow.is_empty() or not bool(urow.get("alive", true)), "Fire killed the unit")
	_check(await _wait_sim(func(): return _by_id(uid).is_empty(), 20.0), "the corpse leaves the world and the labels")
	_check(_labels.label_for(uid) == null, "no label remains for the unit")
	_check(not _world.god.selected.has(uid), "the dead unit is not selected")

	# ---- movement and mode switching
	var before: Vector2i = _world._john_pos
	_world.camera_focus = Vector2.INF
	for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
		if _world.is_walkable(before + d):
			_world.ui_step(d)
			break
	await _wait_sim(func(): return not _world.ui_is_moving(), 5.0)
	await _frames(3)
	_check(_world._john_pos != before, "the wizard still walks")
	var pos_wizard: Vector2i = _world._john_pos
	_world.god.toggle()
	await _frames(30)
	_check(_world.god.active, "God Mode opens")
	_check(_labels.labels().size() == 0, "wizard labels are hidden in God Mode (%d)" % _labels.labels().size())
	_world.god.toggle()
	await _frames(30)
	_check(not _world.god.active and _world._john_pos == pos_wizard, "back in Wizard Mode at the same tile")
	await _frames(20)
	_check(_labels.labels().size() > 0, "labels return in Wizard Mode")

	if _fails.is_empty():
		print("HYBRID_WIZARD_OK")
		quit(0)
	else:
		print("HYBRID_WIZARD_FAIL %s" % str(_fails))
		quit(1)
