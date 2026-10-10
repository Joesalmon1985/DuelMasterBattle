extends SceneTree

## Headed six-faction war. Everything is autonomous: economies, recruitment from
## delivered goods, squads, marches, firefights, deaths, destroyed buildings. The
## camera follows the action; screenshots are taken when the snapshot shows each
## event, never on a timer. Requires the sim on HYBRID_SIM_PORT.

var _world: Node
var _shots: Dictionary = {}
var _seen: Dictionary = {}
var _colors_seen: Dictionary = {}
var _t0 := 0


func _init() -> void:
	call_deferred("_run")


func _fail(msg: String) -> void:
	print("HYBRID_WAR_FAIL %s" % msg)
	quit(1)


func _ents() -> Array:
	return _world._snapshot.get("entities", [])


func _focus(tile: Vector2, zoom: float) -> void:
	_world.camera_focus = (tile + Vector2(0.5, 0.5)) * _world.TPX
	_world._camera.zoom = Vector2(zoom, zoom)


func _shot(name: String) -> void:
	if _shots.has(name):
		return
	for _i in 4:
		await process_frame
	await RenderingServer.frame_post_draw
	var dir := OS.get_environment("HYBRID_SHOT_DIR")
	if dir == "":
		dir = "res://../WizardRTSHybrid/docs/evidence/war"
	DirAccess.make_dir_recursive_absolute(dir)
	var image: Image = get_root().get_viewport().get_texture().get_image()
	image.save_png(dir.replace("\\", "/") + "/%s.png" % name)
	_shots[name] = true
	print("WAR_SHOT %s game_ms=%s" % [name, str(_world._snapshot.get("game_ms", 0))])


func _stat(k: String) -> int:
	return int(_world._snapshot.get("stats", {}).get(k, 0))


func _units_of(faction: String) -> Array:
	var out: Array = []
	for e in _ents():
		if str(e.get("class", "")) == "unit" and str(e.get("faction_name", "")) == faction and bool(e.get("alive", true)):
			out.append(e)
	return out


func _run() -> void:
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	for _i in 30:
		await process_frame
	if _world._snapshot.is_empty():
		_fail("no snapshot")
		return
	var speed := int(OS.get_environment("HYBRID_SPEED"))
	if speed <= 0:
		speed = 30
	_world._sim.op({"op": "speed", "scale": speed})
	_world._input_locked = true
	var factions: Array = _world._snapshot.get("factions", [])
	if factions.size() != 6:
		_fail("expected six factions, got %d" % factions.size())
		return
	# overview of all six capitals
	var caps: Array = []
	for e in _ents():
		if str(e.get("kind", "")) == "warehouse":
			caps.append(Vector2(float(e["tx"]), float(e["ty"])))
	var sum := Vector2.ZERO
	for c in caps:
		sum += c
	_focus(sum / float(caps.size()), 0.055)
	await _shot("01_six_capitals_overview")
	_t0 = Time.get_ticks_msec()
	var limit_s := float(OS.get_environment("HYBRID_WAR_SECONDS"))
	if limit_s <= 0.0:
		limit_s = 300.0
	var need := {"marching": false, "firefight": false, "unit_death": false, "building_destroyed": false, "produced": false}
	var last_units: Dictionary = {}
	while (Time.get_ticks_msec() - _t0) / 1000.0 < limit_s:
		await process_frame
		var snap: Dictionary = _world._snapshot
		for f in factions:
			var fname := str(f.get("name", ""))
			for u in _units_of(fname):
				_colors_seen[fname] = true
		# first produced unit
		if not need["produced"] and _stat("recruited") > 0:
			for e in snap.get("recent_events", []):
				if str(e.get("kind", "")) == "unit_produced":
					var u: Dictionary = {}
					for x in _ents():
						if str(x.get("id", "")) == str(e.get("unit", "")):
							u = x
					if not u.is_empty():
						_focus(Vector2(float(u["tx"]), float(u["ty"])), 0.7)
						await _shot("02_unit_produced_from_delivered_goods")
						need["produced"] = true
		# a squad marching in a group
		if not need["marching"]:
			for f in factions:
				var group: Array = []
				for u in _units_of(str(f.get("name", ""))):
					if str(u.get("order", {}).get("kind", "")) in ["move", "attack_move", "attack"] and str(u.get("status", "")) == "moving":
						group.append(u)
				if group.size() >= 3:
					var c := Vector2.ZERO
					for u in group:
						c += Vector2(float(u["tx"]), float(u["ty"]))
					_focus(c / float(group.size()), 0.5)
					await _shot("03_squad_marching_%s" % str(f.get("name", "")))
					need["marching"] = true
					break
		var effects: Array = snap.get("effects", [])
		if not need["firefight"]:
			for e in effects:
				if str(e.get("t", "")) == "shot":
					_focus(Vector2(float(e["x2"]), float(e["y2"])), 0.6)
					await _shot("04_firefight")
					need["firefight"] = true
					break
		for e in effects:
			if str(e.get("t", "")) == "explosion":
				var big := float(e.get("ttl_ms", 0)) > 800.0
				if big and not need["building_destroyed"]:
					_focus(Vector2(float(e["x1"]), float(e["y1"])), 0.45)
					await _shot("06_building_destroyed")
					need["building_destroyed"] = true
				elif not big and not need["unit_death"]:
					_focus(Vector2(float(e["x1"]), float(e["y1"])), 0.7)
					await _shot("05_unit_dies")
					need["unit_death"] = true
		if need["marching"] and need["firefight"] and need["unit_death"] and need["building_destroyed"] and need["produced"]:
			break
	print("WAR_STATS %s" % str(_world._snapshot.get("stats", {})))
	print("WAR_NEED %s" % str(need))
	var missing: Array = []
	for k in need:
		if not need[k]:
			missing.append(k)
	if missing.size() > 0:
		_fail("never observed: %s" % str(missing))
		return
	if _colors_seen.size() < 3:
		_fail("too few faction colours seen in the world: %s" % str(_colors_seen.keys()))
		return
	if _world._art.missing.size() > 0:
		_fail("missing art %s" % str(_world._art.missing))
		return
	# a closing wide shot over the fighting
	_focus(sum / float(caps.size()), 0.055)
	await _shot("07_after_the_war_overview")
	print("HYBRID_WAR_OK shots=%d factions_with_units=%d" % [_shots.size(), _colors_seen.size()])
	quit(0)
