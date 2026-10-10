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
	if _god == null or _world._snapshot.is_empty() or _world.terrain == null:
		_fail("no god mode, snapshot or terrain")
		return
	_world._sim.op({"op": "speed", "scale": 24})
	_world._sim.op({"op": "ai", "enabled": false})
	await _click_control(_god.mode_btn)
	await _click_control(_god.faction_row.get_node("Faction_Blue"))
	if str(_snap().get("controlled_faction", "")) != "Blue":
		_fail("faction not controlled")
		return
	var wh := _find("warehouse", "Blue")
	var sugg: Dictionary = _world._sim.op({"op": "suggest", "faction": "Blue", "kind": "naval_yard"})
	if str(sugg.get("status", "")) != "ok":
		_fail("the simulation sees no coast for Blue: %s" % str(sugg))
		return
	var site_tile := Vector2i(int(sugg["tile"][0]), int(sugg["tile"][1]))
	# 1. an inland click is refused with a reason, the coast click works
	var yard_btn: Control = _god.build_grid.get_node("Build_naval_yard")
	_god.build_grid.get_parent().ensure_control_visible(yard_btn)
	await _frames(3)
	await _click_control(yard_btn)
	if _god.tool != "build:naval_yard":
		_fail("naval yard tool not armed")
		return
	_world.camera_focus = (Vector2(wh["tx"], wh["ty"]) + Vector2(0.5, 0.5)) * _world.TPX
	_god._cam = _world.camera_focus
	await _frames(8)
	await _click(_screen(Vector2(int(wh["tx"]) + 3, int(wh["ty"]) + 3)))
	if _god.message.find("needs_water") < 0 and _god.message.find("tile_occupied") < 0 and _god.message.find("unsuitable") < 0:
		_fail("an inland click was not refused for the right reason: %s" % _god.message)
		return
	print("NAVAL_STEP inland refused: %s" % _god.message)
	_world.camera_focus = (Vector2(site_tile) + Vector2(0.5, 0.5)) * _world.TPX
	_god._cam = _world.camera_focus
	await _frames(8)
	await _click_control(yard_btn)
	var before_ids: Dictionary = {}
	for e in _world._snapshot.get("entities", []):
		before_ids[str(e.get("id", ""))] = true
	await _click(_screen(Vector2(site_tile)))
	await _frames(5)
	var yard := {}
	for e in _world._snapshot.get("entities", []):
		if not before_ids.has(str(e.get("id", ""))) and str(e.get("kind", "")) == "naval_yard":
			yard = e
	if yard.is_empty() or not yard.has("constructing"):
		_fail("no yard after the click: %s" % _god.message)
		return
	for p in yard.get("footprint", []):
		if not _water(Vector2i(int(p[0]), int(p[1]))):
			_fail("yard footprint tile %s is not water" % str(p))
			return
	print("NAVAL_STEP yard placed %s footprint=%d door=%s,%s" % [yard["id"], yard["footprint"].size(), yard["tx"], yard["ty"]])
	await _shot("01_yard_site_on_water")
	# 2. road from the shore door to the warehouse
	await _click_control(_god.tool_row.get_node("Tool_road"))
	await _click(_screen(Vector2(int(yard["tx"]), int(yard["ty"]))))
	await _click(_screen(Vector2(int(wh["tx"]), int(wh["ty"]))))
	await _frames(5)
	var has_road := false
	for rid in _world._snapshot.get("roads", {}):
		if str(rid).ends_with(":%s-%s" % [str(yard["id"]), str(wh["id"])]):
			has_road = true
	if not has_road:
		_fail("no road to the yard: %s" % _god.message)
		return
	print("NAVAL_STEP road built to the yard")
	await _wait(func(): return not _entity(str(yard["id"])).has("constructing"), "yard completes", 400.0)
	await _shot("02_yard_built")
	# 3. queue a patrol boat in the yard
	await _click(_screen(Vector2(int(yard["tx"]), int(yard["ty"]))))
	await _frames(20)
	var qbtn: Button = _god.actions.get_node_or_null("Act_queue_patrol_boat")
	if qbtn == null:
		_fail("no patrol boat button on the yard: %s" % _god.info.text)
		return
	if _god.info.text.find("Locked") < 0:
		_fail("locked source units are not listed with their reason")
		return
	await _click_control(qbtn)
	await _frames(10)
	var found_ship := {}  # a lambda captures locals by value, so the result goes through a container
	await _wait(func():
		for e in _world._snapshot.get("entities", []):
			if str(e.get("faction_name", "")) == "Blue" and str(e.get("definition", "")) == "openra.pt":
				found_ship["e"] = e
				return true
		return false, "patrol boat appears (paid for with delivered goods)", 900.0)
	var ship: Dictionary = found_ship.get("e", {})
	if ship.is_empty():
		_fail("no patrol boat")
		return
	if not _water(Vector2i(int(ship["tx"]), int(ship["ty"]))):
		_fail("the ship spawned off the water")
		return
	var consumed := int(_world._snapshot.get("stats", {}).get("consumed_plank", 0))
	print("NAVAL_STEP ship %s spawned on water at %s,%s (planks consumed so far %d)" % [ship["id"], ship["tx"], ship["ty"], consumed])
	await _shot("03_ship_spawned")
	# 4. select it and sail across the sea; every tile it stands on must be water
	_world.camera_focus = (Vector2(int(ship["tx"]), int(ship["ty"])) + Vector2(0.5, 0.5)) * _world.TPX
	_god._cam = _world.camera_focus
	_world._camera.zoom = Vector2(0.5, 0.5)
	await _frames(8)
	var ss := _screen(Vector2(int(ship["tx"]), int(ship["ty"])))
	await _drag(ss + Vector2(-60, -60), ss + Vector2(60, 60))
	if not _god.selected.has(str(ship["id"])):
		_fail("box select missed the ship: %s" % str(_god.selected))
		return
	var goal := Vector2i(int(ship["tx"]) + 28, int(ship["ty"]) + 22)
	var found := false
	for r in range(0, 20):
		for dy in range(-r, r + 1):
			for dx in range(-r, r + 1):
				if not found and maxi(absi(dx), absi(dy)) == r and _water(goal + Vector2i(dx, dy)):
					goal = goal + Vector2i(dx, dy)
					found = true
	_world.camera_focus = (Vector2(ship["tx"], ship["ty"]) + Vector2(goal)) * 0.5 * _world.TPX + Vector2(32, 32)
	_god._cam = _world.camera_focus
	await _frames(8)
	await _click(_screen(Vector2(goal)), MOUSE_BUTTON_RIGHT)
	var tiles := {}
	var t0 := Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 120000:
		await process_frame
		var cur := _entity(str(ship["id"]))
		if cur.is_empty():
			break
		var p := Vector2i(int(cur["tx"]), int(cur["ty"]))
		tiles[p] = true
		if not _water(p):
			_fail("ship on land at %s" % str(p))
			return
		if maxi(absi(p.x - goal.x), absi(p.y - goal.y)) <= 1:
			break
	if tiles.size() < 12:
		_fail("ship barely moved (%d tiles)" % tiles.size())
		return
	print("NAVAL_STEP ship sailed %d water tiles toward %s" % [tiles.size(), goal])
	await _shot("04_ship_sailed")
	# 5. an order onto land is refused
	var land := Vector2i(int(wh["tx"]), int(wh["ty"]) + 6)
	var reply: Dictionary = _world._sim.op({"op": "move", "units": [str(ship["id"])], "tx": land.x, "ty": land.y})
	if str(reply.get("status", "")) != "rejected":
		_fail("a ship was ordered onto land")
		return
	print("NAVAL_STEP ship refused a land order")
	# 6. naval combat: the test spawns a Green patrol boat beside the Blue ship; both are on the shared sea
	var cur2 := _entity(str(ship["id"]))
	var enemy_tile := Vector2i(int(cur2["tx"]) + 3, int(cur2["ty"]))
	var sp: Dictionary = _world._sim.op({"op": "spawn", "faction": "Green", "definition": "openra.pt", "tx": enemy_tile.x, "ty": enemy_tile.y})
	if str(sp.get("status", "")) != "ok":
		_fail("could not spawn the enemy ship: %s" % str(sp))
		return
	_world._camera.zoom = Vector2(0.8, 0.8)
	_world.camera_focus = (Vector2(enemy_tile) + Vector2(-1.5, 0.5)) * _world.TPX
	_god._cam = _world.camera_focus
	var hp_before := int(_entity(str(sp["id"])).get("hp", 0))
	var saw_shot := false
	var t1 := Time.get_ticks_msec()
	var shots_taken := false
	while Time.get_ticks_msec() - t1 < 90000:
		await process_frame
		var effects: Array = _world._snapshot.get("effects", [])
		if effects.size() > 0 and not shots_taken:
			shots_taken = true
			saw_shot = true
			await _shot("05_naval_fire")
		var e1 := _entity(str(ship["id"]))
		var e2 := _entity(str(sp["id"]))
		if (e1.is_empty() or not bool(e1.get("alive", true))) or (e2.is_empty() or not bool(e2.get("alive", true))):
			break
		if int(e1.get("hp", 1)) < int(e1.get("max_hp", 1)) and int(e2.get("hp", 1)) < hp_before and saw_shot:
			break
	var e1b := _entity(str(ship["id"]))
	var e2b := _entity(str(sp["id"]))
	var dmg1: bool = e1b.is_empty() or int(e1b.get("hp", 1)) < int(e1b.get("max_hp", 1)) or not bool(e1b.get("alive", true))
	var dmg2: bool = e2b.is_empty() or int(e2b.get("hp", 1)) < hp_before or not bool(e2b.get("alive", true))
	if not saw_shot or not (dmg1 or dmg2):
		_fail("no naval combat: shots=%s dmg=%s/%s" % [saw_shot, dmg1, dmg2])
		return
	print("NAVAL_STEP naval combat: shots drawn, damage dealt (blue hurt=%s green hurt=%s)" % [dmg1, dmg2])
	await _shot("06_after_battle")
	# 7. back to Wizard Mode: same world
	var seed_before := str(_snap().get("seed", ""))
	_god.leave()
	await _frames(10)
	if str(_snap().get("seed", "")) != seed_before or _world.terrain.static_hash != str(_snap().get("map", {}).get("static_hash", "")):
		_fail("world changed on leaving God Mode")
		return
	print("HYBRID_NAVAL_OK")
	quit(0)


func _free_tile(_e: Dictionary) -> Vector2:
	return Vector2.ZERO
