extends SceneTree

## Headed Wizard Mode launch test (execution plan A.3 and A.4). The campaign world is the real HybridWorld with its six faction AIs: the scene
## connects, the factions are simulated for 90 game seconds and build, the wizard comes up to a real Red worker outside its hut, clicks it with a
## real mouse press, chooses "Talk to <name>" in its label, and the story dialogue opens with that worker's name. A.4 adds the save and load part.
## Needs the sim on HYBRID_SIM_PORT with HYBRID_PROFILE=campaign (the AIs are on by default).

var _world: Node
var _fails: Array[String] = []
var _dir := ""
var _seq := 0


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("LAUNCH %s %s" % ["ok  " if ok else "FAIL", label])
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
	print("LAUNCH_SHOT %s" % name)


func _by_id(id: String) -> Dictionary:
	for e in _world._snapshot.get("entities", []):
		if str(e.get("id", "")) == id:
			return e
	return {}


## Advance the simulation by game seconds, in short calls (the client waits at most four real seconds for a reply).
func _sim_advance(seconds: int) -> void:
	var left := seconds
	while left > 0:
		var chunk := mini(left, 5)
		left -= chunk
		_seq = int(_world._snapshot.get("clock_sequence", _seq)) + 1
		var reply: Dictionary = _world._sim.op({"op": "advance", "ms": chunk * 1000, "sequence": _seq, "tree_delta": true})
		if str(reply.get("status", "")) == "ok":
			_world._apply_snapshot(reply.get("snapshot", {}))


func _buildings(faction: String) -> int:
	var n := 0
	for e in _world._snapshot.get("entities", []):
		if str(e.get("class", "")) == "building" and str(e.get("faction_name", "")) == faction:
			n += 1
	return n


func _total_buildings() -> int:
	var n := 0
	for f in ["Red", "Blue", "Green", "Yellow", "Purple", "Orange"]:
		n += _buildings(f)
	return n


## The Red worker outside its hut that is nearest the wizard ("" when there is none).
func _nearest_red_worker() -> String:
	var me: Vector2i = _world._john_pos
	var best := ""
	var bd := 1 << 30
	for e in _world._snapshot.get("entities", []):
		if str(e.get("class", "")) == "worker" and str(e.get("faction_name", "")) == "Red" and not bool(e.get("inside", false)):
			var d := absi(me.x - int(e["tx"])) + absi(me.y - int(e["ty"]))
			if d < bd:
				bd = d
				best = str(e["id"])
	return best


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


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = "res://../WizardRTSHybrid/docs/evidence/narrative/a"
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	await _frames(40)

	# ---- the integrated launch: the real world, the campaign profile, Wizard Mode state present
	var prof: Dictionary = _world._sim.op({"op": "profile"})
	_check(str(prof.get("profile", "")) == "campaign", "the campaign profile (%s)" % str(prof.get("profile", "")))
	var story: Dictionary = _world._snapshot.get("story", {})
	_check(story.has("narrative") and story.has("persons"), "the snapshot carries the Wizard Mode narrative state")
	var before := _total_buildings()
	var red_before := _buildings("Red")
	_sim_advance(90)
	await _frames(4)
	var after := _total_buildings()
	var grew: PackedStringArray = []
	for f in ["Red", "Blue", "Green", "Yellow", "Purple", "Orange"]:
		grew.append("%s %d" % [f, _buildings(f)])
	_check(after > before, "the factions play on their own: buildings %d -> %d after 90 game seconds (Red %d -> %d; now %s)" % [before, after, red_before, _buildings("Red"), ", ".join(grew)])

	# ---- the simulation's own worker is a named, talkable character
	_world.paused = true  # nothing moves between the click and the answer
	_world.wizard_labels.enabled = true
	var wid := _nearest_red_worker()
	for _i in 6:
		if wid != "":
			break
		_sim_advance(10)
		wid = _nearest_red_worker()
	_check(wid != "", "a Red worker is outside its hut")
	if wid == "":
		print("HYBRID_LAUNCH_FAIL ", ", ".join(_fails))
		quit(1)
		return
	_check(await _teleport_next_to(wid), "the wizard stands beside it")
	_sim_advance(2)  # the narrative tick gives the bodies near the wizard a character (the worker keeps walking meanwhile)
	_check(await _teleport_next_to(wid), "the wizard stands beside it again")
	await _frames(4)
	var persons: Dictionary = _world.story_ui.persons()
	_check(persons.has(wid), "the worker %s has a character in story.persons (%d near the wizard)" % [wid, persons.size()])
	var pname: String = _world.story_ui.person_name(wid)
	_check(pname != "" and pname.contains(" "), "the character has a full name (%s)" % pname)
	_world._camera.zoom = Vector2(1.0, 1.0)
	await _click_entity(wid)
	var lbl = _world.wizard_labels.label_for(wid)
	for _retry in 2:
		if lbl != null and lbl.interaction_state() == "RESPONSES":
			break
		await _click_entity(wid, 0.2)
		lbl = _world.wizard_labels.label_for(wid)
	_check(lbl != null and lbl.interaction_state() == "RESPONSES", "clicking the worker opens its label with choices (state %s)" % (lbl.interaction_state() if lbl != null else "none"))
	var talk_offered := false
	if lbl != null:
		for t in lbl.response_labels():
			if str(t).begins_with("Talk to " + pname):
				talk_offered = true
	_check(talk_offered, "the label offers 'Talk to %s'" % pname)
	_check(pname in str(lbl.display_text()) if lbl != null else false, "the label names the worker")
	await _frames(20)  # the label finishes its one-line speech and arms its choices (the wizard test waits the same)
	var t0 := Time.get_ticks_msec()
	while lbl != null and not lbl.responses_input_armed() and Time.get_ticks_msec() - t0 < 5000:
		await _frames(2)  # the label arms its choices a moment after they appear
	if lbl != null:
		lbl.press_response(2)
	t0 = Time.get_ticks_msec()
	while not _world.story_ui.dialog.visible and Time.get_ticks_msec() - t0 < 5000:
		await _frames(2)
	var sui = _world.story_ui
	_check(sui.dialog.visible, "the dialogue opens")
	_check(str(sui.dialog_title.text) == pname, "the dialogue title is the worker's name (%s)" % str(sui.dialog_title.text))
	_check(str(sui.dialog_text.text).contains(pname), "the first line is the worker introducing themselves")
	await _shot("launch_talk")
	sui.close_dialog()
	await _frames(4)
	_check(not sui.dialog.visible, "the dialogue closes")

	if _fails.is_empty():
		print("HYBRID_LAUNCH_OK")
		quit(0)
	else:
		print("HYBRID_LAUNCH_FAIL ", ", ".join(_fails))
		quit(1)
