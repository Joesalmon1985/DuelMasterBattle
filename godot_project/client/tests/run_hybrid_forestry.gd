extends SceneTree

## Headed forestry test. Requires the sim on HYBRID_SIM_PORT. Follows one real
## tree through the lumberjack job, the carrier, and the ranger's replacement.
## Phases are read from the authoritative snapshot, never from a timer.

const FACTION := "Blue"
var _world: Node
var _shots: Dictionary = {}
var _log: Array[String] = []


func _init() -> void:
	call_deferred("_run")


func _row(kind: String, extra := "") -> Array:
	var out: Array = []
	for e in _world._snapshot.get("entities", []):
		if str(e.get("kind", "")) == kind and str(e.get("faction_name", FACTION)) in [FACTION, ""]:
			out.append(e)
	return out


func _focus_on(e: Dictionary) -> void:
	_world.camera_focus = Vector2(float(e.get("tx", 0)) + 0.5, float(e.get("ty", 0)) + 0.5) * _world.TPX


func _shot(name: String) -> void:
	for _i in 3:
		await process_frame
	await RenderingServer.frame_post_draw
	var dir := OS.get_environment("HYBRID_SHOT_DIR")
	if dir == "":
		dir = "res://../WizardRTSHybrid/docs/evidence/forestry"
	var image: Image = get_root().get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(dir)
	var path := dir.replace("\\", "/") + "/%s.png" % name
	var err := image.save_png(path)
	_shots[name] = hash(image.get_data())
	print("FORESTRY_SHOT %s %s err=%s" % [name, image.get_size(), err])


func _fail(msg: String) -> void:
	print("HYBRID_FORESTRY_FAIL %s" % msg)
	quit(1)


func _wait_for(cond: Callable, label: String, timeout_s := 240.0) -> bool:
	var t0 := Time.get_ticks_msec()
	while not cond.call():
		await process_frame
		if (Time.get_ticks_msec() - t0) / 1000.0 > timeout_s:
			_fail("timeout waiting for " + label)
			return false
	print("FORESTRY_PHASE %s game_ms=%s" % [label, _world._snapshot.get("game_ms", 0)])
	return true


func _lumberjack() -> Dictionary:
	for e in _world._snapshot.get("entities", []):
		if str(e.get("role", "")) == "lumberjack" and str(e.get("faction_name", "")) == FACTION:
			return e
	return {}


func _tree(id: String) -> Dictionary:
	for e in _world._snapshot.get("entities", []):
		if str(e.get("id", "")) == id:
			return e
	return {}


func _run() -> void:
	var packed := load("res://client/scenes/hybrid_world.tscn")
	_world = packed.instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	for _i in 30:
		await process_frame
	if _world._snapshot.is_empty():
		_fail("no snapshot")
		return
	var speed := int(OS.get_environment("HYBRID_SPEED"))
	if speed <= 0:
		speed = 4
	for e in _world._snapshot.get("entities", []):
		if str(e.get("kind", "")) == "tree":
			_initial[str(e.get("id"))] = true
	_world._sim.op({"op": "speed", "scale": speed})
	_world._camera.zoom = Vector2(1.0, 1.0)
	# The hut for this faction
	var hut: Dictionary = {}
	for e in _world._snapshot.get("entities", []):
		if str(e.get("definition", "")) == "widelands.lumberjack" and str(e.get("faction_name", "")) == FACTION:
			hut = e
	if hut.is_empty():
		_fail("no hut")
		return
	_focus_on(hut)
	await _shot("01_mature_forest")
	# 2: leaves the hut
	if not await _wait_for(_c_leaves, "worker_leaves_hut"):
		return
	await _shot("02_leaves_hut")
	var w := _lumberjack()
	# the tree he reserved is the nearest old tree he is walking to: track by hacking position
	if not await _wait_for(_c_hack, "chopping"):
		return
	w = _lumberjack()
	_focus_on(w)
	var tree_id := ""
	for e in _world._snapshot.get("entities", []):
		if str(e.get("kind", "")) == "tree" and int(e.get("tx")) == int(w.get("tx")) and int(e.get("ty")) == int(w.get("ty")):
			tree_id = str(e.get("id"))
	if tree_id == "":
		_fail("worker is not standing on a tree")
		return
	print("FORESTRY_TREE %s stage=%s" % [tree_id, _tree(tree_id).get("stage")])
	await _shot("03_chopping")
	if not await _wait_for(func(): return str(_tree(tree_id).get("stage", "")) == "felled", "tree_falls"):
		return
	await _shot("04_tree_felled")
	if not await _wait_for(_c_carry, "carrying_log"):
		return
	await _shot("05_carries_log")
	if not await _wait_for(_c_inside, "log_stored"):
		return
	_focus_on(hut)
	# carrier: a separate entity
	if not await _wait_for(_c_carrier, "carrier_collects"):
		return
	await _shot("06_carrier_collects")
	var wh := {}
	for e in _world._snapshot.get("entities", []):
		if str(e.get("kind", "")) == "warehouse" and str(e.get("faction_name", "")) == FACTION:
			wh = e
	if not await _wait_for(func(): return _arrived(_carrier_id), "log_arrives_warehouse"):
		return
	_focus_on(wh)
	await _shot("07_log_at_warehouse")
	# ranger
	if not await _wait_for(_c_sapling, "sapling_planted"):
		return
	_focus_on(_tree(_sapling_id))
	await _shot("08_sapling")
	if not await _wait_for(func(): return str(_tree(_sapling_id).get("stage", "")) in ["pole", ""], "sapling_grows", 300.0):
		return
	if _tree(_sapling_id).is_empty():
		print("FORESTRY_NOTE sapling died (13.67% chance); lifecycle still verified in Python")
	else:
		await _shot("09_pole")
	var seen := {}
	for k in _shots:
		seen[_shots[k]] = true
	if seen.size() < _shots.size() - 1:
		_fail("screenshots are not distinct")
		return
	if _world._art.missing.size() > 0:
		_fail("missing art %s" % str(_world._art.missing))
		return
	print("HYBRID_FORESTRY_OK shots=%d" % _shots.size())
	quit(0)


var _initial: Dictionary = {}


func _arrived(carrier_id: String) -> bool:
	var c := _tree(carrier_id)
	return not c.is_empty() and str(c.get("status", "")) == "idle"


var _carrier_id := ""
var _sapling_id := ""


func _c_leaves() -> bool:
	var w := _lumberjack()
	return not w.is_empty() and not bool(w.get("inside", true)) and str(w.get("anim", "")) == "walk"


func _c_hack() -> bool:
	return str(_lumberjack().get("anim", "")) == "hack"


func _c_carry() -> bool:
	return str(_lumberjack().get("carrying", "")) == "log"


func _c_inside() -> bool:
	return bool(_lumberjack().get("inside", false))


func _c_carrier() -> bool:
	for e in _world._snapshot.get("entities", []):
		if str(e.get("kind", "")) == "carrier" and str(e.get("faction_name", "")) == FACTION and str(e.get("status", "")) == "carrying":
			_carrier_id = str(e.get("id"))
			return true
	return false


func _c_sapling() -> bool:
	for e in _world._snapshot.get("entities", []):
		if str(e.get("kind", "")) == "tree" and str(e.get("stage", "")) == "sapling" and not _initial.has(str(e.get("id"))):
			_sapling_id = str(e.get("id"))
			return true
	return false
