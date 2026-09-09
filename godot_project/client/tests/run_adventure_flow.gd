extends SceneTree

## Adventure flow test, P1 Trial-Day path: New Game in Ashwell → duel cutscene
## → staff (Water/1) → Ashby lessons → trial_road (fly) → Burnt Wood training
## detour → trial_gate roster → NOT YET → ENTER → threshold ending.
##
## godot --headless --path godot_project --script res://client/tests/run_adventure_flow.gd

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
	await _test_menu_resume_states()
	await _test_chapter()
	_report()


func _ensure_autoloads() -> void:
	for pair in [["EncounterSession", "res://client/scripts/encounter_session.gd"], ["Sfx", "res://client/scripts/sfx.gd"], ["Adventure", "res://client/scripts/adventure.gd"]]:
		if root.get_node_or_null(pair[0]) == null:
			var n = load(pair[1]).new()
			n.name = pair[0]
			root.add_child(n)


# ---------------------------------------------------------------------------------

func _test_menu_resume_states() -> void:
	var menu = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(menu)
	await process_frame
	assert_true(not menu.ui_resume_enabled(), "Resume disabled with no save")
	_adv.new_game()
	_adv.save()
	menu.queue_free()
	await process_frame
	menu = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(menu)
	await process_frame
	assert_true(menu.ui_resume_enabled(), "Resume enabled once a save exists")
	menu.ui_new_game()
	await process_frame
	assert_true(menu.ui_is_overlay_visible(), "New Game warns before overwriting")
	menu.queue_free()
	await process_frame
	_adv.delete_save()


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
	# Advance through any open dialogue, waiting out cutscene tweens.
	var guard := 0
	while guard < max_lines * 60:
		guard += 1
		await process_frame
		if _world.ui_dialogue_open():
			if _world.ui_dialogue_waiting_choice():
				return
			_world.ui_dialogue_advance()
			await process_frame
			_world.ui_dialogue_advance()  # second call finishes typing → closes
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
		while _world.ui_is_moving() and g2 < 60:
			await process_frame
			g2 += 1


func _walk_to(target: Vector2i) -> void:
	# BFS over walkable tiles, then step along the path.
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
	# Step into a solid tile just turns John.
	_world.ui_step(dir)
	await process_frame


func _interact() -> void:
	_world.ui_action()
	await process_frame
	await process_frame


## Fight the pending battle to a forced outcome using legal moves only.
func _fight(win: bool) -> String:
	var board = load("res://client/scenes/game_board.tscn").instantiate()
	root.add_child(board)
	await process_frame
	assert_true(board.ui_is_overlay_visible(), "encounter intro shows")
	board.ui_dismiss_overlay()
	await process_frame
	var game = board.game
	var pc: DmbCombatant = game.player
	var ec: DmbCombatant = game.enemy
	# Ward: first pool spell everywhere (legal).
	for i in range(pc.ward_size):
		board.ui_action_select_locus(i)
		board.ui_action_pick_spell(int(pc.ward_pool[0]))
	board.ui_action_lock_ward()
	await process_frame
	assert_eq(int(board.ui_get_phase()), int(_BattleSim.Phase.DUELING), "battle enters duelling")
	var enemy_ward: Array = game.get_enemy_ward()
	var casts := 0
	while game.phase == _BattleSim.Phase.DUELING and casts < 12:
		game.advance_time_for_test(5.5)
		if win:
			var pattern: Array = []
			for i in range(pc.weave_size):
				var t := DmbFeedback.target_slot(i, ec.ward_size)
				pattern.append(int(enemy_ward[t]))
			game.load_player_attack(pattern)
		else:
			# deliberately weak: never break; wait for the enemy to solve or exhaust
			var pattern: Array = []
			for i in range(pc.weave_size):
				pattern.append(int(pc.attack_pool[0]))
			game.load_player_attack(pattern)
			if pc.attack_pool.size() == 1 and ec.ward_pool.size() == 1:
				# unwinnable-to-lose case: can't avoid winning; let it be
				pass
		board.ui_action_cast()
		casts += 1
		game.advance_time_for_test(0.5)
		# let the enemy act
		var g := 0
		while game.phase == _BattleSim.Phase.DUELING and g < 200 and game.player_cast_block_reason() != "" and game.player_cast_block_reason().begins_with("Weaving"):
			game.advance_time_for_test(1.0)
			g += 1
		await process_frame
		await process_frame
		await process_frame
	var outcome := ""
	if game.result != null:
		outcome = game.result.outcome
	assert_true(outcome != "", "battle reaches a result")
	board.ui_adventure_continue()  # Continue → reports result to Adventure
	await process_frame
	board.queue_free()
	await process_frame
	return outcome


func _fight_from_world(win: bool) -> String:
	# The overworld requested a battle and changed scene; in this harness we
	# instantiate the board ourselves instead of letting change_scene run.
	var g := 0
	while _adv.pending_battle.is_empty() and g < 120:
		await process_frame
		g += 1
	assert_true(not _adv.pending_battle.is_empty(), "overworld requested a battle")
	await _free_world()
	var outcome := await _fight(win)
	await _new_world()
	await _drain_dialogue()
	return outcome


# ---------------------------------------------------------------------------------

func _test_chapter() -> void:
	_adv.new_game()
	await _new_world()
	await _drain_dialogue()
	assert_eq(_world.area_id, "village", "new game starts in Ashwell")
	assert_eq(_adv.progression.weave_size, 0, "John starts with no magic")
	assert_true(not _adv.progression.has_magic(), "no spells at start")

	# Wander onto the road → wizards' duel cutscene.
	await _walk(Vector2i(0, -1), 1)
	await _walk(Vector2i(1, 0), 2)
	await _walk(Vector2i(0, 1), 1)
	await _walk(Vector2i(-1, 0), 1)
	await _drain_dialogue(60)
	assert_true(_adv.flag("duel_seen"), "wizards duel cutscene ran")
	assert_true(_world.ui_entity_exists("halvard_staff"), "staff placed after cutscene")

	# Take the staff: Water, weave 1.
	await _walk_to(Vector2i(10, 9))
	await _face(Vector2i(0, -1))
	assert_eq(_world.ui_prompt(), "Take", "prompt offers Take for staff")
	await _interact()
	await _drain_dialogue()
	assert_true(_adv.progression.knows(1), "learned Water")
	assert_eq(_adv.progression.weave_size, 1, "weave 1 after staff")
	assert_true(_adv.flag("has_staff"), "staff flag set")

	# Villagers react to the staff.
	await _walk_to(Vector2i(7, 8))
	await _face(Vector2i(0, -1))
	assert_true(_world.ui_prompt().begins_with("Talk"), "Mara prompt")
	await _interact()
	await _drain_dialogue()

	# Ashby lesson 1: fixed Water Ward, guaranteed win.
	await _walk_to(Vector2i(14, 15))
	await _face(Vector2i(0, -1))
	assert_true(_world.ui_prompt().begins_with("Challenge"), "Ashby lesson 1 prompt: %s" % _world.ui_prompt())
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Fight")
	await process_frame
	var out := await _fight_from_world(true)
	assert_eq(out, "victory", "Ashby lesson 1 won")
	assert_true(_adv.flag("beat_lesson1"), "lesson 1 flag set")
	assert_true(_world.ui_entity_exists("ashby_lesson2"), "lesson 2 appears after lesson 1")

	# Ashby lesson 2: Water-or-Fire Ward deduction.
	await _walk_to(Vector2i(15, 15))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Fight")
	await process_frame
	out = await _fight_from_world(true)
	assert_eq(out, "victory", "Ashby lesson 2 won")

	# Save/resume mid-way: reload from disk and verify state.
	_adv.save()
	await _free_world()
	_adv.progression = load("res://sim/progression.gd").new()
	_adv.state = {}
	assert_true(_adv.load_game(), "reload after save")
	assert_true(_adv.progression.knows(1) and _adv.progression.weave_size == 1, "progression survives save/load")
	assert_true(_adv.flag("duel_seen") and _adv.flag("beat_lesson1"), "flags survive save/load")
	await _new_world()
	await _drain_dialogue()

	# South to the Trial road.
	await _walk_to(Vector2i(10, 16))
	await _walk(Vector2i(0, 1), 1)
	var g := 0
	while _world.area_id != "trial_road" and g < 120:
		await process_frame
		g += 1
	assert_eq(_world.area_id, "trial_road", "reached the Trial road")

	# Talk to a traveller, then face the Giant Fly (1-slot, escape allowed).
	await _walk_to(Vector2i(7, 3))
	await _face(Vector2i(0, -1))
	assert_true(_world.ui_prompt().begins_with("Talk"), "traveller prompt")
	await _interact()
	await _drain_dialogue()
	await _walk_to(Vector2i(13, 9))
	await _face(Vector2i(0, -1))
	assert_true(_world.ui_prompt().begins_with("Face"), "fly prompt: %s" % _world.ui_prompt())
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Fight")
	await process_frame
	out = await _fight_from_world(true)
	assert_eq(out, "victory", "Giant Fly beaten")
	assert_true(_adv.marked("defeated", "fly_road1"), "fly marked defeated")

	# East to the Burnt Wood training detour, then back.
	await _walk_to(Vector2i(18, 6))
	await _walk(Vector2i(1, 0), 1)
	g = 0
	while _world.area_id != "forest_deep" and g < 120:
		await process_frame
		g += 1
	assert_eq(_world.area_id, "forest_deep", "Burnt Wood training detour reachable")
	await _walk_to(Vector2i(18, 12))
	await _walk(Vector2i(1, 0), 1)
	g = 0
	while _world.area_id != "trial_road" and g < 120:
		await process_frame
		g += 1
	assert_eq(_world.area_id, "trial_road", "returned from Burnt Wood")

	# North to the Trial gate; the roster is waiting.
	await _walk_to(Vector2i(9, 1))
	await _walk(Vector2i(0, -1), 1)
	g = 0
	while _world.area_id != "trial_gate" and g < 120:
		await process_frame
		g += 1
	assert_eq(_world.area_id, "trial_gate", "reached the Trial gate")
	for cid in ["contest_knight", "contest_elf", "contest_throm", "contest_barb2", "contest_assassin", "contest_red", "gate_official"]:
		assert_true(_world.ui_entity_exists(cid), "roster present: %s" % cid)

	# Approach the doors: NOT YET first — nothing happens, free roam continues.
	await _walk_to(Vector2i(9, 2))
	await _drain_dialogue()
	_world.ui_dialogue_choose("Not yet")
	await process_frame
	await _drain_dialogue()
	assert_true(not _adv.flag("entered_trial"), "NOT YET does not enter")

	# Step away and back: ENTER THE TRIAL → threshold ending.
	await _walk_to(Vector2i(9, 4))
	await _walk_to(Vector2i(9, 2))
	await _drain_dialogue(60)
	_world.ui_dialogue_choose("Enter the Trial")
	await process_frame
	await _drain_dialogue(60)
	assert_true(_adv.flag("entered_trial"), "entered the Trial — chapter complete")

	# Resume after the chapter: state persists.
	_adv.save()
	await _free_world()
	assert_true(_adv.load_game(), "final reload")
	assert_eq(_adv.progression.weave_size, 1, "weave 1 persisted")
	assert_true(_adv.flag("entered_trial"), "entry persisted")
	assert_eq(_adv.state["defeated"].size(), 3, "3 encounters recorded (2 lessons + fly)")


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
		print("ADVENTURE FLOW: ALL PASSED")
		quit(0)
	else:
		print("ADVENTURE FLOW: %d FAILURE(S)" % _failures.size())
		for f in _failures:
			print("  - %s" % f)
		quit(1)
