extends SceneTree

## Single player, the AI fellow apprentice as the second wizard: walk up to Mira, challenge her, lock a Ward on the real board, then race her in real time
## (several of our guesses while she is still thinking), until the host reports a result; back in the world afterwards. Prints SINGLE_DUEL_OK or SINGLE_DUEL_FAIL.

var _scratch := ""


func _init() -> void:
	call_deferred("_run")


func _fail(msg: String) -> void:
	print("SINGLE_DUEL_FAIL %s" % msg)
	_finish(1)


func _finish(code: int) -> void:
	var lan: Node = root.get_node("LanSession")
	lan.stop_local_host()
	lan.reset()
	if _scratch != "":
		OS.move_to_trash(_scratch)
	if code == 0:
		print("SINGLE_DUEL_OK")
	quit(code)


func _shot(name: String) -> void:
	var dir := OS.get_environment("HYBRID_SHOT_DIR")
	if dir == "":
		return
	for _i in 4:
		await process_frame
	DirAccess.make_dir_recursive_absolute(dir)
	root.get_viewport().get_texture().get_image().save_png(dir.path_join(name + ".png"))


func _run() -> void:
	DisplayServer.window_set_size(Vector2i(720, 1280))
	_scratch = ProjectSettings.globalize_path("user://").path_join("single_duel_%d" % (Time.get_ticks_msec() % 100000))
	DirAccess.make_dir_recursive_absolute(_scratch)
	OS.set_environment("DMB_RUNS_DIR", _scratch)
	var lan: Node = root.get_node("LanSession")
	lan.reset()
	var menu = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(menu)
	await process_frame
	menu.ui_press_single()
	menu.queue_free()
	var world: Node = null
	var t := 0.0
	while t < 180.0 and world == null:
		await create_timer(0.1).timeout
		t += 0.1
		if current_scene != null and current_scene.scene_file_path == "res://client/scenes/hybrid_world.tscn":
			world = current_scene
	if world == null:
		return _fail("the world never opened")
	for _i in 60:
		await process_frame
	if world.story_ui != null and world.story_ui.opening_card.visible:
		world.story_ui.finish_opening()
	for _i in 10:
		await process_frame
	# find Mira and walk up to her
	var ai_id := ""
	var deadline := Time.get_ticks_msec() + 90000
	while Time.get_ticks_msec() < deadline:
		var rows: Dictionary = world.ui_mp_players()
		for pid in rows:
			if bool(rows[pid].get("ai", false)):
				ai_id = str(pid)
		if ai_id != "":
			var row: Dictionary = rows[ai_id]
			var dx: int = int(row["tx"]) - int(world._john_pos.x)
			var dy: int = int(row["ty"]) - int(world._john_pos.y)
			if absi(dx) + absi(dy) <= 2:
				break
			var dir := Vector2i(signi(dx), 0) if absi(dx) >= absi(dy) else Vector2i(0, signi(dy))
			world.ui_hold_key_direction(dir)
			for _f in 10:
				await process_frame
			world.ui_hold_key_direction(Vector2i.ZERO)
			for _f in 6:
				await process_frame
		else:
			await process_frame
	world.ui_hold_key_direction(Vector2i.ZERO)
	if ai_id == "":
		return _fail("no AI wizard in the world")
	await _shot("sp_duel_mira_adjacent")
	var ch: Dictionary = world.mp_challenge()
	if str(ch.get("status", "")) != "ok":
		return _fail("challenge refused: %s" % str(ch))
	deadline = Time.get_ticks_msec() + 30000
	while world.ui_mp_board() == null and Time.get_ticks_msec() < deadline:
		await process_frame
	var board = world.ui_mp_board()
	if board == null:
		return _fail("Mira did not accept: the board never opened")
	await _shot("sp_duel_setup")
	for i in 3:
		board.ui_action_select_locus(i)
		board.ui_action_pick_spell([0, 1, 6][i])
	board.ui_action_lock_ward()
	for _f in 10:
		await process_frame
	var sim = world.ui_mp_sim()
	if sim == null or not sim.ward_locked():
		return _fail("ward not locked")
	# the race: as soon as both Wards are set, cast twice at once, while Mira (who thinks for seconds) has cast at most once
	deadline = Time.get_ticks_msec() + 120000
	var pool := [0, 1, 6]
	var best_lead := -99
	var waiting_msg := false
	var n := 0
	while Time.get_ticks_msec() < deadline and sim.result == null:
		if sim.phase == sim.Phase.DUELING:
			if sim.player_cast_block_reason().to_lower().find("waiting") >= 0:
				waiting_msg = true
			if sim.can_player_cast():
				board.ui_action_cast()
				best_lead = maxi(best_lead, sim.player_history.size() - sim.enemy_history.size())
			elif sim.is_player_window_open():
				for i in 3:
					board.ui_action_select_locus(i)
					board.ui_action_pick_spell(pool[(n + i * 2) % 3])
				n += 1
		await process_frame
	if sim.result == null:
		return _fail("the duel did not finish")
	if waiting_msg:
		return _fail("the board told us to wait for the rival")
	if best_lead < 2:
		return _fail("we never had a lead of two guesses over Mira (best lead %d): the duel is not real-time" % best_lead)
	print("SINGLE_DUEL_RESULT %s" % JSON.stringify({"outcome": sim.result.outcome, "reason": sim.result.reason, "ours": sim.player_history.size(), "hers": sim.enemy_history.size(), "best_lead": best_lead}))
	deadline = Time.get_ticks_msec() + 6000
	while Time.get_ticks_msec() < deadline and not board.ui_is_result_visible():
		await process_frame
	await _shot("sp_duel_result")
	if not board.ui_pointer_press_overlay_button("Continue"):
		return _fail("no Continue button")
	for _f in 15:
		await process_frame
	if world.ui_mp_board() != null or world._duel_open or world._input_locked:
		return _fail("the world is still locked after the duel")
	var before: Vector2i = world._john_pos
	for dir in [Vector2i(0, 1), Vector2i(1, 0), Vector2i(0, -1), Vector2i(-1, 0)]:
		world.ui_hold_key_direction(dir)
		for _f in 14:
			await process_frame
		world.ui_hold_key_direction(Vector2i.ZERO)
		for _f in 8:
			await process_frame
		if world._john_pos != before:
			break
	if world._john_pos == before:
		return _fail("cannot move after the duel")
	world.mp_leave()
	_finish(0)
