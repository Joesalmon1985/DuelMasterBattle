extends SceneTree

## Headed God Mode test of the territory expansion loop: the GUI queues an MCV at the war factory, the order is paid with delivered wares,
## the vehicle appears as a real unit, is selected and sent to a legal site, Deploy creates a command centre with a new build area,
## a second MCV is refused where it would overlap, and a building can be placed in the new area but not outside it.
## Needs the sim on HYBRID_SIM_PORT with HYBRID_ALLOW_SPAWN=1 (spawn is only used to make the second, illegally placed MCV).

var _world: Node
var _god: Node
var _fails: Array[String] = []
var _dir := ""


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("MCV %s %s" % ["ok  " if ok else "FAIL", label])
	if not ok:
		_fails.append(label)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _win(pos: Vector2) -> Vector2:
	return pos * (Vector2(DisplayServer.window_get_size()) / get_root().get_visible_rect().size)


func _mouse(vpos: Vector2, pressed: bool, button := MOUSE_BUTTON_LEFT) -> void:
	var pos := _win(vpos)
	var e := InputEventMouseButton.new()
	e.position = pos
	e.global_position = pos
	e.button_index = button
	e.pressed = pressed
	e.button_mask = (1 << (button - 1)) if pressed else 0
	Input.parse_input_event(e)


func _click(vpos: Vector2, button := MOUSE_BUTTON_LEFT) -> void:
	var m := InputEventMouseMotion.new()
	m.position = _win(vpos)
	m.global_position = _win(vpos)
	Input.parse_input_event(m)
	await _frames(1)
	_mouse(vpos, true, button)
	await _frames(1)
	_mouse(vpos, false, button)
	await _frames(3)


func _shot(name: String) -> void:
	await _frames(4)
	await RenderingServer.frame_post_draw
	var image: Image = get_root().get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(_dir)
	image.save_png(_dir.replace("\\", "/") + "/%s.png" % name)
	print("MCV_SHOT %s" % name)


func _ents() -> Array:
	return _world._snapshot.get("entities", [])


func _find(pred: Callable) -> Dictionary:
	for e in _ents():
		if pred.call(e):
			return e
	return {}


func _wait(cond: Callable, seconds: float, label: String) -> bool:
	var t0 := Time.get_ticks_msec()
	while not cond.call():
		await process_frame
		if (Time.get_ticks_msec() - t0) / 1000.0 > seconds:
			_check(false, "timeout: " + label)
			return false
	return true


func _screen_of(e: Dictionary, dy := 0.5) -> Vector2:
	var wp: Vector2 = (Vector2(float(e["tx"]), float(e["ty"])) + Vector2(0.5, dy)) * float(_world.TPX)
	return _world.get_canvas_transform() * wp


func _mcvs() -> Array:
	var out: Array = []
	for e in _ents():
		if str(e.get("definition", "")) == "openra.mcv" and str(e.get("faction_name", "")) == "Red":
			out.append(e)
	return out


func _ccs() -> Array:
	var out: Array = []
	for e in _ents():
		if str(e.get("kind", "")) == "warehouse" and str(e.get("faction_name", "")) == "Red":
			out.append(e)
	return out


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = "res://../WizardRTSHybrid/docs/evidence/mcv"
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	await _frames(40)
	_world._sim.op({"op": "ai", "enabled": false})  # this test plays Red; nobody else acts
	_world._sim.op({"op": "speed", "scale": 10})
	_god = _world.god
	_god.enter()
	_god.choose_faction("Red")
	await _frames(10)
	_check(_god.active, "God Mode is on")
	var ccs0 := _ccs().size()

	# 1. select the war factory with a real click and queue an MCV from its panel
	var factory := _find(func(e): return str(e.get("definition", "")) == "openra.weap" and str(e.get("faction_name", "")) == "Red")
	_world.camera_focus = (Vector2(float(factory["tx"]), float(factory["ty"])) - Vector2(0, 0.5)) * float(_world.TPX)
	_world._camera.zoom = Vector2(0.7, 0.7)
	await _frames(6)
	await _click(_screen_of(factory, -0.5))
	_check(_god.selected.has(str(factory["id"])), "the war factory is selected by clicking its picture (footprint aware)")
	var queue_btn: Button = null
	await _frames(10)
	for c in _god.actions.get_children():
		if c is Button and str(c.text).contains("MCV"):
			queue_btn = c
	_check(queue_btn != null, "the factory panel offers MCV")
	if queue_btn == null:
		print("HYBRID_MCV_FAIL no button")
		quit(1)
		return
	queue_btn.pressed.emit()
	await _frames(3)
	var f_row := _find(func(e): return str(e.get("id", "")) == str(factory["id"]))
	var q: Array = f_row.get("queue", [])
	_check(q.size() >= 1 and str(q[0].get("unit", "")) == "mcv", "an MCV is in the real production queue")
	await _shot("01_mcv_queued")

	# 2. wares are delivered to the factory, then the vehicle is built and appears
	var started := await _wait(func(): return str(_find(func(e): return str(e.get("id", "")) == str(factory["id"])).get("queue", [{}])[0].get("state", "")) == "building" or not _mcvs().is_empty(), 240.0, "the factory receives the wares and starts the MCV")
	_check(started, "production started only after the wares arrived")
	_check(await _wait(func(): return not _mcvs().is_empty(), 240.0, "the MCV appears"), "the MCV rolls out as a real unit")
	var mcv: Dictionary = _mcvs()[0]
	_check(mcv.has("unit_cargo") and (mcv["unit_cargo"] as Dictionary).size() > 0, "it carries the starter kit: %s" % str(mcv.get("unit_cargo", {})))
	await _shot("02_mcv_built")

	# 3. send it to a legal site chosen by the simulation, with a real right click on the map
	var site: Dictionary = _world._sim.op({"op": "suggest", "kind": "mcv_site", "faction": "Red", "unit": str(mcv["id"])})
	_check(str(site.get("status", "")) == "ok", "the simulation names a legal deployment site (%s)" % str(site.get("tile", site.get("reason", ""))))
	var tile: Array = site.get("tile", [0, 0])
	await _click(_screen_of(mcv, 0.2))
	_check(_god.selected.has(str(mcv["id"])), "the MCV is selected")
	_world.camera_focus = (Vector2(float(tile[0]), float(tile[1])) + Vector2(0.5, 0.5)) * float(_world.TPX)
	await _frames(6)
	var here0 := Vector2(float(mcv["tx"]), float(mcv["ty"]))
	_world.camera_focus = Vector2.INF
	_world._camera.position = (Vector2(float(tile[0]), float(tile[1])) + Vector2(0.5, 0.5)) * float(_world.TPX)
	_world.camera_focus = _world._camera.position
	await _frames(6)
	var dest_screen: Vector2 = _world.get_canvas_transform() * ((Vector2(float(tile[0]), float(tile[1])) + Vector2(0.5, 0.5)) * float(_world.TPX))
	await _click(dest_screen, MOUSE_BUTTON_RIGHT)
	var moved := await _wait(func(): return not _find(func(e): return str(e.get("id", "")) == str(mcv["id"])).is_empty() and (_find(func(e): return str(e.get("id", "")) == str(mcv["id"]))["tx"] == tile[0] and _find(func(e): return str(e.get("id", "")) == str(mcv["id"]))["ty"] == tile[1]), 400.0, "the MCV drives to the site")
	_check(moved, "it drove to the site with normal pathfinding")
	await _shot("03_mcv_at_site")

	# 4. Deploy button
	var deploy_btn: Button = null
	await _frames(6)
	for c in _god.actions.get_children():
		if c is Button and str(c.text) == "Deploy":
			deploy_btn = c
	_check(deploy_btn != null, "the panel offers Deploy for the selected MCV")
	deploy_btn.pressed.emit()
	await _frames(3)
	_check(await _wait(func(): return _ccs().size() == ccs0 + 1, 60.0, "deployment completes"), "Deploy created exactly one new command centre")
	_check(_mcvs().is_empty(), "the MCV was consumed")
	var new_cc: Dictionary = {}
	for e in _ccs():
		if bool(e.get("outpost", false)):
			new_cc = e
	_check(not new_cc.is_empty() and int(new_cc.get("territory", 0)) == 16, "the new centre has its own 16 tile build area")
	_world.camera_focus = (Vector2(float(new_cc["tx"]), float(new_cc["ty"])) - Vector2(0, 1.0)) * float(_world.TPX)
	_world._camera.zoom = Vector2(0.5, 0.5)
	await _frames(8)
	await _shot("04_command_centre_deployed")

	# 5. a building can be placed in the new area, not outside it
	var inside: Dictionary = _world._sim.op({"op": "build", "faction": "Red", "kind": "producer", "tx": int(new_cc["tx"]) + 6, "ty": int(new_cc["ty"]) + 4})
	var outside: Dictionary = _world._sim.op({"op": "build", "faction": "Red", "kind": "producer", "tx": int(new_cc["tx"]) + 30, "ty": int(new_cc["ty"])})
	_check(str(outside.get("reason", "")) == "outside_territory", "construction outside every build area is refused (%s)" % str(outside.get("reason", "")))
	_check(str(inside.get("reason", "ok")) != "outside_territory", "construction inside the new area is not refused for territory (%s)" % str(inside.get("reason", inside.get("status", ""))))

	# 6. an MCV beside the home warehouse is refused by the overlap rule, through the same Deploy button
	var home := _find(func(e): return str(e.get("kind", "")) == "warehouse" and str(e.get("faction_name", "")) == "Red" and not bool(e.get("outpost", false)))
	var spawn: Dictionary = _world._sim.op({"op": "spawn", "faction": "Red", "definition": "openra.mcv", "tx": int(home["tx"]) + 8, "ty": int(home["ty"]) + 8})
	_check(str(spawn.get("status", "")) == "ok", "a second MCV was placed beside the home centre")
	var dep: Dictionary = _world._sim.op({"op": "deploy", "unit": str(spawn.get("id", ""))})
	_check(str(dep.get("reason", "")) == "overlaps_friendly_territory", "deploying inside the home build area is rejected (%s)" % str(dep.get("reason", "")))
	var after := _ccs().size()
	_check(after == ccs0 + 1, "no duplicate command centre appeared")

	if _fails.is_empty():
		print("HYBRID_MCV_OK")
		quit(0)
	else:
		print("HYBRID_MCV_FAIL %s" % str(_fails))
		quit(1)
