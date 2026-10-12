extends SceneTree

## Headed M5 test: an outbreak in the wizard's hex region, seen and treated through the real UI over the one simulation. Needs the sim
## with HYBRID_PROFILE=developer HYBRID_FIXTURE=outbreak (cubes in the wizard's region, cadence off). Real mouse click opens the healer's
## dialogue, real key presses (T) start two treatments, and the picture changes with the simulation (clues, region outline, quest).

var _world: Node
var _ui: Node
var _fails: Array[String] = []
var _dir := ""
var _seq := 0


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("OUTBREAK %s %s" % ["ok  " if ok else "FAIL", label])
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


func _key(code: int) -> void:
	for pressed in [true, false]:
		var e := InputEventKey.new()
		e.keycode = code
		e.physical_keycode = code
		e.pressed = pressed
		Input.parse_input_event(e)
		await _frames(1)
	await _frames(3)


func _shot(name: String) -> Image:
	await _frames(4)
	await RenderingServer.frame_post_draw
	var image: Image = get_root().get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(_dir)
	image.save_png(_dir.replace("\\", "/") + "/%s.png" % name)
	print("OUTBREAK_SHOT %s" % name)
	return image


func _sim_advance(seconds: int) -> void:
	_seq = int(_world._snapshot.get("clock_sequence", _seq)) + 1
	var reply: Dictionary = _world._sim.op({"op": "advance", "ms": seconds * 1000, "sequence": _seq, "tree_delta": true})
	if str(reply.get("status", "")) == "ok":
		_world._apply_snapshot(reply.get("snapshot", {}))


func _entities(kind: String) -> Array:
	var out: Array = []
	for e in _world._snapshot.get("entities", []):
		if str(e.get("kind", "")) == kind:
			out.append(e)
	return out


func _screen_of(e: Dictionary) -> Vector2:
	var wp: Vector2 = (Vector2(float(e["tx"]), float(e["ty"])) + Vector2(0.5, 0.5)) * float(_world.TPX)
	return _world.get_canvas_transform() * wp


func _cd(a: Color, b: Color) -> float:
	return sqrt(pow(a.r - b.r, 2) + pow(a.g - b.g, 2) + pow(a.b - b.b, 2))


func _count_near(img: Image, centre: Vector2, col: Color, tol: float, r := 40) -> int:
	var sc := Vector2(img.get_size()) / get_root().get_visible_rect().size
	var n := 0
	for dy in range(-r, r + 1, 2):
		for dx in range(-r, r + 1, 2):
			var q := Vector2i((centre + Vector2(dx, dy)) * sc)
			if q.x >= 0 and q.y >= 0 and q.x < img.get_width() and q.y < img.get_height() and _cd(img.get_pixelv(q), col) < tol:
				n += 1
	return n


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = "res://../WizardRTSHybrid/docs/evidence/m5"
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	await _frames(40)
	_ui = _world.story_ui
	_world.wizard_labels.enabled = false
	_sim_advance(12)  # the healer's quest opens from the cubes within a second or two
	await _frames(6)
	var reg: Dictionary = _world._snapshot.get("regions", {})
	_check(reg.get("cubes", {}).size() == 2, "the snapshot carries an outbreak in two regions (%s)" % str(reg.get("cubes", {})))
	var clues := _entities("outbreak_clue")
	_check(clues.size() == 3, "one visible clue per cube (%d)" % clues.size())
	var healers: Array = []
	for e in _entities("npc"):
		if str(e.get("role", "")) == "healer":
			healers.append(e)
	_check(healers.size() == 1 and bool(healers[0].get("has_quest", false)), "a healer with a quest stands in the afflicted settlement")
	var healer: Dictionary = healers[0]
	var player: Dictionary = _world._snapshot.get("player", {})
	_world.camera_focus = (Vector2(float(player["tx"]), float(player["ty"])) + Vector2(0.5, 0.5)) * float(_world.TPX)
	_world._camera.zoom = Vector2(0.5, 0.5)
	await _frames(10)
	var img := await _shot("01_outbreak_clues")
	var seen := 0
	for c in clues:
		var sp := _screen_of(c)
		if sp.x > 0 and sp.y > 0 and sp.x < 1280 and sp.y < 720:
			seen += _count_near(img, sp + Vector2(0, -25), Color(0.85, 0.15, 0.7), 0.3, 40)
	_check(seen > 60, "the sickness smoke (magenta) is drawn near the clues (%d pixels)" % seen)
	var outline := _count_near(img, get_root().get_visible_rect().size * 0.5, Color(0.87, 0.39, 0.86), 0.2, 1300)
	_check(outline > 20, "the region outline is drawn (pink hex edge, %d pixels)" % outline)
	# owner playtest (12 Oct 2026): the outbreak must explain itself and its economic effect, and say how to treat it
	var line: String = _ui.objective_text()
	_check(line.contains("marks") and line.contains("Work runs at") and line.contains("Press T"), "the status line names the outbreak, its effect and the T key: '%s'" % line)
	var imp: Dictionary = reg.get("impact", {}).get(str(reg.get("player_region", "")), {})
	_check(float(imp.get("factor", 1.0)) < 1.0 and int(imp.get("slowed", 0)) > 0, "the snapshot measures the slowed workplaces (%s)" % str(imp))
	# the wizard walks up to the healer and talks (real click)
	_world.set_john_pos(Vector2i(int(healer["tx"]) + 1, int(healer["ty"])))
	_world._arrived()
	await _frames(4)
	_world._camera.zoom = Vector2(0.9, 0.9)
	_world.camera_focus = (Vector2(float(healer["tx"]), float(healer["ty"])) + Vector2(0.5, 0.5)) * float(_world.TPX)
	await _frames(8)
	await _click_at(_screen_of(healer))
	_check(_ui.dialog.visible and str(_ui.dialog_text.text).contains("marks"), "clicking the healer opens a dialogue that counts the marks")
	await _shot("02_healer_dialogue")
	var accept: Button = _ui.choices_box.get_node_or_null("Choice_accept_treat")
	_check(accept != null, "the dialogue offers to treat the region")
	if accept != null:
		await _click_at(accept.get_global_rect().get_center())
	await _key(KEY_ESCAPE)
	# treat twice with the T key; the sim advances between presses
	var before := int(_world._snapshot["regions"]["cubes"].values()[0])
	var start_cubes := 0
	for v in _world._snapshot["regions"]["cubes"].values():
		start_cubes += int(v)
	await _key(KEY_T)
	_sim_advance(4)
	await _frames(4)
	var mid: Dictionary = _world._snapshot.get("regions", {})
	_check(bool(mid.get("treating", false)), "T starts a treatment: the channel is open")
	_check(_ui.objective_text().contains("Treating"), "the status line shows the treatment countdown: '%s'" % _ui.objective_text())
	await _shot("03_treating")
	_sim_advance(6)
	await _frames(4)
	var total := 0
	for v in _world._snapshot["regions"]["cubes"].values():
		total += int(v)
	_check(total == start_cubes - 1, "the first treatment removed one cube (%d -> %d)" % [start_cubes, total])
	_sim_advance(21)
	await _key(KEY_T)
	_sim_advance(11)
	await _frames(8)
	var left := 0
	var here := str(_world._snapshot["regions"].get("player_region", ""))
	left = int(_world._snapshot["regions"]["cubes"].get(here, 0))
	_check(left == 0, "the wizard's own region is clean after the second treatment")
	_sim_advance(3)
	await _frames(8)
	var done := false
	for e in _entities("npc"):
		if str(e.get("role", "")) == "healer" and str(e.get("quest_status", "")) == "completed":
			done = true
	_check(done, "the healer's quest is completed in the simulation")
	var after := await _shot("04_region_clean")
	_check(_entities("outbreak_clue").size() == 1, "only the neighbouring region's clue is left (%d)" % _entities("outbreak_clue").size())
	if _fails.is_empty():
		print("HYBRID_OUTBREAK_OK")
		quit(0)
	else:
		print("HYBRID_OUTBREAK_FAIL %s" % ", ".join(_fails))
		quit(1)
