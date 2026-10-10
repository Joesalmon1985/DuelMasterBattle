extends SceneTree

## Launch the hybrid scene, walk the existing avatar, and screenshot start,
## middle, and end. Requires the Python sim on HYBRID_SIM_PORT.


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	DisplayServer.window_set_size(Vector2i(1280, 720))
	Engine.time_scale = 8.0
	var packed := load("res://client/scenes/hybrid_world.tscn")
	var world = packed.instantiate()
	root.add_child(world)
	for _i in 30:
		await process_frame
	if world._snapshot.is_empty():
		print("HYBRID_WALK_FAIL no snapshot")
		quit(1)
		return
	var start_pos: Vector2i = world._john_pos
	var start_hex: Array = world._snapshot.get("player", {}).get("hex", [])
	var world_id := str(world._snapshot.get("world_id", ""))
	if not await _shot(world, "walk_start"):
		print("HYBRID_WALK_FAIL shot walk_start")
		quit(1)
		return
	var east: Vector2i = world._john_pos + Vector2i(1, 0)
	print("HYBRID_WALK_DIAG lock=%s moving=%s scripted=%s east_walkable=%s key=%s" % [
		world._input_locked, world._moving, world._scripted_running, world.is_walkable(east), world._test_key_dir
	])
	var shot_middle := false
	var steps := 0
	var option_i := 0
	while world._hex_crossings < 20 and steps < 4000:
		# East across the map, then south. One row of hexes is shorter than 20.
		var prefer := Vector2i(1, 0) if world._last_hex.x < 18 else Vector2i(0, 1)
		var options: Array[Vector2i] = [prefer, Vector2i(0, 1), Vector2i(-1, 0), Vector2i(0, -1)]
		var travel: Vector2i = options[option_i]
		var before: Vector2i = world._john_pos
		world.ui_hold_key_direction(travel)
		for _frame in 4:
			await process_frame
		steps += 1
		if world._john_pos == before:
			option_i = (option_i + 1) % options.size()
		else:
			option_i = 0
		if steps == 1 or steps % 200 == 0:
			print("HYBRID_WALK_PROGRESS steps=%d pos=%s hex=%s crossings=%d" % [steps, world._john_pos, world._last_hex, world._hex_crossings])
		if not shot_middle and world._hex_crossings >= 10:
			if not await _shot(world, "walk_middle"):
				print("HYBRID_WALK_FAIL shot walk_middle")
				quit(1)
				return
			shot_middle = true
	world.ui_hold_key_direction(Vector2i.ZERO)
	for _frame in 20:
		await process_frame
	if not await _shot(world, "walk_end"):
		print("HYBRID_WALK_FAIL shot walk_end")
		quit(1)
		return
	var end_pos: Vector2i = world._john_pos
	var end_hex: Array = world._snapshot.get("player", {}).get("hex", [])
	var moved := end_pos != start_pos
	var same_world := str(world._snapshot.get("world_id", "")) == world_id
	var camera_distance := float(world._camera.position.distance_to(world._john.position))
	var camera_on_john := camera_distance < 80.0
	print("HYBRID_WALK start=%s end=%s hex %s -> %s crossings=%d moved=%s world=%s camera=%s" % [
		start_pos, end_pos, start_hex, end_hex, world._hex_crossings, moved, same_world, camera_on_john
	])
	if not moved or not same_world or not camera_on_john or world._hex_crossings < 20:
		print("HYBRID_WALK_FAIL")
		quit(1)
		return
	print("HYBRID_WALK_OK")
	quit(0)


func _shot(world: Node, name: String) -> bool:
	var dir := OS.get_environment("HYBRID_SHOT_DIR")
	if dir == "":
		return true
	await process_frame
	await process_frame
	await RenderingServer.frame_post_draw
	var viewport := get_root().get_viewport()
	var image: Image = RenderingServer.texture_2d_get(viewport.get_texture().get_rid())
	if image == null or image.get_width() == 0:
		image = viewport.get_texture().get_image()
	if image == null:
		print("HYBRID_SHOT %s null" % name)
		return false
	var colored := 0
	var terrain := 0
	var step := 8
	for y in range(0, image.get_height(), step):
		for x in range(0, image.get_width(), step):
			var pixel := image.get_pixel(x, y)
			if pixel.r + pixel.g + pixel.b > 0.15:
				colored += 1
			if pixel.g > pixel.r + 0.05 and pixel.g > 0.2:
				terrain += 1
	var mid := image.get_pixel(image.get_width() / 2, image.get_height() / 2)
	print("HYBRID_SHOT %s size=%s colored=%d terrain=%d center=%s john=%s" % [name, image.get_size(), colored, terrain, mid, world._john_pos])
	DirAccess.make_dir_recursive_absolute(dir)
	var path := dir.replace("\\", "/") + "/%s.png" % name
	var err := image.save_png(path)
	print("HYBRID_SHOT_SAVE %s %s" % [path, err])
	return colored >= 30 and terrain >= 100 and err == OK
