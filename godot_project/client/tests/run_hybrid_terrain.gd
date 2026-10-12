extends SceneTree

## Terrain in the live hybrid: the Godot view must match the Python terrain, and it must be visible.
## Requires the sim on HYBRID_SIM_PORT. Shots go to HYBRID_SHOT_DIR. Every shot has state assertions.


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	DisplayServer.window_set_size(Vector2i(1280, 720))
	var packed := load("res://client/scenes/hybrid_world.tscn")
	var world = packed.instantiate()
	root.add_child(world)
	for _i in 40:
		await process_frame
	if world._snapshot.is_empty() or world.terrain == null:
		print("HYBRID_TERRAIN_FAIL no snapshot or no terrain")
		quit(1)
		return
	var t = world.terrain
	var sim: Object = world._sim
	var snap_hash := str(world._snapshot.get("map", {}).get("static_hash", ""))
	print("HYBRID_TERRAIN_INFO size=%dx%d hash=%s snapshot_hash=%s" % [t.w, t.h, t.static_hash, snap_hash])
	if t.static_hash != snap_hash or snap_hash == "":
		print("HYBRID_TERRAIN_FAIL terrain hash differs from the simulation")
		quit(1)
		return
	# 1. the view's terrain is the sim's terrain, tile by tile on a sample
	var rng := RandomNumberGenerator.new()
	rng.seed = 4242
	for _k in 60:
		var x := rng.randi_range(0, t.w - 1)
		var y := rng.randi_range(0, t.h - 1)
		var reply: Dictionary = sim.op({"op": "tile", "tx": x, "ty": y})
		if str(reply.get("terrain", "")) != t.terrain_name_at(x, y) or bool(reply.get("ground", false)) != t.ground(x, y):
			print("HYBRID_TERRAIN_FAIL tile %d,%d sim=%s view=%s" % [x, y, str(reply.get("terrain", "")), t.terrain_name_at(x, y)])
			quit(1)
			return
	print("HYBRID_TERRAIN_SAMPLE_OK 60 tiles match the simulation")
	# 2. find biome spots from the data
	var spots := {
		"water": _find(t, func(x, y): return _all_class(t, x, y, 5, "water"), Vector2i(int(t.starts[1][0]), int(t.starts[1][1]))),
		"mountain": _find(t, func(x, y): return _all_class(t, x, y, 4, "mineable"), Vector2i(int(t.starts[0][0]), int(t.starts[0][1]))),
		"farmland": _find(t, func(x, y): return _all_class(t, x, y, 5, "arable"), Vector2i(int(t.starts[2][0]), int(t.starts[2][1]) + 6)),
	}
	var shot_dir := OS.get_environment("HYBRID_SHOT_DIR")
	t.show_resources = true
	world._camera.zoom = Vector2(0.7, 0.7)
	for name in ["water", "mountain", "farmland"]:
		var spot: Vector2i = spots[name]
		world.camera_focus = (Vector2(spot) + Vector2(0.5, 0.5)) * world.TPX
		for _i in 10:
			await process_frame
		t._res_stamp = -10.0
		for _i in 3:
			await process_frame
		var mix := _view_mix(world, t)
		print("HYBRID_TERRAIN_VIEW %s spot=%s mix=%s deposits=%d" % [name, spot, str(mix), t.res_nodes.size()])
		var centre: Vector2 = world._camera.get_screen_center_position() / float(world.TPX)
		var centre_class: String = t.class_name_at(int(floor(centre.x)), int(floor(centre.y)))
		print("HYBRID_TERRAIN_CENTRE %s tile=%s class=%s" % [name, centre, centre_class])
		var want_class: String = {"water": "water", "mountain": "mineable", "farmland": "arable"}[name]
		var ok: bool = centre_class == want_class
		if name == "mountain":
			ok = ok and t.res_nodes.size() > 0
		var shot_ok: bool = await _shot(world, "terrain_%s" % name, name)
		if not ok:
			print("HYBRID_TERRAIN_FAIL %s view does not show the expected terrain" % name)
			quit(1)
			return
		if not shot_ok:
			quit(1)
			return
	# 3. the wizard cannot enter water: the simulation refuses the pose and the view refuses the step
	var wspot: Vector2i = spots["water"]
	var pr: Dictionary = sim.op({"op": "pose", "tx": wspot.x, "ty": wspot.y, "facing": "down"})
	if str(pr.get("status", "")) != "rejected" or world.is_walkable(wspot):
		print("HYBRID_TERRAIN_FAIL the wizard may enter water")
		quit(1)
		return
	print("HYBRID_TERRAIN_WATER_BLOCKS_WIZARD ok")
	# 4. far view still shows land and sea; the minimap in God Mode uses the same data
	world.camera_focus = Vector2(t.w, t.h) * 0.5 * world.TPX
	world._camera.zoom = Vector2(0.1, 0.1)
	for _i in 8:
		await process_frame
	if not await _shot(world, "terrain_overview", "overview"):
		quit(1)
		return
	# 5. mode switch keeps the same world and terrain
	var before := str(world._snapshot.get("seed", "")) + str(world._snapshot.get("map", {}).get("static_hash", ""))
	world.camera_focus = Vector2.INF
	world.god.enter()
	for _i in 12:
		await process_frame
	world._camera.zoom = Vector2(0.4, 0.4)
	var gpos: Vector2 = (Vector2(t.starts[0][0], t.starts[0][1]) + Vector2(0.5, 0.5)) * world.TPX
	world.camera_focus = gpos
	for _i in 12:
		await process_frame
	if not await _shot(world, "terrain_god_mode", "god"):
		quit(1)
		return
	world.god.leave()
	for _i in 6:
		await process_frame
	var after := str(world._snapshot.get("seed", "")) + str(world._snapshot.get("map", {}).get("static_hash", ""))
	if before != after:
		print("HYBRID_TERRAIN_FAIL world changed across a mode switch")
		quit(1)
		return
	print("HYBRID_TERRAIN_OK")
	quit(0)


func _all_class(t, x: int, y: int, r: int, cls: String) -> bool:
	for dy in range(-r, r + 1, 2):
		for dx in range(-r, r + 1, 2):
			if t.class_name_at(x + dx, y + dy) != cls:
				return false
	return true


func _find(t, pred: Callable, near: Vector2i) -> Vector2i:
	for r in range(0, 120):
		for dy in range(-r, r + 1):
			for dx in range(-r, r + 1):
				if maxi(absi(dx), absi(dy)) != r:
					continue
				var x := near.x + dx
				var y := near.y + dy
				if x < 6 or y < 6 or x >= t.w - 6 or y >= t.h - 6:
					continue
				if pred.call(x, y):
					return Vector2i(x, y)
	return near


func _view_mix(world: Node, t) -> Dictionary:
	var xf: Transform2D = world.get_viewport().get_canvas_transform().affine_inverse()
	var vp: Vector2 = world.get_viewport_rect().size
	var tl: Vector2 = xf * Vector2.ZERO
	var br: Vector2 = xf * vp
	var counts := {}
	var total := 0
	var step := 2
	for ty in range(maxi(int(tl.y / world.TPX), 0), mini(int(br.y / world.TPX), t.h - 1), step):
		for tx in range(maxi(int(tl.x / world.TPX), 0), mini(int(br.x / world.TPX), t.w - 1), step):
			var c: String = t.class_name_at(tx, ty)
			counts[c] = int(counts.get(c, 0)) + 1
			total += 1
	for k in counts:
		counts[k] = float(counts[k]) / maxf(total, 1)
	return counts


func _shot(world: Node, file: String, what: String) -> bool:
	var dir := OS.get_environment("HYBRID_SHOT_DIR")
	await process_frame
	await process_frame
	await RenderingServer.frame_post_draw
	var viewport := get_root().get_viewport()
	var image: Image = RenderingServer.texture_2d_get(viewport.get_texture().get_rid())
	if image == null or image.get_width() == 0:
		image = viewport.get_texture().get_image()
	if image == null:
		print("HYBRID_TERRAIN_FAIL shot %s null" % file)
		return false
	var blue := 0
	var grey := 0
	var green := 0
	var samples := 0
	for y in range(60, image.get_height(), 8):
		for x in range(0, image.get_width(), 8):
			var p := image.get_pixel(x, y)
			samples += 1
			if p.b > p.r + 0.12 and p.b > p.g:
				blue += 1
			elif absf(p.r - p.g) < 0.06 and absf(p.g - p.b) < 0.08 and p.r > 0.2:
				grey += 1
			elif p.g > p.r + 0.04 and p.g > p.b:
				green += 1
	print("HYBRID_TERRAIN_SHOT %s blue=%.2f grey=%.2f green=%.2f" % [file, float(blue) / samples, float(grey) / samples, float(green) / samples])
	var ok := true
	if what == "water":
		ok = float(blue) / samples > 0.12
	elif what == "mountain":
		ok = float(grey) / samples > 0.1
	elif what == "farmland":
		ok = float(green) / samples > 0.2
	elif what == "overview":
		ok = float(blue) / samples > 0.05 and float(green) / samples > 0.1
	if not ok:
		print("HYBRID_TERRAIN_FAIL shot %s colours do not match the terrain" % file)
		return false
	if dir != "":
		DirAccess.make_dir_recursive_absolute(dir)
		var err := image.save_png(dir.replace("\\", "/") + "/%s.png" % file)
		print("HYBRID_TERRAIN_SAVE %s err=%s" % [file, err])
		return err == OK
	return true
