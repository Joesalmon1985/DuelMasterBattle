extends SceneTree

## Headed LAN acceptance: this Godot client joins a Python-hosted world where a scripted second human (scripts/lan_bot.py)
## plays the host's wizard. Checks: both wizards on screen, movement replicated both ways, a declined challenge, a full
## human-versus-human Ward duel through the real board UI (host-scored), return to the world, continued movement.
## Env: HYBRID_LAN_HOST (127.0.0.1), HYBRID_LAN_PORT, HYBRID_LAN_CODE. Prints HYBRID_LAN_OK.

var _fail := ""
var _lan: Node  # the LanSession autoload (a SceneTree script cannot name autoloads directly)


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	DisplayServer.window_set_size(Vector2i(720, 1280))
	Engine.time_scale = 1.0
	var host := OS.get_environment("HYBRID_LAN_HOST")
	if host == "":
		host = "127.0.0.1"
	var port := int(OS.get_environment("HYBRID_LAN_PORT"))
	var code := OS.get_environment("HYBRID_LAN_CODE")
	_lan = root.get_node("/root/LanSession")
	_lan.reset()
	_lan.mode = "join"
	_lan.player_name = "GodotPlayer"
	var hello: Dictionary = _lan.connect_and_hello(host, port, code, "GodotPlayer")
	if str(hello.get("status", "")) != "ok":
		return _die("hello failed: %s" % str(hello))
	print("HYBRID_LAN_HELLO %s" % JSON.stringify({"player_id": _lan.player_id, "state": hello.get("state")}))
	# wait for the host's wizard (the bot) to start the world
	var deadline := Time.get_ticks_msec() + 60000
	while Time.get_ticks_msec() < deadline:
		var lob: Dictionary = _lan.sim.op({"op": "lobby"})
		if str(lob.get("session", {}).get("state", "")) == "playing":
			break
		await create_timer(0.3).timeout
	var world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(world)
	for _i in 40:
		await process_frame
	if world._snapshot.is_empty() or not world.mp:
		return _die("no snapshot or not in LAN mode")
	# 1. both wizards exist on this screen
	deadline = Time.get_ticks_msec() + 20000
	while world.ui_mp_players().is_empty() and Time.get_ticks_msec() < deadline:
		await process_frame
	var others: Dictionary = world.ui_mp_players()
	if others.size() != 1:
		return _die("expected one remote wizard, saw %d" % others.size())
	var other_id: String = others.keys()[0]
	var actor = world.actor("lan:" + other_id)
	if actor == null or not is_instance_valid(actor):
		return _die("remote avatar not drawn")
	print("HYBRID_LAN_REMOTE %s" % JSON.stringify({"id": other_id, "tile": [others[other_id]["tx"], others[other_id]["ty"]], "me": [world._john_pos.x, world._john_pos.y]}))
	await _shot(world, "lan_two_wizards")
	# the LAN status line must not sit on the campaign HUD card or the top bar, in portrait and in landscape
	var clear := _status_clear(world, "720x1280")
	DisplayServer.window_set_size(Vector2i(1280, 720))
	for _f in 6:
		await process_frame
	await _shot(world, "lan_two_wizards_landscape")
	clear = _status_clear(world, "1280x720") and clear
	DisplayServer.window_set_size(Vector2i(720, 1280))
	for _f in 6:
		await process_frame
	if not clear:
		return _die("LAN status label overlaps the HUD")
	# 2. this client moves; the host accepts the steps (the pose in the next state poll matches)
	var start: Vector2i = world._john_pos
	var moved := false
	for dir in [Vector2i(0, -1), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(1, 0)]:
		world.ui_hold_key_direction(dir)
		for _f in 14:
			await process_frame
		world.ui_hold_key_direction(Vector2i.ZERO)
		for _f in 10:
			await process_frame
		if world._john_pos != start:
			moved = true
			break
	if not moved:
		return _die("could not move")
	for _f in 12:
		await process_frame
	var server_pose: Dictionary = world._snapshot.get("player", {})
	if Vector2i(int(server_pose.get("tx", -1)), int(server_pose.get("ty", -1))) != world._john_pos:
		return _die("host pose %s differs from local %s" % [server_pose, world._john_pos])
	# 3. the bot walks up to us: its tile changes on our screen and its actor glides (remote movement replicated)
	deadline = Time.get_ticks_msec() + 60000
	var adjacent := false
	while Time.get_ticks_msec() < deadline:
		var rows: Dictionary = world.ui_mp_players()
		if rows.has(other_id):
			var t := Vector2i(int(rows[other_id]["tx"]), int(rows[other_id]["ty"]))
			if absi(t.x - world._john_pos.x) + absi(t.y - world._john_pos.y) <= 1:
				adjacent = true
				break
		await process_frame
	if not adjacent:
		return _die("bot never reached us")
	print("HYBRID_LAN_ADJACENT")
	for _f in 20:
		await process_frame
	# 4. the bot challenges first; we decline (invite panel appears, then goes away)
	deadline = Time.get_ticks_msec() + 40000
	while world.ui_mp_invite().is_empty() and Time.get_ticks_msec() < deadline:
		await process_frame
	if world.ui_mp_invite().is_empty():
		return _die("no invite arrived from the bot")
	await _shot(world, "lan_invite_panel")
	var decl: Dictionary = world.mp_respond(false)
	if str(decl.get("status", "")) != "ok" or bool(decl.get("accepted", true)):
		return _die("decline failed: %s" % str(decl))
	print("HYBRID_LAN_DECLINED")
	# with no invite pending and the other wizard beside us, the challenge button is offered
	deadline = Time.get_ticks_msec() + 5000
	while not world._mp_challenge_btn.visible and Time.get_ticks_msec() < deadline:
		await process_frame
	await _shot(world, "lan_adjacent_challenge_button")
	if not world._mp_challenge_btn.visible:
		return _die("challenge button not visible when adjacent")
	# 5. we challenge; the bot accepts; the board opens in setup
	var ch: Dictionary = world.mp_challenge()
	if str(ch.get("status", "")) != "ok":
		return _die("challenge failed: %s" % str(ch))
	deadline = Time.get_ticks_msec() + 30000
	while world.ui_mp_board() == null and Time.get_ticks_msec() < deadline:
		await process_frame
	var board = world.ui_mp_board()
	if board == null:
		return _die("board did not open")
	for _f in 10:
		await process_frame
	await _shot(world, "lan_duel_setup")
	# ward setup through the board UI
	for i in 3:
		board.ui_action_select_locus(i)
		board.ui_action_pick_spell([0, 1, 3][i])
	board.ui_action_lock_ward()
	for _f in 10:
		await process_frame
	var sim = world.ui_mp_sim()
	if sim == null or not sim.ward_locked():
		return _die("ward not locked: %s" % (sim.last_error() if sim != null else "no sim"))
	print("HYBRID_LAN_WARD_LOCKED")
	# 6. duel: cast through the board until the host reports a result; the rival's ward stays hidden until then
	deadline = Time.get_ticks_msec() + 120000
	var casts := 0
	var pool := [0, 1, 3]
	var revealed_early := false
	var shot_mid := false
	while Time.get_ticks_msec() < deadline:
		if sim.result != null:
			break
		if sim.phase == sim.Phase.DUELING:
			var ew: Array = sim.get_enemy_ward()
			for v in ew:
				if v != null:
					revealed_early = true
			if sim.can_player_cast():
				board.ui_action_cast()
				casts += 1
			elif sim.is_player_window_open():
				for i in 3:
					board.ui_action_select_locus(i)
					board.ui_action_pick_spell(pool[(casts + i) % 3])
			if casts == 1 and not shot_mid:
				shot_mid = true
				for _f in 6:
					await process_frame
				await _shot(world, "lan_duel_feedback")
		await process_frame
	if sim.result == null:
		return _die("duel did not finish (casts=%d)" % casts)
	if revealed_early:
		return _die("rival ward disclosed before the end")
	var outcome: String = sim.result.outcome
	var rival_ward: Array = sim.get_enemy_ward()
	print("HYBRID_LAN_RESULT %s" % JSON.stringify({"outcome": outcome, "reason": sim.result.reason, "casts": casts, "rival_ward": rival_ward}))
	if rival_ward.size() != 3 or rival_ward.has(null):
		return _die("rival ward not disclosed after the end: %s" % str(rival_ward))
	deadline = Time.get_ticks_msec() + 5000
	while Time.get_ticks_msec() < deadline and not board.ui_is_result_visible():
		await process_frame
	await _shot(world, "lan_duel_result")
	if not board.ui_pointer_press_overlay_button("Continue"):
		return _die("no Continue button")
	for _f in 10:
		await process_frame
	# 7. back in the shared world: unlocked, can move, the other wizard is still there
	if world.ui_mp_board() != null or world._duel_open or world._input_locked:
		return _die("world still locked after the duel")
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
		return _die("cannot move after the duel")
	if not world.ui_mp_players().has(other_id):
		return _die("other wizard vanished after the duel")
	for _f in 10:
		await process_frame
	await _shot(world, "lan_after_duel")
	var stats: Dictionary = world.ui_mp_stats()
	print("HYBRID_LAN_STATS %s" % JSON.stringify(stats))
	print("HYBRID_LAN_OK")
	quit(0)


func _status_clear(world: Node, label: String) -> bool:
	var status: Rect2 = world._mp_status.get_global_rect()
	var card: Rect2 = world.hud.panel.get_global_rect()
	var bar: Rect2 = world._hud.get_global_rect()
	var view: Rect2 = world.get_viewport().get_visible_rect()
	var ok := not status.intersects(card) and not status.intersects(bar) and view.encloses(status) and status.size.x > 100.0
	print("HYBRID_LAN_STATUS_LAYOUT %s %s status=%s card=%s bar=%s view=%s" % [label, "ok" if ok else "OVERLAP", status, card, bar, view])
	return ok


func _die(msg: String) -> void:
	print("HYBRID_LAN_FAIL %s" % msg)
	quit(1)


func _shot(world: Node, name: String) -> bool:
	var dir := OS.get_environment("HYBRID_SHOT_DIR")
	if dir == "":
		return true
	world.queue_redraw()
	await process_frame
	await process_frame
	var img := root.get_viewport().get_texture().get_image()
	if img == null:
		return false
	DirAccess.make_dir_recursive_absolute(dir)
	var ok := img.save_png(dir.path_join(name + ".png")) == OK
	print("HYBRID_LAN_SHOT %s %s" % [name, "ok" if ok else "fail"])
	return ok
