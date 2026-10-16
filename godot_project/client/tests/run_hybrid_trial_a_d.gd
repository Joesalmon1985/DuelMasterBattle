extends SceneTree

## Headed acceptance for the Trial's first half (plan M5, scenarios E and F): this Godot client joins a Python-hosted Wizard World (a scripted
## second human, scripts/lan_bot.py, started the session and stays put), is put beside the gate (the host's dev-only `teleport`), sees the gate
## drawn on the map, goes in with no lesson taken, walks the Crystal Entrance with real validated steps (a wall refuses, a wrong tile snaps back),
## takes Sukumvit's box (the pocket strip shows it), reads the crystal, goes up through the exit into the Footprint Fork (a second zone built by
## the legacy tile builder), reads a sign, faces the Giant Fly on the REAL board, and sees the host's verdict (a win removes it; a loss wounds).
## Env: HYBRID_LAN_HOST, HYBRID_LAN_PORT, HYBRID_LAN_CODE, HYBRID_SHOT_DIR. Prints HYBRID_TRIAL_OK or HYBRID_TRIAL_FAIL <reasons>.

var _lan: Node
var _world: Node
var _tm: Node
var _fails: Array = []
var _dir := ""


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("TRIAL %s: %s" % ["ok" if ok else "FAIL", label])
	if not ok:
		_fails.append(label)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _shot(name: String) -> void:
	if _dir == "":
		return
	await _frames(3)
	DirAccess.make_dir_recursive_absolute(_dir)
	root.get_viewport().get_texture().get_image().save_png(_dir.path_join(name + ".png"))


func _wait_until(cond: Callable, seconds := 10.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while Time.get_ticks_msec() < deadline:
		if cond.call():
			return true
		await process_frame
	return cond.call()


## Hold a direction until the wizard stands at `to` on that axis (or stops moving for a while).
func _walk(dir: Vector2i, to: Vector2i, seconds := 12.0) -> void:
	_world.ui_hold_key_direction(dir)
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	var last: Vector2i = _world._john_pos
	var still := 0
	while Time.get_ticks_msec() < deadline:
		var p: Vector2i = _world._john_pos
		if (dir.x != 0 and p.x == to.x) or (dir.y != 0 and p.y == to.y):
			break
		still = still + 1 if p == last else 0
		last = p
		if still > 60:  # a wall: the host (or the local rule) refuses every step
			break
		await process_frame
	_world.ui_hold_key_direction(Vector2i.ZERO)
	await _wait_until(func(): return not _world._moving, 2.0)
	await _frames(4)


func _set_ward(board: Node, ward: Array) -> bool:
	for sp in ward:
		if not board.ui_pointer_press_tray_spell(int(sp)):
			return false
		await _frames(2)
	if not board.ui_pointer_press_lock_ward():
		return false
	await _frames(3)
	return true


func _cast(board: Node, pattern: Array) -> void:
	for i in pattern.size():
		board.ui_action_select_locus(i)
		board.ui_pointer_press_tray_spell(int(pattern[i]))
		await _frames(1)
	board.ui_action_cast()
	await _frames(2)
	board.ui_advance_time(6.5)
	await _frames(3)


func _fight(board: Node, pool: Array) -> int:
	board.ui_set_fast_cast(true)
	await _set_ward(board, [0, 1, 6])
	var candidates: Array = []
	for a in pool:
		for b in pool:
			for c in pool:
				candidates.append([a, b, c])
	var guesses := 0
	while guesses < 8 and not board.game.result and not candidates.is_empty():
		var attack: Array = candidates[0]
		await _cast(board, attack)
		guesses += 1
		if board.game.player_history.size() < guesses:
			continue
		var rec = board.game.player_history[guesses - 1]
		var kept: Array = []
		for cand in candidates:
			var r: Dictionary = DmbFeedback.score_attack(cand, attack)
			if int(r["fracture"]) == int(rec.fracture_count) and int(r["echo"]) == int(rec.echo_count):
				kept.append(cand)
		candidates = kept
	return guesses


func _board() -> Node:
	return _world._adapter._board


func _entity_ids() -> Array:
	var out: Array = []
	for e in _tm.ui_view().get("entities", []):
		out.append(str(e["id"]))
	return out


func _run() -> void:
	DisplayServer.window_set_size(Vector2i(720, 1280))
	Engine.time_scale = 1.0
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
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
		await _die("hello failed: %s" % str(hello))
		return
	var deadline := Time.get_ticks_msec() + 60000
	while Time.get_ticks_msec() < deadline:
		var lob: Dictionary = _lan.sim.op({"op": "lobby"})
		if str(lob.get("session", {}).get("state", "")) == "playing":
			break
		await create_timer(0.3).timeout
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	await _frames(40)
	if _world._snapshot.is_empty() or not _world.mp:
		await _die("no snapshot or not in LAN mode")
		return
	_tm = _world.trial_mode
	if _world.story_ui != null:
		_world.story_ui.finish_opening()
	await _frames(5)
	# 1. the gate is on the map; we are put beside it (dev teleport) and see it drawn
	var gate: Dictionary = {}
	for e in _world._snapshot.get("entities", []):
		if typeof(e) == TYPE_DICTIONARY and str(e.get("kind", "")) == "trial_gate":
			gate = e
	_check(not gate.is_empty(), "the Trial's gate is a landmark on the map")
	if gate.is_empty():
		await _finish()
		return
	var tp: Dictionary = _world._sim.op({"op": "teleport", "tx": int(gate["tx"]), "ty": int(gate["ty"]) + 1})
	_check(str(tp.get("status", "")) == "ok", "teleported beside the gate (host dev op): %s" % str(tp.get("status", "")))
	_world.refresh_snapshot()
	_world._place_john_from_snapshot()
	await _frames(10)
	await _shot("t01_gate")
	# 2. in, unprepared: a zone built by the legacy tile builder, the pocket strip empty
	var r: Dictionary = _tm.enter()
	_check(str(r.get("status", "")) == "ok", "trial_enter accepted: %s" % str(r))
	await _frames(10)
	_check(_tm.active and str(_world.area_id) == "dd_entrance", "zone mode: area is dd_entrance (%s)" % str(_world.area_id))
	_check(_world._tiles_root.get_child_count() > 100, "cave tiles are built (%d sprites)" % _world._tiles_root.get_child_count())
	_check(_world._john_pos == Vector2i(10, 11), "we stand at the entry tile %s" % str(_world._john_pos))
	_check(_tm.strip.visible and _tm.strip.text.begins_with("Pockets: empty"), "the pocket strip shows empty pockets: %s" % _tm.strip.text)
	_check(_tm.leave_btn.visible, "the way out is offered at the door")
	await _shot("t02_entrance")
	# 3. real steps: east two tiles then the wall refuses; the host agrees with where we stand
	await _walk(Vector2i(1, 0), Vector2i(13, 11), 6.0)
	_check(_world._john_pos.x >= 12 and _world._john_pos.x <= 14, "walked east to the wall: %s" % str(_world._john_pos))
	var v: Dictionary = _world._sim.op({"op": "trial_view"}).get("view", {})
	var vp: Array = v.get("pos", [-1, -1])
	_check(int(vp[0]) == _world._john_pos.x and int(vp[1]) == _world._john_pos.y, "the host's position matches ours after real steps: %s" % str(vp))
	_check(not _tm.leave_btn.visible, "away from the door the way out is not offered")
	# 4. up to the aid box (7,5): along the path, then west; take it
	await _walk(Vector2i(-1, 0), Vector2i(10, 11), 6.0)
	await _walk(Vector2i(0, -1), Vector2i(10, 5), 10.0)
	await _walk(Vector2i(-1, 0), Vector2i(8, 5), 6.0)
	_check(_world._john_pos == Vector2i(8, 5), "beside the box at (8,5): %s" % str(_world._john_pos))
	_world.face_john("left")
	_tm.interact()
	await _frames(6)
	var rep: Dictionary = _tm.last_reply
	_check(str(rep.get("status", "")) == "ok" and str(rep.get("item", {}).get("id", "")) == "sukumvit_note", "took Sukumvit's box: %s" % str(rep.get("item")))
	_check(_tm.card.visible and _tm.ui_card_text().contains("SUKUMVIT"), "the note is read on the card")
	await _shot("t03_aid_box")
	_tm.card.activate_primary()
	await _frames(4)
	_check(not _entity_ids().has("aid_box"), "the box is gone from the zone")
	_check(_tm.strip.text.contains("Sukumvit"), "the pocket strip shows the note: %s" % _tm.strip.text)
	# 5. read the crystal (11,3) from (10,3)
	await _walk(Vector2i(1, 0), Vector2i(10, 5), 6.0)
	await _walk(Vector2i(0, -1), Vector2i(10, 3), 6.0)
	_world.face_john("right")
	_tm.interact()
	await _frames(6)
	_check(_tm.ui_card_text().contains("Crystal") or _tm.ui_card_text().contains("crystal"), "the crystal reads: %s" % _tm.ui_card_text().substr(0, 60))
	_tm.card.activate_primary()
	await _frames(4)
	# 6. through the exit at (9,0) into the Footprint Fork
	await _walk(Vector2i(0, -1), Vector2i(10, 1), 6.0)
	await _walk(Vector2i(-1, 0), Vector2i(9, 1), 4.0)
	await _walk(Vector2i(0, -1), Vector2i(9, 0), 4.0)
	await _wait_until(func(): return str(_world.area_id) == "dd_fork", 5.0)
	_check(str(_world.area_id) == "dd_fork" and _tm.ui_view().get("zone", "") == "dd_fork", "the exit led into the Footprint Fork (%s)" % str(_world.area_id))
	_check(_world._john_pos == Vector2i(9, 12), "placed at the fork's southern door %s" % str(_world._john_pos))
	await _shot("t04_fork")
	# 7. the sign at (6,3) from (6,4)? read dd_prints_east at (7,5) from (7,6)
	await _walk(Vector2i(0, -1), Vector2i(9, 6), 10.0)
	await _walk(Vector2i(-1, 0), Vector2i(7, 6), 6.0)
	_world.face_john("up")
	_tm.interact()
	await _frames(6)
	_check(_tm.card.visible and _tm.ui_card_text().length() > 10, "the footprints sign reads: %s" % _tm.ui_card_text().substr(0, 60))
	_tm.card.activate_primary()
	await _frames(4)
	# 8. the Giant Fly at (16,6): walk east along the corridor to (15,6), face it, the card, the real board
	await _walk(Vector2i(1, 0), Vector2i(15, 6), 12.0)
	_check(_world._john_pos == Vector2i(15, 6), "beside the fly at (15,6): %s" % str(_world._john_pos))
	_world.face_john("right")
	_tm.interact()
	await _frames(6)
	rep = _tm.last_reply
	_check(str(rep.get("status", "")) == "started" and str(rep.get("enemy", "")) == "giant_fly", "the fly is a lease: %s" % str(rep.get("status")))
	_check(_tm.card.visible and _tm.ui_card_text().length() > 10, "the fly's introduction is on the card")
	await _shot("t05_fly_card")
	_tm.card.activate_primary()
	var opened := await _wait_until(func(): return _world._duel_open and _board() != null and is_instance_valid(_board()), 8.0)
	_check(opened, "the real board opened for the fly")
	var outcome := "no_board"
	if opened:
		var board := _board()
		await _shot("t06_fly_board")
		await _fight(board, [1, 6])
		if board.game.result != null:
			outcome = str(board.game.result.outcome)
			if await _wait_until(func(): return board.ui_is_result_visible(), 8.0):
				board.ui_pointer_press_overlay_button("Continue")
		await _frames(12)
	print("TRIAL fly outcome: %s" % outcome)
	_check(outcome in ["victory", "defeat", "stalemate"], "the fly's duel finished: %s" % outcome)
	await _wait_until(func(): return not _world._duel_open, 8.0)
	await _frames(6)
	var ids := _entity_ids()
	if outcome == "victory":
		_check(not ids.has("fly_east"), "a won duel removes the fly from the zone")
	else:
		_check(ids.has("fly_east"), "the fly stays after a loss or a draw")
		if outcome == "defeat":
			_check((_tm.ui_view().get("conditions", []) as Array).has("wounded"), "a loss to the fly wounds (one cast fewer)")
	_check(not _world._dead_mode, "the fly never kills")
	await _shot("t07_after_fly")
	# 9. the way out is only the way in
	var lv: Dictionary = _world._sim.op({"op": "trial_leave"})
	_check(str(lv.get("reason", "")) == "not_at_the_door", "leaving from the fork is refused: %s" % str(lv.get("reason")))
	_check(_tm.active and str(_world.area_id) == "dd_fork", "still inside, in the fork")
	await _finish()


func _finish() -> void:
	if _fails.is_empty():
		print("HYBRID_TRIAL_OK")
	else:
		print("HYBRID_TRIAL_FAIL %s" % " | ".join(PackedStringArray(_fails)))
	await _frames(3)
	quit(0 if _fails.is_empty() else 1)


func _die(msg: String) -> void:
	print("HYBRID_TRIAL_FAIL %s" % msg)
	await _frames(2)
	quit(1)
