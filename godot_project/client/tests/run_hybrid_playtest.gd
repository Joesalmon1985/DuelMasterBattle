extends SceneTree

## Headed regression for the first manual playtest (docs/PLAYTEST_FIXES.md): tree stage sprites, smooth motion, no walking on
## the spot, carried wares, the war factory with its door, and the burning-building sequence. Needs the sim on HYBRID_SIM_PORT
## with HYBRID_ALLOW_SPAWN=1 (the damage hook). Phases come from the snapshot, never from a timer.

var _world: Node
var _art
var _fails: Array[String] = []
var _dir := ""


func _init() -> void:
	call_deferred("_run")


func _ents() -> Array:
	return _world._snapshot.get("entities", [])


func _check(ok: bool, label: String) -> void:
	print("PLAYTEST %s %s" % ["ok  " if ok else "FAIL", label])
	if not ok:
		_fails.append(label)


func _focus(tile: Vector2, zoom: float) -> void:
	_world.camera_focus = (tile + Vector2(0.5, 0.5)) * _world.TPX
	_world._camera.zoom = Vector2(zoom, zoom)


func _shot(name: String) -> void:
	for _i in 4:
		await process_frame
	await RenderingServer.frame_post_draw
	var image: Image = get_root().get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(_dir)
	image.save_png(_dir.replace("\\", "/") + "/%s.png" % name)
	print("PLAYTEST_SHOT %s" % name)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _by_id(id: String) -> Dictionary:
	for e in _ents():
		if str(e.get("id", "")) == id:
			return e
	return {}


func _wait(cond: Callable, label: String, seconds := 240.0) -> bool:
	var t0 := Time.get_ticks_msec()
	while not cond.call():
		await process_frame
		if (Time.get_ticks_msec() - t0) / 1000.0 > seconds:
			_check(false, "timeout: " + label)
			return false
	return true


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = "res://../WizardRTSHybrid/docs/evidence/playtest"
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	await _frames(30)
	if _world._snapshot.is_empty():
		print("HYBRID_PLAYTEST_FAIL no snapshot")
		quit(1)
		return
	_art = _world._art
	_world._sim.op({"op": "speed", "scale": 1})

	# 1. Trees: every growth stage selects its own sprite, never the generic mature picture.
	var stage_files := {}
	for e in _ents():
		if str(e.get("kind", "")) == "tree" and str(e.get("definition", "")) == "widelands.beech":
			stage_files[str(e.get("stage", ""))] = str(_art._item_for(e).get("godot", ""))
	for stage in ["sapling", "pole", "mature", "old"]:
		_check(stage_files.has(stage) and stage_files[stage].ends_with("beech_%s.png" % stage), "tree stage %s uses beech_%s.png (%s)" % [stage, stage, stage_files.get(stage, "none present")])
	_check(str(_art._item_for({"kind": "tree", "definition": "widelands.beech", "stage": "felled"}).get("godot", "")).ends_with("fallentree.png"), "felled tree uses the fallen-tree sprite")

	# 2. War factory: base plus door, on its 3x2 footprint, ring and health bar aligned to it.
	var weap := {}
	for e in _ents():
		if str(e.get("definition", "")) == "openra.weap" and str(e.get("faction_name", "")) == "Red":
			weap = e
	_check(not weap.is_empty() and weap.has("ground_footprint") and (weap["ground_footprint"] as Array).size() == 6, "war factory has a 3x2 ground footprint")
	var item: Dictionary = _art.items.get("openra.weap", {})
	_check(item.has("overlay_prefix") and absf(float(item.get("scale", 0)) - 64.0 / 24.0) < 0.01, "war factory art: door overlay and one cell per tile")
	var door_tex = _art._tex("res://client/hybrid/art/openra/weap-top-0000.png")
	_check(door_tex != null, "door overlay frame loads")
	_focus(Vector2(float(weap.get("tx", 0)), float(weap.get("ty", 0)) - 0.5), 1.0)
	await _shot("weap_idle_door_closed")

	# 3. Motion: carriers and workers glide, they do not hop; idle ones stand still.
	var worst_step := 0.0
	var worst_id := ""
	var idle_animating := 0
	var last_pos := {}
	var moved := {}
	for _f in 240:
		await process_frame
		for id in _art._vis.keys():
			var p: Vector2 = _art._vis[id]["pos"]
			if last_pos.has(id):
				var d := p.distance_to(last_pos[id])
				if d < 4.0:
					if d > worst_step:
						worst_step = d
						worst_id = str(id)
					if d > 0.001:
						moved[id] = int(moved.get(id, 0)) + 1
			last_pos[id] = p
	var gliders := 0
	for id in moved:
		if int(moved[id]) >= 10:
			gliders += 1
	print("PLAYTEST motion: worst per-frame step %.3f tiles (%s %s), %d figures moved over 10+ frames" % [worst_step, worst_id, str(_by_id(worst_id)), gliders])
	_check(worst_step <= 0.6, "no figure moves more than 0.6 tile in one rendered frame (worst %.3f)" % worst_step)
	_check(gliders >= 3, "several figures glide over many frames (%d)" % gliders)
	for e in _ents():
		if str(e.get("class", "")) == "carrier" and str(e.get("status", "")) == "idle":
			var d: Dictionary = _art._motion(e)
			if not bool(d.get("_static", false)):
				idle_animating += 1
	_check(idle_animating == 0, "idle carriers show a still frame, not the walking loop (%d animating)" % idle_animating)

	# 4. Cargo: a carrier or worker holding a ware shows that ware's own picture.
	_check(await _wait(func():
		for e in _ents():
			if str(e.get("class", "")) == "carrier" and str(e.get("cargo", "")) != "":
				return true
		return false, "a loaded carrier", 400.0), "found a loaded carrier")
	var goods := {}
	for e in _ents():
		var g := str(e.get("cargo", e.get("carrying", "")))
		if g != "":
			goods[g] = _art.items.has("widelands.ware.%s" % g)
	_check(not goods.is_empty() and not goods.values().has(false), "every carried ware has its own sprite: %s" % str(goods))
	_check(_art.items["widelands.ware.plank"]["godot"] != _art.items["widelands.ware.log"]["godot"], "plank and log are different pictures")
	for e in _ents():
		if str(e.get("class", "")) == "carrier" and str(e.get("cargo", "")) != "":
			_focus(Vector2(float(e["tx"]), float(e["ty"])), 1.6)
			break
	await _shot("carrier_with_ware")

	# 5. Burning: a building at 0 HP stops at once, burns ~4 s of game time, then goes.
	var target := {}
	for e in _ents():
		if str(e.get("definition", "")) == "widelands.quarry" and str(e.get("faction_name", "")) == "Blue":
			target = e
	var tid := str(target.get("id", ""))
	_focus(Vector2(float(target.get("tx", 0)), float(target.get("ty", 0))), 1.4)
	var reply: Dictionary = _world._sim.op({"op": "damage", "building": tid, "amount": 100000000})
	_check(str(reply.get("status", "")) == "ok", "damage hook accepted")
	_world._apply_snapshot(reply.get("snapshot", {}))
	var row := _by_id(tid)
	_check(bool(row.get("destroyed", false)) and int(row.get("ruin_ms", 0)) <= 4000 and int(row.get("ruin_ms", 0)) > 0, "building marked destroyed with a short ruin timer (%s)" % str(row.get("ruin_ms", "?")))
	_check(_art.items.has("widelands.destroyed_building"), "burning sheet imported")
	await _shot("building_burning")
	var t0 := Time.get_ticks_msec()
	_check(await _wait(func(): return _by_id(tid).is_empty(), "ruin removed", 60.0), "ruin removed after the burn")
	print("PLAYTEST burn lasted %.1f real s" % ((Time.get_ticks_msec() - t0) / 1000.0))
	await _shot("building_gone")

	# 6. Wizard: holding a direction walks smoothly (no stop between tiles, no big hops), the camera follows without lag.
	_world.camera_focus = Vector2.INF
	var start: Vector2i = _world._john_pos
	var dir := Vector2i.ZERO
	for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
		var free := true
		for k in range(1, 14):
			if not _world.is_walkable(start + d * k):
				free = false
				break
		if free:
			dir = d
			break
	_check(dir != Vector2i.ZERO, "found a clear 13-tile run for the wizard")
	if dir != Vector2i.ZERO:
		_world._camera.zoom = Vector2(0.8, 0.8)
		_world.ui_hold_key_direction(dir)
		var prev: Vector2 = _world._john.position
		var stalls := 0
		var hop := 0.0
		var max_dt := 0.0
		var cam_lag := 0.0
		var t_last := Time.get_ticks_msec()
		var frames_walked := 0
		var tiles0: Vector2i = _world._john_pos
		for _f in 120:
			await process_frame
			var now := Time.get_ticks_msec()
			var dt := float(now - t_last) / 1000.0
			t_last = now
			var step: float = (_world._john.position - prev).length()
			prev = _world._john.position
			if _f > 4 and step < 0.01 * _world.TPX:
				stalls += 1
			if _f > 5:  # the camera was parked on a building a moment ago; judge it once it has settled on the wizard
				hop = maxf(hop, step)
				max_dt = maxf(max_dt, dt)
			if _f > 5:
				cam_lag = maxf(cam_lag, (_world._camera.position - (_world._john.position + Vector2(_world.TPX * 0.5, _world.TPX * 0.5))).length())
			frames_walked += 1
			if _world.is_walkable(_world._john_pos + dir) == false:
				break
		_world.ui_hold_key_direction(Vector2i.ZERO)
		while _world.ui_is_moving():
			await process_frame
		await _frames(3)
		var walked: Vector2i = _world._john_pos - tiles0
		var allowed: float = 1.25 * _world.TPX * max_dt / _world.STEP_SECONDS  # the longest frame of the run could move him this far
		print("PLAYTEST wizard: %d frames, %d tiles, %d stalled frames, worst step %.1f px (allowed %.1f for a %.0f ms frame), camera lag %.1f px" % [frames_walked, absi(walked.x) + absi(walked.y), stalls, hop, allowed, max_dt * 1000.0, cam_lag])
		_check(absi(walked.x) + absi(walked.y) >= 5, "the wizard walked several tiles")
		_check(stalls <= 1, "no stalled frames between tiles (%d)" % stalls)
		_check(hop <= allowed, "no step larger than the longest frame can explain (%.1f <= %.1f px)" % [hop, allowed])
		_check(cam_lag <= 1.0, "camera sits on the wizard (lag %.1f px)" % cam_lag)
		var pos_reply: Dictionary = _world._sim.op({"op": "snapshot"})
		var pl: Dictionary = pos_reply.get("snapshot", {}).get("player", {})
		_check(int(pl.get("tx", -1)) == _world._john_pos.x and int(pl.get("ty", -1)) == _world._john_pos.y, "authoritative player tile equals the walked tile")

	if _fails.is_empty():
		print("HYBRID_PLAYTEST_OK")
		quit(0)
	else:
		print("HYBRID_PLAYTEST_FAIL %s" % str(_fails))
		quit(1)
