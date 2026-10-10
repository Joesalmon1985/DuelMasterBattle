extends SceneTree

## Headed food-chain test: wheat planted, grown and harvested by a walking farmer;
## an animal hunted by a hunter and carried home; then bread and rations in the
## stats. Phases are read from the authoritative snapshot. Needs the sim on HYBRID_SIM_PORT.

const FACTION := "Blue"
var _world: Node
var _shots := {}


func _init() -> void:
	call_deferred("_run")


func _fail(msg: String) -> void:
	print("HYBRID_FOOD_FAIL %s" % msg)
	quit(1)


func _ents() -> Array:
	return _world._snapshot.get("entities", [])


func _role(role: String) -> Dictionary:
	for e in _ents():
		if str(e.get("role", "")) == role and str(e.get("faction_name", "")) == FACTION:
			return e
	return {}


func _focus(e: Dictionary, zoom := 1.0) -> void:
	_world.camera_focus = (Vector2(float(e.get("tx", 0)), float(e.get("ty", 0))) + Vector2(0.5, 0.5)) * _world.TPX
	_world._camera.zoom = Vector2(zoom, zoom)


func _shot(name: String) -> void:
	for _i in 3:
		await process_frame
	await RenderingServer.frame_post_draw
	var dir := OS.get_environment("HYBRID_SHOT_DIR")
	if dir == "":
		dir = "res://../WizardRTSHybrid/docs/evidence/food"
	DirAccess.make_dir_recursive_absolute(dir)
	var image: Image = get_root().get_viewport().get_texture().get_image()
	image.save_png(dir.replace("\\", "/") + "/%s.png" % name)
	_shots[name] = hash(image.get_data())
	print("FOOD_SHOT %s game_ms=%s" % [name, str(_world._snapshot.get("game_ms", 0))])


func _wait(cond: Callable, label: String, timeout := 240.0) -> bool:
	var t0 := Time.get_ticks_msec()
	while not cond.call():
		await process_frame
		if (Time.get_ticks_msec() - t0) / 1000.0 > timeout:
			_fail("timeout waiting for " + label)
			return false
	print("FOOD_PHASE %s game_ms=%s" % [label, str(_world._snapshot.get("game_ms", 0))])
	return true


func _farmer_anim(a: String) -> bool:
	return str(_role("farmer").get("anim", "")) == a and not bool(_role("farmer").get("inside", true))


func _field_near_farmer(stage: String) -> Dictionary:
	var f := _role("farmer")
	if f.is_empty():
		return {}
	for e in _ents():
		if str(e.get("definition", "")) == "widelands.wheat" and str(e.get("stage", "")) == stage:
			if absi(int(e["tx"]) - int(f["tx"])) <= 3 and absi(int(e["ty"]) - int(f["ty"])) <= 3:
				return e
	return {}


func _any_stage(stage: String) -> Dictionary:
	for e in _ents():
		if str(e.get("definition", "")) == "widelands.wheat" and str(e.get("stage", "")) == stage:
			return e
	return {}


func _stat(k: String) -> int:
	return int(_world._snapshot.get("stats", {}).get(k, 0))


func _run() -> void:
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	for _i in 30:
		await process_frame
	if _world._snapshot.is_empty():
		_fail("no snapshot")
		return
	_world._sim.op({"op": "speed", "scale": int(OS.get_environment("HYBRID_SPEED")) if OS.get_environment("HYBRID_SPEED") != "" else 6})
	_world._input_locked = true
	var farm := {}
	for e in _ents():
		if str(e.get("definition", "")) == "widelands.farm" and str(e.get("faction_name", "")) == FACTION:
			farm = e
	_focus(farm, 0.9)
	await _shot("01_farm_and_empty_land")
	var seen := {}
	var field_id := ""
	var animals_peak := _count_class("animal")
	var limit := float(OS.get_environment("HYBRID_FOOD_SECONDS"))
	if limit <= 0.0:
		limit = 420.0
	var t0 := Time.get_ticks_msec()
	while (Time.get_ticks_msec() - t0) / 1000.0 < limit:
		await process_frame
		var farmer := _role("farmer")
		var hunter := _role("hunter")
		if not seen.has("plant") and str(farmer.get("anim", "")) == "plant" and not bool(farmer.get("inside", true)):
			seen["plant"] = true
			_focus(farmer, 1.3)
			await _shot("02_farmer_plants")
		if not seen.has("tiny") and not _any_stage("tiny").is_empty():
			seen["tiny"] = true
			field_id = str(_any_stage("tiny").get("id", ""))
			_focus(_any_stage("tiny"), 1.3)
			await _shot("03_tiny_wheat")
		if seen.has("tiny") and not seen.has("medium") and _stage_of(field_id) == "medium":
			seen["medium"] = true
			_focus(_any_stage("medium"), 1.3)
			await _shot("04_medium_wheat")
		if not seen.has("ripe") and not _any_stage("ripe").is_empty():
			seen["ripe"] = true
			_focus(_any_stage("ripe"), 1.3)
			await _shot("05_ripe_wheat")
		if not seen.has("harvest") and str(farmer.get("anim", "")) == "harvest" and not bool(farmer.get("inside", true)):
			seen["harvest"] = true
			_focus(farmer, 1.3)
			await _shot("06_farmer_harvests")
		if not seen.has("wheat_carry") and str(farmer.get("carrying", "")) == "wheat":
			seen["wheat_carry"] = true
			_focus(farmer, 1.3)
			await _shot("07_farmer_carries_wheat")
		if not seen.has("hunter_out") and str(hunter.get("anim", "")) == "walk" and not bool(hunter.get("inside", true)):
			seen["hunter_out"] = true
			_focus(hunter, 1.0)
			await _shot("08_hunter_walks_to_game")
		if not seen.has("meat_carry") and str(hunter.get("carrying", "")) == "meat":
			seen["meat_carry"] = true
			_focus(hunter, 1.3)
			await _shot("09_hunter_carries_meat")
		if not seen.has("harvested") and not _any_stage("harvested").is_empty():
			seen["harvested"] = true
		if seen.size() >= 9 and _stat("made_bread") > 0 and _stat("made_ration") > 0 and _stat("made_water") > 0:
			break
	print("FOOD_SEEN %s" % str(seen.keys()))
	print("FOOD_STATS %s" % str({"wheat": _stat("made_wheat"), "meat": _stat("made_meat"), "bread": _stat("made_bread"), "ration": _stat("made_ration"), "water": _stat("made_water"), "coal": _stat("made_coal"), "fields": _stat("fields_planted")}))
	for need in ["plant", "tiny", "medium", "ripe", "harvest", "wheat_carry", "hunter_out", "meat_carry", "harvested"]:
		if not seen.has(need):
			_fail("never observed: %s" % need)
			return
	if _stat("made_bread") <= 0 or _stat("made_ration") <= 0 or _stat("made_water") <= 0 or _stat("made_meat") <= 0:
		_fail("food stats missing")
		return
	var distinct := {}
	for k in _shots:
		distinct[_shots[k]] = true
	if distinct.size() < _shots.size() - 1:
		_fail("screenshots are not distinct")
		return
	if _world._art.missing.size() > 0:
		_fail("missing art %s" % str(_world._art.missing))
		return
	print("HYBRID_FOOD_OK shots=%d" % _shots.size())
	quit(0)


func _stage_of(id: String) -> String:
	for e in _ents():
		if str(e.get("id", "")) == id:
			return str(e.get("stage", ""))
	return ""


func _count_class(c: String) -> int:
	var n := 0
	for e in _ents():
		if str(e.get("class", "")) == c:
			n += 1
	return n
