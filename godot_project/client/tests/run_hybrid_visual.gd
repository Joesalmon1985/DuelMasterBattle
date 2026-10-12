extends SceneTree

## Headed mashup shots of the live hybrid. Requires the sim on HYBRID_SIM_PORT.


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var packed := load("res://client/scenes/hybrid_world.tscn")
	var world = packed.instantiate()
	root.add_child(world)
	for _i in 40:
		await process_frame
	if world._snapshot.is_empty():
		print("HYBRID_VISUAL_FAIL no snapshot")
		quit(1)
		return
	if world._art.missing.size() > 0:
		print("HYBRID_VISUAL_MISSING %s" % str(world._art.missing))
		print("HYBRID_VISUAL_FAIL missing textures")
		quit(1)
		return
	var seen: Dictionary = {}
	for entity in world._snapshot.get("entities", []):
		var definition := str(entity.get("definition", ""))
		if definition != "":
			seen[definition] = true
	print("HYBRID_VISUAL_ENTITIES %s" % str(seen.keys()))
	world._camera.zoom = Vector2(0.48, 0.48)
	for _i in 8:
		await process_frame
	if not await _shot(world, "mashup_1280x720", Vector2i(1280, 720)):
		quit(1)
		return
	world._camera.zoom = Vector2(0.32, 0.32)
	if not await _shot(world, "mashup_wide_1280x720", Vector2i(1280, 720)):
		quit(1)
		return
	world._camera_nudge = Vector2(-640, -80)
	world._camera.zoom = Vector2(0.85, 0.85)
	var usable := DisplayServer.screen_get_usable_rect().size
	if usable.x < 1920 or usable.y < 1080:
		# a window cannot be larger than the usable screen (panels take space): this shot is for a bigger display
		print("HYBRID_VISUAL_SKIP 1920x1080 needs a usable screen of at least 1920x1080 (this one is %s)" % str(usable))
	elif not await _shot(world, "mashup_1920x1080", Vector2i(1920, 1080)):
		quit(1)
		return
	print("HYBRID_VISUAL_OK")
	quit(0)


func _settlement_anchor(world: Node) -> Vector2:
	var sum := Vector2.ZERO
	var count := 0
	for entity in world._snapshot.get("entities", []):
		if str(entity.get("faction_name", "")) != "Red":
			continue
		var kind := str(entity.get("kind", ""))
		if kind in ["tree", "rock", "hazard"]:
			continue
		sum += Vector2(int(entity.get("tx", 0)), int(entity.get("ty", 0))) * world.TPX
		count += 1
	if count == 0:
		return world._camera.position
	return sum / float(count)


func _shot(world: Node, name: String, size: Vector2i) -> bool:
	DisplayServer.window_set_size(size)
	for _i in 6:
		await process_frame
	await RenderingServer.frame_post_draw
	var dir := OS.get_environment("HYBRID_SHOT_DIR")
	if dir == "":
		dir = "res://../WizardRTSHybrid/docs/evidence/gallery"
	var viewport := get_root().get_viewport()
	var image: Image = RenderingServer.texture_2d_get(viewport.get_texture().get_rid())
	if image == null or image.get_width() == 0:
		image = viewport.get_texture().get_image()
	if image == null or image.get_width() != size.x or image.get_height() != size.y:
		print("HYBRID_VISUAL_FAIL %s size=%s" % [name, image.get_size() if image != null else "null"])
		return false
	var path := dir.replace("\\", "/") + "/%s.png" % name
	DirAccess.make_dir_recursive_absolute(dir)
	var err := image.save_png(path)
	print("HYBRID_VISUAL_SAVE %s %s err=%s" % [name, image.get_size(), err])
	return err == OK
