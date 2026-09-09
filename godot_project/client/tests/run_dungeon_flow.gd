extends SceneTree

## Dungeon flow test, P2 slice: Crystal Entrance → fork (fly) → galleries
## (riddle, torch, dog) → pit (Throm choice) → lower (Fire, potion, troll).
## Loses the troll fight → fail_run restarts at the gate with knowledge kept;
## restarts, wins, takes the ring. Also proves run pickups + fights reset.
##
## godot --headless --path godot_project --script res://client/tests/run_dungeon_flow.gd

const _BattleSim = preload("res://sim/battle_sim.gd")

var _failures: Array = []
var _world
var _adv


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	_ensure_autoloads()
	_adv = root.get_node("Adventure")
	_adv.delete_save()
	await process_frame
	await _test_slice()
	_report()


func _ensure_autoloads() -> void:
	for pair in [["EncounterSession", "res://client/scripts/encounter_session.gd"], ["Sfx", "res://client/scripts/sfx.gd"], ["Adventure", "res://client/scripts/adventure.gd"]]:
		if root.get_node_or_null(pair[0]) == null:
			var n = load(pair[1]).new()
			n.name = pair[0]
			root.add_child(n)


func _new_world() -> void:
	_world = load("res://client/scenes/overworld.tscn").instantiate()
	_world.test_mode = true
	root.add_child(_world)
	await process_frame
	await process_frame


func _free_world() -> void:
	if _world and is_instance_valid(_world):
		_world.queue_free()
		_world = null
	await process_frame


func _drain_dialogue(max_lines: int = 40) -> void:
	# Warm-up: ui_action starts the dialogue asynchronously; do not conclude
	# "nothing to drain" before it has had a chance to open or lock input.
	var warm := 0
	while warm < 120 and not _world.ui_dialogue_open() and not _world.ui_input_locked():
		await process_frame
		warm += 1
	var guard := 0
	while guard < max_lines * 60:
		guard += 1
		await process_frame
		if _world.ui_dialogue_open():
			if _world.ui_dialogue_waiting_choice():
				return
			_world.ui_dialogue_advance()
			await process_frame
			_world.ui_dialogue_advance()
			await process_frame
		elif not _world.ui_input_locked():
			return
	_failures.append("dialogue/cutscene did not finish")


func _walk(dir: Vector2i, steps: int) -> void:
	for i in range(steps):
		var guard := 0
		while (_world.ui_is_moving() or _world.ui_input_locked()) and guard < 600:
			await process_frame
			guard += 1
		_world.ui_step(dir)
		var g2 := 0
		while _world.ui_is_moving() and g2 < 600:
			await process_frame
			g2 += 1


func _walk_to(target: Vector2i) -> void:
	var start: Vector2i = _world.john_pos()
	if start == target:
		return
	var prev: Dictionary = {start: start}
	var queue: Array = [start]
	var found := false
	while not queue.is_empty():
		var cur: Vector2i = queue.pop_front()
		if cur == target:
			found = true
			break
		for dir in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
			var nxt: Vector2i = cur + dir
			if prev.has(nxt) or nxt.x < 0 or nxt.y < 0 or nxt.x >= _world.grid_w or nxt.y >= _world.grid_h:
				continue
			if not _world.ui_tile_walkable(nxt):
				continue
			if nxt != target and _world.ui_is_exit(nxt):
				continue
			prev[nxt] = cur
			queue.append(nxt)
	if not found:
		_failures.append("no path to %s from %s in %s" % [target, start, _world.area_id])
		return
	var path: Array = []
	var c := target
	while c != start:
		path.push_front(c)
		c = prev[c]
	for step in path:
		var dir: Vector2i = step - _world.john_pos()
		await _walk(dir, 1)
		if _world.area_id != _world.area_id or _world.john_pos() != step:
			break
	if _world.john_pos() != target:
		_failures.append("could not walk to %s (at %s)" % [target, _world.john_pos()])


func _face(dir: Vector2i) -> void:
	_world.ui_step(dir)
	await process_frame
	var guard := 0
	while _world.ui_is_moving() and guard < 600:
		await process_frame
		guard += 1


func _interact() -> void:
	var guard2 := 0
	while _world.ui_is_moving() and guard2 < 600:
		await process_frame
		guard2 += 1
	_world.ui_action()
	await process_frame
	await process_frame


## Fight to a forced outcome. rig_ward optionally fixes the enemy Ward
## (used to make losses deterministic: Water attacks never break Fire).
func _fight(win: bool, rig_ward: Array = []) -> String:
	var board = load("res://client/scenes/game_board.tscn").instantiate()
	root.add_child(board)
	await process_frame
	assert_true(board.ui_is_overlay_visible(), "encounter intro shows")
	board.ui_dismiss_overlay()
	await process_frame
	var game = board.game
	var pc: DmbCombatant = game.player
	var ec: DmbCombatant = game.enemy
	for i in range(pc.ward_size):
		board.ui_action_select_locus(i)
		board.ui_action_pick_spell(int(pc.ward_pool[0]))
	board.ui_action_lock_ward()
	await process_frame
	assert_eq(int(board.ui_get_phase()), int(_BattleSim.Phase.DUELING), "battle enters duelling")
	if not rig_ward.is_empty():
		game.debug_set_enemy_ward(rig_ward)
	var enemy_ward: Array = game.get_enemy_ward()
	var casts := 0
	while game.phase == _BattleSim.Phase.DUELING and casts < 12:
		game.advance_time_for_test(5.5)
		var pattern: Array = []
		if win:
			for i in range(pc.weave_size):
				var t := DmbFeedback.target_slot(i, ec.ward_size)
				pattern.append(int(enemy_ward[t]))
		else:
			for i in range(pc.weave_size):
				pattern.append(int(pc.attack_pool[0]))
		game.load_player_attack(pattern)
		board.ui_action_cast()
		casts += 1
		game.advance_time_for_test(0.5)
		var g := 0
		while game.phase == _BattleSim.Phase.DUELING and g < 200 and game.player_cast_block_reason() != "" and game.player_cast_block_reason().begins_with("Weaving"):
			game.advance_time_for_test(1.0)
			g += 1
		await process_frame
		await process_frame
		await process_frame
	# Enemy may still have casts after the player exhausts; let it finish.
	var tail := 0
	while game.phase == _BattleSim.Phase.DUELING and tail < 60:
		game.advance_time_for_test(5.0)
		tail += 1
	var outcome := ""
	if game.result != null:
		outcome = game.result.outcome
	assert_true(outcome != "", "battle reaches a result")
	board.ui_adventure_continue()
	await process_frame
	board.queue_free()
	await process_frame
	return outcome


func _fight_from_world(win: bool, rig_ward: Array = []) -> String:
	var g := 0
	while _adv.pending_battle.is_empty() and g < 120:
		await process_frame
		g += 1
	assert_true(not _adv.pending_battle.is_empty(), "overworld requested a battle")
	await _free_world()
	var outcome := await _fight(win, rig_ward)
	await _new_world()
	await _drain_dialogue()
	return outcome


# ---------------------------------------------------------------------------------

func _setup_run() -> void:
	_adv.new_game()
	_adv.set_flag("opening_seen")
	_adv.set_flag("duel_seen")
	_adv.set_flag("has_staff")
	_adv.set_flag("entered_trial")
	_adv.learn_spell(1)
	_adv.grow_weave(1)
	_adv.start_run()
	assert_true(_adv.run_active(), "run active for slice")


func _test_slice() -> void:
	await _setup_run()
	await _new_world()
	await _drain_dialogue()
	assert_eq(_world.area_id, "dd_entrance", "run starts at the entrance")

	# Aid box: Sukumvit's warning, run-scoped.
	await _walk_to(Vector2i(7, 6))
	await _face(Vector2i(0, -1))
	assert_eq(_world.ui_prompt(), "Take", "aid box prompt")
	await _interact()
	await _drain_dialogue()
	assert_true(_adv.run_flag("picked_aid_box"), "aid box taken (run-scoped)")

	# North to the fork; knowledge records the visit.
	await _walk_to(Vector2i(9, 1))
	await _walk(Vector2i(0, -1), 1)
	var g := 0
	while _world.area_id != "dd_fork" and g < 120:
		await process_frame
		g += 1
	assert_eq(_world.area_id, "dd_fork", "reached the fork")
	assert_true(_adv.knowledge_status("dd_fork") != "unknown", "fork recorded in knowledge")

	# Painted arrow, then the eastern fly.
	await _walk_to(Vector2i(6, 4))
	await _face(Vector2i(0, -1))
	assert_eq(_world.ui_prompt(), "Look", "arrow prompt")
	await _interact()
	await _drain_dialogue()
	await _walk_to(Vector2i(15, 6))
	await _face(Vector2i(1, 0))
	assert_true(_world.ui_prompt().begins_with("Face"), "east fly prompt: %s" % _world.ui_prompt())
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Fight")
	await process_frame
	var out := await _fight_from_world(true)
	assert_eq(out, "victory", "east fly beaten")
	assert_true(_adv.marked("defeated", "fly_east"), "fly recorded")

	# West to the galleries; answer the old man.
	await _walk_to(Vector2i(1, 6))
	await _walk(Vector2i(-1, 0), 1)
	g = 0
	while _world.area_id != "dd_galleries" and g < 120:
		await process_frame
		g += 1
	assert_eq(_world.area_id, "dd_galleries", "reached the galleries")
	await _walk_to(Vector2i(9, 5))
	await _face(Vector2i(0, -1))
	assert_true(_world.ui_prompt().begins_with("Talk"), "old man prompt")
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("150")
	await process_frame
	await _drain_dialogue()
	assert_true(_adv.run_flag("riddle_answered"), "riddle answered")

	# Torch, then the guard dog.
	await _walk_to(Vector2i(5, 12))
	await _face(Vector2i(0, 1))
	await _interact()
	await _drain_dialogue()
	assert_true(_adv.run_flag("picked_dd_torch"), "torch taken (run-scoped)")
	await _walk_to(Vector2i(14, 9))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Fight")
	await process_frame
	out = await _fight_from_world(true)
	assert_eq(out, "victory", "guard dog beaten")

	# West to the pit; Throm's choice (betrayal path deferred, ally path here).
	await _walk_to(Vector2i(1, 8))
	await _walk(Vector2i(-1, 0), 1)
	g = 0
	while _world.area_id != "dd_pit" and g < 120:
		await process_frame
		g += 1
	assert_eq(_world.area_id, "dd_pit", "reached the pit")
	assert_eq(str(_adv.run_state()["contestants"].get("throm", "")), "ahead", "Throm ahead until met")
	await _walk_to(Vector2i(6, 7))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Offer to lower him")
	await process_frame
	await _drain_dialogue()
	_world.ui_dialogue_choose("Climb down after him")
	await process_frame
	await _drain_dialogue()
	assert_true(_adv.run_flag("pit_ally"), "pit alliance formed")
	assert_eq(str(_adv.run_state()["contestants"].get("throm", "")), "uneasy_ally", "Throm allied")

	# West to the lower route; greet Throm, read the red book, drink the vial.
	await _walk_to(Vector2i(1, 8))
	await _walk(Vector2i(-1, 0), 1)
	g = 0
	while _world.area_id != "dd_lower" and g < 120:
		await process_frame
		g += 1
	assert_eq(_world.area_id, "dd_lower", "reached the lower route")
	await _walk_to(Vector2i(4, 6))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	await _walk_to(Vector2i(5, 5))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	assert_true(_adv.progression.knows(0), "learned Fire from the red book")
	assert_eq(_adv.progression.weave_size, 2, "weave 2 after red book")
	await _walk_to(Vector2i(6, 5))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Drink it")
	await process_frame
	await _drain_dialogue()
	assert_true("poisoned" in _adv.run_state().get("conditions", []), "vial poisons")
	assert_eq(_adv.player_mods().get("min_cast_bonus", -1.0), 2.0, "poison slows next duel")

	# Lose the troll fight on purpose (rigged Fire Ward): the run ends at the gate.
	await _walk_to(Vector2i(15, 8))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Fight")
	await process_frame
	var w := 0
	while _adv.pending_battle.is_empty() and w < 120:
		await process_frame
		w += 1
	assert_true(_adv.pending_battle.get("player_mods", {}).has("min_cast_bonus"), "mods ride into battle")
	out = await _fight_from_world(false, [0, 0])
	assert_eq(out, "defeat", "troll takes John apart")
	assert_eq(_world.area_id, "trial_gate", "failed run restarts at the gate")
	assert_true(not _adv.run_active(), "run inactive after fail")
	assert_eq(_adv.knowledge_status("dd_lower"), "entered", "knowledge kept after fail")
	assert_true(_adv.progression.knows(0), "Fire kept after fail")
	assert_eq(_adv.progression.weave_size, 2, "weave kept after fail")
	assert_eq(_adv.run_state().get("conditions", ["x"]), [], "conditions cleared after fail")
	assert_true(_adv.flag("entered_trial"), "world flags kept after fail")

	# Second run: fights and run pickups are back; win the troll, take the ring.
	_adv.start_run()
	await _free_world()
	await _new_world()
	await _drain_dialogue()
	assert_eq(_world.area_id, "dd_entrance", "second run starts clean")
	assert_true(not _adv.marked("defeated", "fly_east"), "fights reset for the new run")
	await _walk_to(Vector2i(9, 1))
	await _walk(Vector2i(0, -1), 1)
	g = 0
	while _world.area_id != "dd_fork" and g < 120:
		await process_frame
		g += 1
	await _walk_to(Vector2i(1, 6))
	await _walk(Vector2i(-1, 0), 1)
	g = 0
	while _world.area_id != "dd_galleries" and g < 120:
		await process_frame
		g += 1
	await _walk_to(Vector2i(9, 5))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("150")
	await process_frame
	await _drain_dialogue()
	await _walk_to(Vector2i(1, 8))
	await _walk(Vector2i(-1, 0), 1)
	g = 0
	while _world.area_id != "dd_pit" and g < 120:
		await process_frame
		g += 1
	await _walk_to(Vector2i(6, 7))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Let him lower you")
	await process_frame
	await _drain_dialogue()
	await _walk_to(Vector2i(1, 8))
	await _walk(Vector2i(-1, 0), 1)
	g = 0
	while _world.area_id != "dd_lower" and g < 120:
		await process_frame
		g += 1
	await _walk_to(Vector2i(5, 5))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	assert_true(_adv.run_flag("picked_red_book"), "red book takeable again after fail")
	await _walk_to(Vector2i(15, 8))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Fight")
	await process_frame
	out = await _fight_from_world(true)
	assert_eq(out, "victory", "troll beaten on the second run")
	assert_true(_adv.run_flag("troll_down"), "troll run flag set")
	assert_eq(str(_adv.run_state()["contestants"].get("throm", "")), "wounded", "Throm wounded after")
	await _walk_to(Vector2i(15, 8))
	await _face(Vector2i(0, 1))
	assert_eq(_world.ui_prompt(), "Take", "bone ring left where the troll fell")
	await _interact()
	await _drain_dialogue()
	assert_true(_adv.run_flag("picked_bone_ring"), "bone ring taken")

	_adv.save()
	await _free_world()
	assert_true(_adv.load_game(), "final reload")
	assert_true(_adv.progression.knows(0), "Fire persisted")
	assert_eq(_adv.knowledge_status("dd_lower"), "entered", "knowledge persisted")


# --- assertions --------------------------------------------------------------------

func assert_true(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)
		print("  FAIL: %s" % msg)


func assert_eq(a, b, msg: String) -> void:
	if a != b:
		_failures.append("%s (got %s, expected %s)" % [msg, a, b])
		print("  FAIL: %s (got %s, expected %s)" % [msg, a, b])


func _report() -> void:
	if _failures.is_empty():
		print("DUNGEON FLOW: ALL PASSED")
		quit(0)
	else:
		print("DUNGEON FLOW: %d FAILURE(S)" % _failures.size())
		for f in _failures:
			print("  - %s" % f)
		quit(1)
