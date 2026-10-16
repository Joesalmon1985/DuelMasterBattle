extends SceneTree

## Headed acceptance for the Trial's second half (plan M6): this Godot client joins a Python-hosted Wizard World (lan_bot.py started it and stays
## put), goes in, and is stood in the later zones by the host's dev-only `trial_teleport` (the walk is M5's business). It takes the Dwarf's tests on
## the card (Stone learned), faces Throm on the REAL board (his face on the board, a boss budget), wakes the idol's second guardian by taking the
## false eye (a duel born of a choice), takes the emerald, smashes the mirrors for Light without a duel, collects the sapphire and the diamond,
## places the gems at Igbut's door (a wrong order bites, the right one opens on daylight: the zone closes over the hex world), and in a fresh run
## loses to the Trialmastiff to see the dead mode inside a zone. Env: HYBRID_LAN_HOST, HYBRID_LAN_PORT, HYBRID_LAN_CODE, HYBRID_SHOT_DIR.
## Prints HYBRID_TRIAL_FULL_OK or HYBRID_TRIAL_FULL_FAIL <reasons>.

var _lan: Node
var _world: Node
var _tm: Node
var _fails: Array = []
var _dir := ""


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("TRIALFULL %s: %s" % ["ok" if ok else "FAIL", label])
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


## Stand in a zone (host dev op), wait for the client to build it, face a way.
func _stand(zone: String, x: int, y: int, facing: String) -> bool:
	var r: Dictionary = _world._sim.op({"op": "trial_teleport", "zone": zone, "x": x, "y": y})
	if str(r.get("status", "")) != "ok":
		_check(false, "trial_teleport %s refused: %s" % [zone, str(r)])
		return false
	var ok := await _wait_until(func(): return str(_world.area_id) == zone and _world._john_pos == Vector2i(x, y) and not _world._moving, 8.0)
	_world.face_john(facing)
	await _frames(3)
	return ok


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


func _board() -> Node:
	return _world._adapter._board


## The card's "Begin the duel", then the real board: our Ward, then the one cast that breaks theirs (the test knows the answer; the board does the rest).
## `win` false: cast a colour outside their Ward until they break ours. Returns the board's outcome.
func _duel(win: bool) -> String:
	if not _tm.card.visible:
		return "no_card"
	_tm.card.activate_primary()
	if not await _wait_until(func(): return _world._duel_open and _board() != null and is_instance_valid(_board()), 8.0):
		return "no_board"
	var board := _board()
	board.ui_set_fast_cast(true)
	var pool: Array = Array(board._player_c.attack_pool)
	var size: int = int(board._player_c.weave_size)
	var mine: Array = []
	for i in size:
		mine.append(pool[i % pool.size()])
	await _set_ward(board, mine)
	var ward: Array = Array(board.game.get_enemy_ward())
	var casts := 0
	while board.game.result == null and casts < 12:
		if win:
			await _cast(board, ward)
		else:
			var miss := -1
			for c in pool:
				if not ward.has(c):
					miss = int(c)
			var pattern: Array = []
			for i in size:
				pattern.append(miss if miss >= 0 else ward[(i + 1) % ward.size()])
			await _cast(board, pattern)
		casts += 1
	var outcome := "unfinished"
	if board.game.result != null:
		outcome = str(board.game.result.outcome)
		if await _wait_until(func(): return board.ui_is_result_visible(), 8.0):
			board.ui_pointer_press_overlay_button("Continue")
	await _wait_until(func(): return not _world._duel_open, 8.0)
	await _frames(8)
	return outcome


func _ids() -> Array:
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
	var gate: Dictionary = {}
	for e in _world._snapshot.get("entities", []):
		if typeof(e) == TYPE_DICTIONARY and str(e.get("kind", "")) == "trial_gate":
			gate = e
	if gate.is_empty():
		await _die("no gate")
		return
	_world._sim.op({"op": "teleport", "tx": int(gate["tx"]), "ty": int(gate["ty"]) + 1})
	_world.refresh_snapshot()
	_world._place_john_from_snapshot()
	await _frames(6)
	var r: Dictionary = _tm.enter()
	_check(str(r.get("status", "")) == "ok", "entered the Trial")
	await _frames(8)
	# 1. the Dwarf's tests on the card: Stone learned
	if await _stand("dd_trialmaster", 9, 5, "up"):
		_check(str(_world.area_id) == "dd_trialmaster" and _world._tiles_root.get_child_count() > 100, "the Trialmaster Complex is built (%d tiles)" % _world._tiles_root.get_child_count())
		_tm.interact()
		await _frames(5)
		_check(_tm.card.visible and _tm.ui_card_choices() == ["accept"], "the Dwarf offers the test: %s" % str(_tm.ui_card_choices()))
		await _shot("f01_dwarf")
		_tm.card.activate_choice_id("accept")
		await _frames(4)
		_check(_tm.ui_card_choices() == ["same", "less", "more"], "the dice: %s" % str(_tm.ui_card_choices()))
		_tm.card.activate_choice_id("less")
		await _frames(4)
		_check(_tm.ui_card_choices() == ["gaze", "snatch"] and _tm.ui_card_text().contains("The cup lifts"), "the cobra after the roll")
		_tm.card.activate_choice_id("gaze")
		await _frames(4)
		_check(_tm.ui_card_text().contains("Stone"), "the map and Stone: %s" % _tm.ui_card_text().substr(0, 50))
		await _shot("f02_dwarf_map")
		_tm.card.activate_primary()
		await _frames(4)
		_check(_ids().has("throm_arena"), "Throm is dragged into the arena")
	# 2. Throm, delirious, on the real board
	if await _stand("dd_trialmaster", 5, 7, "left"):
		_tm.interact()
		await _frames(5)
		var rep: Dictionary = _tm.last_reply
		_check(str(rep.get("status", "")) == "started" and str(rep.get("enemy", "")) == "throm_duel", "Throm is a lethal lease: %s" % str(rep.get("status")))
		_check(_tm.card.visible and _tm.ui_card_text().contains("crossbow"), "Throm's introduction on the card")
		var outcome := await _duel(true)
		var board_arch := ""
		print("TRIALFULL throm outcome: %s" % outcome)
		_check(outcome == "victory", "Throm's Ward broken on the real board: %s" % outcome)
		_check(not _ids().has("throm_arena") and not _world._dead_mode, "Throm falls; we live")
		await _shot("f03_after_throm")
	# 3. the idol: the false eye wakes the second guardian (a duel from a choice); the emerald
	if await _stand("dd_idol", 11, 3, "down"):
		_tm.interact()
		await _frames(5)
		_check(_tm.ui_card_choices() == ["take", "leave"], "the false eye asks first: %s" % str(_tm.ui_card_choices()))
		_tm.card.activate_choice_id("take")
		await _frames(6)
		_check(_tm.card.visible and _tm.ui_card_text().contains("finds you"), "the guardian finds you: %s" % _tm.ui_card_text().substr(0, 60))
		await _shot("f04_guardian_card")
		var outcome := await _duel(true)
		print("TRIALFULL guardian outcome: %s" % outcome)
		_check(outcome == "victory", "the second guardian broken: %s" % outcome)
		_check(_ids().has("emerald_eye") and not _ids().has("guard_idol2"), "the emerald eye is free to take")
	if await _stand("dd_idol", 8, 3, "down"):
		_tm.interact()
		await _frames(5)
		_check(_tm.strip.text.contains("Gems: emerald"), "the strip shows the emerald: %s" % _tm.strip.text)
		_tm.card.activate_primary()
		await _frames(3)
	# 4. the mirrors: smashed, Light without a duel
	if await _stand("dd_mirror", 10, 5, "up"):
		_tm.interact()
		await _frames(5)
		_check(_tm.ui_card_choices() == ["smash", "leave"], "the mirrors ask: %s" % str(_tm.ui_card_choices()))
		_tm.card.activate_choice_id("smash")
		await _frames(5)
		_check(_tm.ui_card_text().contains("without a duel"), "silver rain")
		_tm.card.activate_primary()
		await _frames(4)
		_check(not _ids().has("demon_mirror1") and _ids().has("light_shard"), "the demon is gone, the shard lies in the frame")
		await _shot("f05_mirrors")
	if await _stand("dd_mirror", 10, 3, "up"):
		_tm.interact()
		await _frames(5)
		_check(_tm.last_reply.get("spell", -1) == 4, "Light learned from the shard")
		_tm.card.activate_primary()
		await _frames(3)
	# 5. the sapphire and the diamond
	if await _stand("dd_vaults", 9, 3, "up"):
		_tm.interact()
		await _frames(5)
		_check(str(_tm.last_reply.get("gem", "")) == "sapphire", "the sapphire and its key")
		_tm.card.activate_primary()
		await _frames(3)
	if await _stand("dd_vault_inner", 7, 5, "up"):
		_tm.interact()
		await _frames(5)
		_check(str(_tm.last_reply.get("gem", "")) == "diamond", "the true diamond")
		_check(_tm.strip.text.contains("Gems: emerald, sapphire, diamond"), "three gems on the strip: %s" % _tm.strip.text)
		_tm.card.activate_primary()
		await _frames(3)
		await _shot("f06_three_gems")
	# 6. Igbut's door: a wrong order bites, the right one opens on daylight; the zone closes over the hex world
	if await _stand("dd_igbut", 8, 7, "up"):
		_tm.interact()
		await _frames(5)
		_check(_tm.ui_card_choices() == ["face", "later"], "Igbut: %s" % str(_tm.ui_card_choices()))
		_tm.card.activate_choice_id("face")
		await _frames(4)
		_check(_tm.ui_card_choices().size() == 6, "six orders offered")
		await _shot("f07_gem_lock")
		_tm.card.activate_choice_id("ESD")
		await _frames(4)
		_check(_tm.ui_card_text().contains("1 placed true"), "the door bites: %s" % _tm.ui_card_text().substr(0, 40))
		_tm.card.activate_choice_id("SED")
		await _frames(6)
		_check(_tm.card.visible and _tm.ui_card_text().contains("CHAMPION"), "the champion's page")
		await _shot("f08_champion")
		var out := await _wait_until(func(): return not _tm.active, 8.0)
		_check(out and str(_world.area_id) == "hybrid", "the Trial let everyone out: back on the map (%s)" % str(_world.area_id))
		_check(_tm.card.visible, "the champion's page stays over the daylight until read")
		_tm.card.activate_primary()
		await _frames(6)
		_check(not _tm.card.visible and not _world._input_locked, "read, and the map is ours again")
		var g := Vector2i(int(gate["tx"]), int(gate["ty"]))
		_check(maxi(absi(_world._john_pos.x - g.x), absi(_world._john_pos.y - g.y)) <= 3, "standing at the gate %s" % str(_world._john_pos))
		await _shot("f09_daylight")
	# 7. a fresh run: lose to the mastiff; dead inside the zone
	r = _tm.enter()
	_check(str(r.get("status", "")) == "ok" and str(r.get("run", "")) == "trial:2", "a new run begins: %s" % str(r.get("run")))
	await _frames(8)
	if await _stand("dd_galleries", 13, 8, "down"):
		_tm.interact()
		await _frames(5)
		_check(str(_tm.last_reply.get("enemy", "")) == "guard_dog" and bool(_tm.last_reply.get("lethal", false)), "the mastiff, lethal")
		var outcome := await _duel(false)
		print("TRIALFULL mastiff outcome: %s" % outcome)
		_check(outcome == "defeat", "lost to the mastiff on purpose: %s" % outcome)
		var dead := await _wait_until(func(): return _world._dead_mode, 10.0)
		_check(dead and _tm.active and str(_world.area_id) == "dd_galleries", "dead inside the zone: the zone stays on screen")
		_check(not _world._john.visible, "the standing avatar is gone")
		var bodies: Array = _tm.ui_view().get("bodies", [])
		_check(bodies.size() == 1 and int(bodies[0]["x"]) == 13, "our body lies where we fell: %s" % str(bodies))
		await _shot("f10_dead_inside")
	await _finish()


func _finish() -> void:
	if _fails.is_empty():
		print("HYBRID_TRIAL_FULL_OK")
	else:
		print("HYBRID_TRIAL_FULL_FAIL %s" % " | ".join(PackedStringArray(_fails)))
	await _frames(3)
	quit(0 if _fails.is_empty() else 1)


func _die(msg: String) -> void:
	print("HYBRID_TRIAL_FULL_FAIL %s" % msg)
	await _frames(2)
	quit(1)
