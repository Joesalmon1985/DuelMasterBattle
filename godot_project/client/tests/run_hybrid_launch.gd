extends SceneTree

## Headed Wizard Mode launch test (execution plan A.3 and A.4). The campaign world is the real HybridWorld with its six faction AIs: the scene
## connects, the factions are simulated for 90 game seconds and build, the wizard comes up to a real Red worker outside its hut, clicks it with a
## real mouse press (the inspect card opens), presses Talk on it, and the conversation opens with that worker's name. A.4: Escape opens the pause menu
## (Save game, Continue), a save to slot `test` then 30 game seconds then a load puts the clock and the wizard back, and the client autosave
## (HYBRID_AUTOSAVE_SECONDS=5) writes `auto` within seconds but never while a dialogue is open.
## Needs the sim on HYBRID_SIM_PORT with HYBRID_PROFILE=campaign (the AIs are on by default) and HYBRID_AUTOSAVE_SECONDS=5, DMB_RUNS shared with the sim.

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


## Let the camera move AND draw before a screen position is computed: a window that is not in front gets no draws, and the canvas transform
## would be the old one (clicks then land on the wrong place).
func _click_at(vpos: Vector2) -> void:
	var m := InputEventMouseMotion.new()
	m.position = _win(vpos)
	m.global_position = _win(vpos)
	Input.parse_input_event(m)
	await _frames(1)
	_mouse(vpos, true)
	await _frames(1)
	_mouse(vpos, false)
	await _frames(4)


func _settle() -> void:
	await _frames(3)
	await RenderingServer.frame_post_draw


func _key(code: int) -> void:
	for pressed in [true, false]:
		var e := InputEventKey.new()
		e.keycode = code
		e.physical_keycode = code
		e.pressed = pressed
		Input.parse_input_event(e)
		await _frames(1)
	await _frames(2)


## Where the simulator writes a slot (the sim and this test share DMB_RUNS; the default is ~/dmb_runs).
func _save_file(slot: String) -> String:
	var runs := OS.get_environment("DMB_RUNS")
	if runs == "":
		runs = OS.get_environment("HOME") + "/dmb_runs"
	return "%s/saves/campaign/%s.pkl" % [runs, slot]


func _wait_until(cond: Callable, seconds := 10.0) -> bool:
	var t0 := Time.get_ticks_msec()
	while not cond.call():
		await _frames(2)
		if (Time.get_ticks_msec() - t0) / 1000.0 > seconds:
			return false
	return true


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


## A story person (the teacher, a villager) stands within eight tiles: the worker walks about, and a click that lands near them opens their dialogue instead.
func _near_resident(e: Dictionary) -> bool:
	for n in _world._snapshot.get("entities", []):
		if typeof(n) == TYPE_DICTIONARY and str(n.get("class", "")) == "npc":
			if maxi(absi(int(n["tx"]) - int(e["tx"])), absi(int(n["ty"]) - int(e["ty"]))) <= 8:
				return true
	return false


## The Red worker outside its hut that is nearest the wizard ("" when there is none).
func _nearest_red_worker() -> String:
	var me: Vector2i = _world._john_pos
	var best := ""
	var bd := 1 << 30
	for e in _world._snapshot.get("entities", []):
		if str(e.get("class", "")) == "worker" and str(e.get("faction_name", "")) == "Red" and not bool(e.get("inside", false)) and not _near_resident(e):
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
	var pos := Vector2(float(e["tx"]), float(e["ty"]))
	var vis: Dictionary = _world._art._vis.get(id, {})
	if not vis.is_empty():
		pos = vis["pos"]  # the art layer glides a figure toward its tile: click where it is drawn, not where it is going
	var wp: Vector2 = (pos + Vector2(0.5, dy)) * float(_world.TPX)
	_world.camera_focus = wp
	await _settle()
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
	await _frames(20)
	_world.story_ui.finish_opening()  # the arrival text belongs to run_hybrid_tutorial.gd

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
	var panel = _world.wizard_labels.panel
	for _retry in 2:
		if panel.visible and _world.wizard_labels.current_id == wid:
			break
		await _click_entity(wid, 0.2)
	_check(panel.visible and _world.wizard_labels.current_id == wid, "clicking the worker opens its inspect card")
	_check(panel.title_label.text == pname, "the card names the worker (%s)" % panel.title_label.text)
	_check(panel.subtitle_label.text.contains("settlement"), "and says what they do (%s)" % panel.subtitle_label.text)
	await _frames(10)
	var talk: Button = panel.choices_box.get_node_or_null("Choice_talk")
	_check(talk != null and not talk.disabled, "the card offers Talk")
	await _settle()
	if talk != null:
		var tc: Vector2 = talk.get_global_rect().get_center()
		await _click_at(tc)
	var t0 := Time.get_ticks_msec()
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

	# ---- A.4: pause menu, save, load
	_check(is_equal_approx(_world.autosave_seconds, 5.0), "HYBRID_AUTOSAVE_SECONDS reaches the client (%s)" % str(_world.autosave_seconds))
	var started_msec := Time.get_unix_time_from_system()
	await _key(KEY_ESCAPE)
	_check(await _wait_until(func(): return _world.menu_card.visible, 5.0), "Escape opens the pause menu")
	_check(_world.autosave_wait_reason() == "menu", "an autosave waits while the menu is open (%s)" % _world.autosave_wait_reason())
	await _settle()
	await _shot("launch_pause_menu")
	var save_btn: Button = _world.menu_card.choice_button("save")
	await _click_at(save_btn.get_global_rect().get_center())
	await _settle()
	_check(_world.menu_card.body_label.text == "Game saved.", "the menu confirms the save (%s)" % _world.menu_card.body_label.text)
	var cont_btn: Button = _world.menu_card.choice_button("continue")
	await _click_at(cont_btn.get_global_rect().get_center())
	_check(await _wait_until(func(): return not _world._menu_open, 5.0), "Continue closes the menu")
	_check(FileAccess.file_exists(_save_file("manual")), "the manual save exists (%s)" % _save_file("manual"))

	var t0_ms := int(_world._snapshot.get("game_ms", 0))
	var home: Vector2i = _world._john_pos
	var saved: Dictionary = _world.save_slot("test")
	_check(str(saved.get("status", "")) == "ok" and int(saved.get("game_ms", -1)) == t0_ms, "save to slot test at game_ms %d (%s)" % [t0_ms, str(saved.get("status", ""))])
	_sim_advance(30)
	_world.set_john_pos(home + Vector2i(0, 3) if _world.is_walkable(home + Vector2i(0, 3)) else home + Vector2i(0, -3))
	_world._arrived()
	await _frames(3)
	var t1_ms := int(_world._snapshot.get("game_ms", 0))
	_check(t1_ms >= t0_ms + 30000, "30 more game seconds pass (%d -> %d)" % [t0_ms, t1_ms])
	var loaded: Dictionary = _world.load_slot("test")
	_check(str(loaded.get("status", "")) == "ok" and not bool(loaded.get("hash_mismatch", true)), "load slot test (%s)" % str(loaded.get("status", loaded.get("reason", ""))))
	_check(int(_world._snapshot.get("game_ms", 0)) == t0_ms, "the clock went back to %d (now %d)" % [t0_ms, int(_world._snapshot.get("game_ms", 0))])
	_check(_world._john_pos == home and int(_world._snapshot["player"]["tx"]) == home.x, "the wizard is where he was saved %s (now %s)" % [str(home), str(_world._john_pos)])
	_check(_world.terrain != null and _world._snapshot.get("entities", []).size() > 100, "the terrain and the world are drawn again (%d rows)" % _world._snapshot.get("entities", []).size())
	_check(_world.story_ui.person_name(wid) == pname, "the worker is still %s after the load" % pname)
	var bad: Dictionary = _world.load_slot("no_such_slot")
	_check(str(bad.get("reason", "")) == "missing" and int(_world._snapshot.get("game_ms", 0)) == t0_ms, "loading a missing slot is refused and changes nothing")

	# ---- A.4: the client autosave waits for a quiet moment
	_world.story_ui.talk_to(wid)
	await _frames(4)
	_check(_world.story_ui.dialog.visible and _world.autosave_wait_reason() == "dialogue", "a dialogue is open and holds the autosave (%s)" % _world.autosave_wait_reason())
	var count_open: int = _world.autosave_count
	await create_timer(7.0).timeout  # longer than HYBRID_AUTOSAVE_SECONDS: the autosave is due but must wait
	_check(_world.autosave_count == count_open, "no autosave while the dialogue is open (count %d)" % _world.autosave_count)
	_world.story_ui.close_dialog()
	_check(await _wait_until(func(): return _world.autosave_count > count_open, 10.0), "the autosave is written within 10 s of the dialogue closing (count %d)" % _world.autosave_count)
	_check(FileAccess.file_exists(_save_file("auto")) and float(FileAccess.get_modified_time(_save_file("auto"))) >= started_msec - 1.0, "auto.pkl exists and is fresh")

	if _fails.is_empty():
		print("HYBRID_LAUNCH_OK")
		quit(0)
	else:
		print("HYBRID_LAUNCH_FAIL ", ", ".join(_fails))
		quit(1)
