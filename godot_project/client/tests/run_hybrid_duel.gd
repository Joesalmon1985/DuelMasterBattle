extends SceneTree

## Walk the Overworld avatar to the route hazard, open the retained board,
## finish it, and check the world pose and the hazard.


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	DisplayServer.window_set_size(Vector2i(1280, 720))
	Engine.time_scale = 6.0
	var world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(world)
	for _i in 30:
		await process_frame
	if world._snapshot.is_empty():
		print("HYBRID_DUEL_FAIL no snapshot")
		quit(1)
		return
	var hazard := Vector2i(-9999, -9999)
	for entity in world._snapshot.get("entities", []):
		if typeof(entity) == TYPE_DICTIONARY and str(entity.get("kind", "")) == "hazard":
			hazard = Vector2i(int(entity.get("tx", 0)), int(entity.get("ty", 0)))
	if hazard.x < -1000:
		print("HYBRID_DUEL_FAIL no hazard")
		quit(1)
		return
	var ids_before: Array = []
	var steps := 0
	while absi(hazard.x - world._john_pos.x) + absi(hazard.y - world._john_pos.y) > 1 and steps < 900:
		var dx: int = hazard.x - world._john_pos.x
		var dy: int = hazard.y - world._john_pos.y
		var prefer: Vector2i = Vector2i(signi(dx), 0) if absi(dx) >= absi(dy) and dx != 0 else Vector2i(0, signi(dy))
		var before: Vector2i = world._john_pos
		world.ui_hold_key_direction(prefer)
		for _frame in 3:
			await process_frame
		if world._john_pos == before:
			var side: Vector2i = Vector2i(0, 1 if dy >= 0 else -1)
			world.ui_hold_key_direction(side)
			for _frame in 3:
				await process_frame
		steps += 1
	world.ui_hold_key_direction(Vector2i.ZERO)
	for _frame in 8:
		await process_frame
	var pose: Vector2i = world._john_pos
	if absi(hazard.x - pose.x) + absi(hazard.y - pose.y) > 1:
		print("HYBRID_DUEL_FAIL did not reach hazard pose=%s hazard=%s" % [pose, hazard])
		quit(1)
		return
	world._on_action()
	for _frame in 20:
		await process_frame
	if not world._duel_open or world._adapter._board == null:
		print("HYBRID_DUEL_FAIL board closed pose=%s" % pose)
		quit(1)
		return
	var during_reply: Dictionary = world._sim.op({"op": "snapshot"})
	var during: Dictionary = during_reply.get("snapshot", {})
	ids_before = during.get("entity_ids", [])
	var ms_during := int(during.get("game_ms", -1))
	var paused: bool = bool(during.get("paused", false))
	for _hold in 10:
		await process_frame
	var during_again: Dictionary = world._sim.op({"op": "snapshot"}).get("snapshot", {})
	var ms_held_open: bool = int(during_again.get("game_ms", -2)) == ms_during
	if not await _shot("duel_open"):
		print("HYBRID_DUEL_FAIL shot")
		quit(1)
		return
	var board = world._adapter._board
	board.ui_debug_finish_duel("victory")
	var deadline := Time.get_ticks_msec() + 3000
	while Time.get_ticks_msec() < deadline and not board.ui_is_result_visible():
		await process_frame
	if board.ui_is_result_visible() and board.ui_overlay_button_labels().has("Continue"):
		board.ui_pointer_press_overlay_button("Continue")
	else:
		world._adapter._on_board_finished("victory", {})
	for _frame in 30:
		await process_frame
	var snap: Dictionary = world._snapshot
	var same_pose: bool = world._john_pos == pose
	# the duel must not respawn or reseed the world: every building, unit and faction that existed still exists.
	# (trees, animals and workers are ecology and economy: they change with game time, which resumes after the duel)
	var same_ids := true
	# the periodic snapshots are delta-compressed and carry no id list: ask the simulation for the full one
	var ids_after: Array = world._sim.op({"op": "snapshot"}).get("snapshot", {}).get("entity_ids", [])
	for id in ids_before:
		if str(id).begins_with("building:") or str(id).begins_with("unit:") or str(id).begins_with("faction:"):
			if not ids_after.has(id):
				same_ids = false
	var cleared: bool = bool(snap.get("hazard_active", true)) == false
	print("HYBRID_DUEL pose=%s paused=%s ms=%s cleared=%s same_pose=%s same_ids=%s held_open=%s" % [
		pose, paused, ms_during, cleared, same_pose, same_ids, ms_held_open
	])
	if not paused or not cleared or not same_pose or not same_ids or not ms_held_open:
		print("HYBRID_DUEL_FAIL")
		quit(1)
		return
	print("HYBRID_DUEL_OK")
	quit(0)


func _shot(name: String) -> bool:
	var dir := OS.get_environment("HYBRID_SHOT_DIR")
	if dir == "":
		return true
	await process_frame
	await RenderingServer.frame_post_draw
	var image: Image = get_root().get_viewport().get_texture().get_image()
	if image == null:
		return false
	DirAccess.make_dir_recursive_absolute(dir)
	var path := dir.replace("\\", "/") + "/%s.png" % name
	return image.save_png(path) == OK
