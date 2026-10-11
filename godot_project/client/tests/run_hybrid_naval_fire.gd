extends SceneTree

## Headed naval test: build a naval yard on the coast through the God Mode GUI, road it, queue a patrol boat that is paid
## in delivered goods, watch it spawn on water and sail only on water, then fight. Requires the sim on HYBRID_SIM_PORT
## with HYBRID_ALLOW_SPAWN=1 (the enemy ship is spawned by the test; everything else is GUI input).

var _world: Node
var _god: Node
var _shots := 0


func _init() -> void:
	call_deferred("_run")


func _fail(msg: String) -> void:
	print("HYBRID_NAVAL_FAIL %s" % msg)
	quit(1)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _win(pos: Vector2) -> Vector2:
	# Positions in this test are viewport coordinates (stretch mode scales the
	# window); synthetic events are window coordinates.
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


func _move_to(vpos: Vector2) -> void:
	var pos := _win(vpos)
	var m := InputEventMouseMotion.new()
	m.position = pos
	m.global_position = pos
	Input.parse_input_event(m)


func _click(pos: Vector2, button := MOUSE_BUTTON_LEFT) -> void:
	_move_to(pos)
	await _frames(2)
	_mouse(pos, true, button)
	await _frames(2)
	_mouse(pos, false, button)
	await _frames(3)


func _click_control(c: Control) -> void:
	await _click(c.get_global_rect().get_center())


func _drag(a: Vector2, b: Vector2) -> void:
	_move_to(a)
	await _frames(2)
	_mouse(a, true)
	await _frames(2)
	_move_to((a + b) * 0.5)
	await _frames(2)
	_move_to(b)
	await _frames(2)
	_mouse(b, false)
	await _frames(3)


func _screen(tile: Vector2) -> Vector2:
	return _world.get_viewport().get_canvas_transform() * ((tile + Vector2(0.5, 0.5)) * _world.TPX)


func _snap() -> Dictionary:
	return _world._sim.op({"op": "snapshot"}).get("snapshot", {})


func _find(kind: String, faction: String, extra := "") -> Dictionary:
	for e in _world._snapshot.get("entities", []):
		if str(e.get("kind", "")) == kind and str(e.get("faction_name", "")) == faction:
			return e
	return {}


func _entity(id: String) -> Dictionary:
	for e in _world._snapshot.get("entities", []):
		if str(e.get("id", "")) == id:
			return e
	return {}


func _shot(name: String) -> void:
	await _frames(3)
	await RenderingServer.frame_post_draw
	var dir := OS.get_environment("HYBRID_SHOT_DIR")
	if dir == "":
		dir = "res://../WizardRTSHybrid/docs/evidence/naval"
	DirAccess.make_dir_recursive_absolute(dir)
	var image: Image = get_root().get_viewport().get_texture().get_image()
	image.save_png(dir.replace("\\", "/") + "/%s.png" % name)
	_shots += 1
	print("NAVAL_SHOT %s" % name)


func _wait(cond: Callable, label: String, timeout := 120.0) -> bool:
	var t0 := Time.get_ticks_msec()
	while not cond.call():
		await process_frame
		if (Time.get_ticks_msec() - t0) / 1000.0 > timeout:
			_fail("timeout: " + label)
			return false
	print("NAVAL_STEP %s" % label)
	return true


func _water(t: Vector2i) -> bool:
	return _world.terrain.class_name_at(t.x, t.y) == "water"


func _run() -> void:
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	await _frames(30)
	_god = _world.god
	_world._sim.op({"op": "ai", "enabled": false})
	await _click_control(_god.mode_btn)
	await _click_control(_god.faction_row.get_node("Faction_Blue"))
	var t = _world.terrain
	var spot := Vector2i(int(t.starts[1][0]) + 40, int(t.starts[1][1]) + 10)
	for r in range(0, 30):
		var done := false
		for dy in range(-r, r + 1):
			for dx in range(-r, r + 1):
				if not done and maxi(absi(dx), absi(dy)) == r and _water(spot + Vector2i(dx, dy)) and _water(spot + Vector2i(dx + 4, dy)):
					spot = spot + Vector2i(dx, dy)
					done = true
		if done:
			break
	var a: Dictionary = _world._sim.op({"op": "spawn", "faction": "Blue", "definition": "openra.pt", "tx": spot.x, "ty": spot.y})
	var b: Dictionary = _world._sim.op({"op": "spawn", "faction": "Green", "definition": "openra.pt", "tx": spot.x + 3, "ty": spot.y})
	_world._sim.op({"op": "speed", "scale": 3})
	var seen := 0
	for i in 120:
		await process_frame
		var eff: Array = _world._snapshot.get("effects", [])
		if eff.size() > 0:
			seen += 1
			if seen <= 3:
				print("NAVAL_STEP frame %d effects=%d first=%s" % [i, eff.size(), str(eff[0])])
	var ea := _entity(str(a["id"]))
	var eb := _entity(str(b["id"]))
	print("NAVAL_STEP frames_with_effects=%d hp a=%s b=%s" % [seen, str(ea.get("hp")), str(eb.get("hp"))])
	quit(0)
