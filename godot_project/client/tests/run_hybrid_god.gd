extends SceneTree

## Headed God Mode test driven by real GUI input events (mouse motion, button
## press and release). Requires the sim on HYBRID_SIM_PORT. The only direct sim
## call is the clock speed, so waiting for construction and recruitment does not
## take minutes.

var _world: Node
var _god: Node
var _shots := 0


func _init() -> void:
	call_deferred("_run")


func _fail(msg: String) -> void:
	print("HYBRID_GOD_FAIL %s" % msg)
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
		dir = "res://../WizardRTSHybrid/docs/evidence/god_mode"
	DirAccess.make_dir_recursive_absolute(dir)
	var image: Image = get_root().get_viewport().get_texture().get_image()
	image.save_png(dir.replace("\\", "/") + "/%s.png" % name)
	_shots += 1
	print("GOD_SHOT %s" % name)


func _wait(cond: Callable, label: String, timeout := 120.0) -> bool:
	var t0 := Time.get_ticks_msec()
	while not cond.call():
		await process_frame
		if (Time.get_ticks_msec() - t0) / 1000.0 > timeout:
			_fail("timeout: " + label)
			return false
	print("GOD_STEP %s" % label)
	return true


func _run() -> void:
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	await _frames(30)
	_god = _world.god
	if _god == null or _world._snapshot.is_empty():
		_fail("no god mode or snapshot")
		return
	_world._sim.op({"op": "speed", "scale": 8})
	var john_before: Vector2i = _world._john_pos
	var game_ms_before := int(_world._snapshot.get("game_ms", 0))

	# 1. the visible button
	if _god.active or not _god.mode_btn.visible or _god.mode_btn.text != "God Mode":
		_fail("button not shown in Wizard Mode")
		return
	await _click_control(_god.mode_btn)
	if not _god.active or not _god.panel.visible:
		_fail("God Mode did not open from the button")
		return
	await _shot("01_god_mode_opened")

	# 2. choose a faction through the GUI
	var fb: Control = _god.faction_row.get_node("Faction_Green")
	await _click_control(fb)
	if str(_snap().get("controlled_faction", "")) != "Green":
		_fail("faction not controlled")
		return
	print("GOD_STEP faction Green")
	await _frames(10)

	# 3. open the build menu and place a lumberjack hut on a free tile
	var wh := _find("warehouse", "Green")
	var spot := _free_tile(wh)
	await _click_control(_god.build_grid.get_node("Build_producer"))
	if _god.tool != "build:producer":
		_fail("build tool not armed")
		return
	var before_ids: Dictionary = {}
	for e in _world._snapshot.get("entities", []):
		before_ids[str(e.get("id", ""))] = true
	await _click(_screen(Vector2(spot)))
	await _frames(5)
	var site := {}
	for e in _world._snapshot.get("entities", []):
		if not before_ids.has(str(e.get("id", ""))) and str(e.get("kind", "")) == "producer":
			site = e
	if site.is_empty() or not site.has("constructing"):
		_fail("no construction site after the click")
		return
	print("GOD_STEP placed %s at %s" % [site["id"], spot])
	await _shot("02_construction_site")

	# 4. road: Road tool, click the site, click the warehouse
	var roads_before: int = _world._snapshot.get("roads", {}).size()
	await _click_control(_god.tool_row.get_node("Tool_road"))
	await _click(_screen(Vector2(int(site["tx"]), int(site["ty"]))))
	await _click(_screen(Vector2(int(wh["tx"]), int(wh["ty"]))))
	await _frames(5)
	if _world._snapshot.get("roads", {}).size() != roads_before + 1:
		_fail("road not built: %s" % _god.message)
		return
	print("GOD_STEP road built")
	await _shot("03_road_built")
	await _wait(func(): return not _entity(str(site["id"])).has("constructing"), "site completes", 180.0)

	# 5. inspect the warehouse stock
	await _click(_screen(Vector2(int(wh["tx"]), int(wh["ty"]))))
	await _frames(20)
	if _god.info.text.find("Stock") < 0 or (_god.info.text.find("plank") < 0 and _god.info.text.find("log") < 0):
		_fail("warehouse info missing stock: %s" % _god.info.text)
		return
	print("GOD_STEP warehouse stock shown")

	# 6. open a barracks and queue a unit
	var bar := _find("barracks", "Green")
	await _click(_screen(Vector2(int(bar["tx"]), int(bar["ty"]))))
	await _frames(20)
	var qbtn: Button = _god.actions.get_node_or_null("Act_queue_infantry")
	if qbtn == null:
		_fail("no queue button for the barracks")
		return
	var units_before := 0
	for e in _world._snapshot.get("entities", []):
		if str(e.get("class", "")) == "unit" and str(e.get("faction_name", "")) == "Green":
			units_before += 1
	await _click_control(qbtn)
	await _frames(20)
	await _shot("04_barracks_queue")
	await _frames(60)
	var dbg := _entity(str(bar["id"]))
	print("GOD_DBG barracks queue=%s stock=%s msg=%s" % [str(dbg.get("queue", [])), str(_world._snapshot.get("stocks", {}).get(str(bar["id"]), {})), _god.message])
	await _wait(func():
		var n := 0
		for e in _world._snapshot.get("entities", []):
			if str(e.get("class", "")) == "unit" and str(e.get("faction_name", "")) == "Green":
				n += 1
		return n > units_before, "unit recruited", 180.0)

	# 7. box-select the new unit
	var unit := {}
	for e in _world._snapshot.get("entities", []):
		if str(e.get("class", "")) == "unit" and str(e.get("faction_name", "")) == "Green" and str(e.get("class", "")) == "unit":
			unit = e
	var unit_id := str(unit["id"])
	# the newest unit has the highest id number
	for e in _world._snapshot.get("entities", []):
		if str(e.get("class", "")) == "unit" and str(e.get("faction_name", "")) == "Green":
			if int(str(e["id"]).split(":")[1]) > int(unit_id.split(":")[1]):
				unit = e
				unit_id = str(e["id"])
	_world.camera_focus = (Vector2(int(unit["tx"]), int(unit["ty"])) + Vector2(0.5, 0.5)) * _world.TPX
	_god._cam = _world.camera_focus
	await _frames(6)
	var us := _screen(Vector2(int(unit["tx"]), int(unit["ty"])))
	await _drag(us + Vector2(-90, -110), us + Vector2(90, 70))
	if not _god.selected.has(unit_id):
		_fail("box select missed the unit: %s" % str(_god.selected))
		return
	print("GOD_STEP box selected %s" % unit_id)
	await _shot("05_unit_selected")

	# 8. right-click move
	var start_tile := Vector2i(int(unit["tx"]), int(unit["ty"]))
	await _click(_screen(Vector2(start_tile + Vector2i(6, 2))), MOUSE_BUTTON_RIGHT)
	var moved_ok: bool = await _wait(func():
		var e := _entity(unit_id)
		return Vector2i(int(e["tx"]), int(e["ty"])) != start_tile, "unit obeys move", 60.0)
	if not moved_ok:
		return
	await _shot("06_unit_moving")

	# 9. attack: jump with the minimap to Blue, right-click an enemy building
	var target := _find("producer", "Blue")
	var mp: Vector2 = _god.minimap.get_global_rect().position + Vector2(float(target["tx"]) / _god.MAP_TILES.x * _god.MINI.x, float(target["ty"]) / _god.MAP_TILES.y * _god.MINI.y)
	await _click(mp)
	await _frames(8)
	var t_hp := int(target.get("hp", 1000))
	await _click(_screen(Vector2(int(target["tx"]), int(target["ty"]))), MOUSE_BUTTON_RIGHT)
	var order: Dictionary = _entity(unit_id).get("order", {})
	if str(order.get("kind", "")) != "attack":
		_fail("attack order not issued: %s" % str(order))
		return
	print("GOD_STEP attack ordered")
	await _wait(func(): return int(_entity(str(target["id"])).get("hp", 1000)) < t_hp, "enemy building damaged", 240.0)
	await _shot("07_attacking_enemy_building")

	# 10. back to Wizard Mode through the same button
	await _click_control(_god.mode_btn)
	await _frames(10)
	if _god.active or _god.mode_btn.text != "God Mode":
		_fail("did not return to Wizard Mode")
		return
	var snap := _snap()
	var pl: Dictionary = snap.get("player", {})
	if Vector2i(int(pl["tx"]), int(pl["ty"])) != john_before or _world._john_pos != john_before:
		_fail("wizard moved: %s vs %s" % [pl, john_before])
		return
	if str(snap.get("controlled_faction", "x")) != "" or int(snap.get("game_ms", 0)) <= game_ms_before:
		_fail("world state not continuous")
		return
	await _shot("08_back_in_wizard_mode")
	# G key goes through the same toggle
	var key := InputEventKey.new()
	key.keycode = KEY_G
	key.pressed = true
	Input.parse_input_event(key)
	await _frames(5)
	if not _god.active:
		_fail("G key did not open God Mode")
		return
	key = InputEventKey.new()
	key.keycode = KEY_G
	key.pressed = false
	Input.parse_input_event(key)
	await _frames(2)
	key = InputEventKey.new()
	key.keycode = KEY_G
	key.pressed = true
	Input.parse_input_event(key)
	await _frames(5)
	if _god.active:
		_fail("G key did not close God Mode")
		return
	if _world._art.missing.size() > 0:
		_fail("missing art %s" % str(_world._art.missing))
		return
	print("HYBRID_GOD_OK shots=%d" % _shots)
	quit(0)


func _free_tile(wh: Dictionary) -> Vector2i:
	var taken: Dictionary = {}
	for t in _world._snapshot.get("blocked", []):
		taken[Vector2i(int(t[0]), int(t[1]))] = true
	for road in _world._snapshot.get("roads", {}).values():
		for t in road:
			taken[Vector2i(int(t[0]), int(t[1]))] = true
	for e in _world._snapshot.get("entities", []):
		if str(e.get("kind", "")) == "tree":
			taken[Vector2i(int(e["tx"]), int(e["ty"]))] = true
	var base := Vector2i(int(wh["tx"]), int(wh["ty"]))
	for dy in range(3, 9):
		for dx in range(3, 12):
			var t := base + Vector2i(dx, dy)
			if not taken.has(t) and not taken.has(t + Vector2i(1, 0)) and not taken.has(t + Vector2i(0, 1)):
				return t
	return base + Vector2i(8, 8)
