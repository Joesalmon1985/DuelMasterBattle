extends SceneTree

## Dungeon flow test, P3 Trialmaster: Dwarf tests (dice/cobra) earn Stone;
## forced Throm duel on the ally path; betrayal and attack variants.
##
## godot --headless --path godot_project --script res://client/tests/run_dungeon_p3.gd

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
	await _test_ally_path()
	await _test_betrayed_path()
	await _test_attack_path()
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


func _drain_dialogue(max_lines: int = 60) -> void:
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
		elif not _world.ui_input_locked() or not _adv.pending_battle.is_empty():
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
	if win:
		# A deliberate win: the player reads the Ward and casts before the enemy acts.
		game.debug_set_enemy_cast_at(999.0)
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

func _setup_p3(ally: bool) -> void:
	_adv.new_game()
	for ph in ["john_intro", "ashby_training", "pre_trial", "trial"]:
		_adv.advance_phase(ph)
	_adv.set_flag("opening_seen")
	_adv.set_flag("entered_trial")
	_adv.learn_spell(1)
	_adv.learn_spell(6)
	_adv.learn_spell(0)
	_adv.learn_spell(3)
	_adv.grow_weave(3)
	_adv.start_run()
	_adv.set_run_flag("troll_down")
	_adv.mark("defeated", "troll_lower1")
	if ally:
		_adv.set_run_flag("pit_ally")
		_adv.set_contestant("throm", "uneasy_ally")
	else:
		_adv.set_run_flag("pit_betrayed")
		_adv.set_contestant("throm", "betrayed")
	_adv.set_location("dd_lower", 3, 5, "left")


func _enter_trialmaster() -> void:
	await _new_world()
	await _drain_dialogue()
	await _walk_to(Vector2i(1, 5))
	await _walk(Vector2i(-1, 0), 1)
	var g := 0
	while _world.area_id != "dd_trialmaster" and g < 120:
		await process_frame
		g += 1
	assert_eq(_world.area_id, "dd_trialmaster", "entered the Trialmaster complex")


func _do_dwarf_tests(first_choice: String) -> void:
	await _walk_to(Vector2i(9, 5))
	await _face(Vector2i(0, -1))
	assert_true(_world.ui_prompt().begins_with("Talk"), "dwarf prompt")
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose(first_choice)
	await process_frame
	await _drain_dialogue()
	_world.ui_dialogue_choose("More than 8")
	await process_frame
	await _drain_dialogue()
	_world.ui_dialogue_choose("Hold its gaze")
	await process_frame
	await _drain_dialogue()
	assert_true(_adv.run_flag("dwarf_map"), "earned the Dwarf's map from the test (D1)")


func _test_ally_path() -> void:
	await _setup_p3(true)
	await _enter_trialmaster()
	await _do_dwarf_tests("Accept the test")
	assert_true(_adv.run_flag("trial_ready"), "trial ready after tests")
	assert_true(_world.ui_entity_exists("throm_arena"), "Throm is sent in")
	await _walk_to(Vector2i(4, 8))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Fight")
	await process_frame
	var out := await _fight_from_world(true)
	assert_eq(out, "victory", "Throm duel won")
	assert_true(_adv.run_flag("trial_done"), "trial done after the duel")
	assert_eq(str(_adv.run_state()["contestants"].get("throm", "")), "dead", "Throm is dead")
	await _free_world()


func _test_betrayed_path() -> void:
	await _setup_p3(false)
	await _enter_trialmaster()
	await _do_dwarf_tests("Accept the test")
	assert_true(_adv.run_flag("trial_done"), "trial done without a duel")
	assert_true(not _world.ui_entity_exists("throm_duel"), "no invented arena opponent")
	assert_true(_adv.run_flag("dwarf_map"), "map earned alone too")
	await _free_world()


func _test_attack_path() -> void:
	await _setup_p3(true)
	await _enter_trialmaster()
	await _walk_to(Vector2i(9, 5))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Attack with Throm")
	await process_frame
	await _drain_dialogue()
	assert_true("wounded" in _adv.run_state().get("conditions", []), "attacking the Dwarf wounds")
	_world.ui_dialogue_choose("More than 8")
	await process_frame
	await _drain_dialogue()
	_world.ui_dialogue_choose("Hold its gaze")
	await process_frame
	await _drain_dialogue()
	assert_true(_adv.run_flag("dwarf_map"), "test proceeds after the attack")
	await _free_world()


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
		print("DUNGEON P3: ALL PASSED")
		quit(0)
	else:
		print("DUNGEON P3: %d FAILURE(S)" % _failures.size())
		for f in _failures:
			print("  - %s" % f)
		quit(1)
