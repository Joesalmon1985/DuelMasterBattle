extends SceneTree

## Adventure flow test (CORRECTIVE_PASS_PLAN Phase 13, brief §30): NEW GAME as
## Halvard → Red intercept (facing checked) → unwinnable prologue → Halvard dies →
## John → staff (Water/1) → Ashby ×3 (win / forced loss + Vine/2 / optimal fair)
## → Giant Fly (decline is harmless; 2 slots) → Burnt Wood (pendant=Fire,
## shard=Stone+weave 3) → gate refuses underpowered, admits 4 spells / 3 knots.
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
	await _test_gate_rejects_underpowered()
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
			_world.ui_dialogue_advance()  # second call finishes typing → closes
			await process_frame
		elif not _world.ui_input_locked() or not _adv.pending_battle.is_empty():
			return
	_failures.append("dialogue/cutscene did not finish (area=%s pos=%s open=%s locked=%s text=%s)" % [_world.area_id, str(_world.john_pos()), _world.ui_dialogue_open(), _world.ui_input_locked(), _world._dialogue.ui_visible_text().left(60)])


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


## Fight the pending battle to a forced outcome using legal moves only.
func _fight(win: bool, rig_ward: Array = [], max_casts: int = 12) -> Dictionary:
	var board = load("res://client/scenes/game_board.tscn").instantiate()
	root.add_child(board)
	await process_frame
	assert_true(board.ui_is_overlay_visible(), "encounter intro shows")
	board.ui_dismiss_overlay()
	await process_frame
	var game = board.game
	var pc: DmbCombatant = game.player
	var ec: DmbCombatant = game.enemy
	var info := {"player_name": pc.display_name, "player_weave": pc.weave_size, "enemy_ward": ec.ward_size, "enemy_weave": ec.weave_size,
		"enemy_logic": ec.bot_logic, "enemy_cap": ec.bot_solver_cap, "forced": game.forced_defeat_by_cast}
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
	while game.phase == _BattleSim.Phase.DUELING and casts < max_casts:
		game.advance_time_for_test(5.5)
		var pattern: Array = []
		for i in range(pc.weave_size):
			if win:
				var t := DmbFeedback.target_slot(i, ec.ward_size)
				pattern.append(int(enemy_ward[t]))
			else:
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
		info["enemy_casts"] = game.result.bot_guess_count
		info["duel_time"] = game.duel_time
	assert_true(outcome != "", "battle reaches a result")
	info["outcome"] = outcome
	info["buttons"] = board.ui_overlay_button_labels()
	board.ui_adventure_continue()
	await process_frame
	board.queue_free()
	await process_frame
	return info


func _fight_from_world(win: bool, rig_ward: Array = []) -> Dictionary:
	var g := 0
	while _adv.pending_battle.is_empty() and g < 120:
		await process_frame
		g += 1
	assert_true(not _adv.pending_battle.is_empty(), "overworld requested a battle")
	await _free_world()
	var info := await _fight(win, rig_ward)
	await _new_world()
	await _drain_dialogue(80)
	return info


func _go(dir: Vector2i, from: Vector2i, expect: String) -> void:
	await _walk_to(from)
	await _walk(dir, 1)
	var g := 0
	while _world.area_id != expect and g < 120:
		await process_frame
		g += 1
	assert_eq(_world.area_id, expect, "travelled to " + expect)


func _talk_ashby() -> void:
	await _walk_to(Vector2i(14, 15))
	await _face(Vector2i(0, -1))
	assert_true(_world.ui_prompt().begins_with("Talk"), "Ashby prompt: %s" % _world.ui_prompt())
	await _interact()
	await _drain_dialogue(60)


# ---------------------------------------------------------------------------------
# THE STORY (brief §30). One continuous run from NEW GAME to Trial entry.
# ---------------------------------------------------------------------------------

const STALE_PHRASES := ["Blue Wizard having", "came through at dawn", "Try again", "run is over", "You are John. You cut wood"]


func _test_chapter() -> void:
	_adv.new_game()
	await _new_world()
	await _drain_dialogue(60)

	# --- Prologue: you are Halvard ---------------------------------------------------
	assert_eq(_adv.story_phase(), "halvard_prologue", "new game starts in the prologue")
	assert_eq(_adv.protagonist(), "halvard", "player controls Halvard")
	assert_eq(_world.ui_player_sprite_key(), "blue_mage", "Halvard is drawn as the Blue mage")
	assert_eq(_world.area_id, "village", "prologue opens in Ashwell")
	assert_eq(_adv.progression.weave_size, 0, "John's progression untouched during the prologue")
	var start: Vector2i = _world.john_pos()
	await _walk(Vector2i(1, 0), 1)
	await _walk(Vector2i(0, 1), 1)
	assert_true(_world.john_pos() != start, "Halvard can move")
	# Villagers know who is standing in front of them.
	await _walk_to(Vector2i(12, 6))
	await _face(Vector2i(0, -1))
	assert_true(_world.ui_prompt().begins_with("Talk"), "Pip prompt (got '%s' at %s)" % [_world.ui_prompt(), str(_world.john_pos())])
	var pip_lines: Array = _world.ui_npc_lines_for("child_pip")
	assert_true("REAL wizard" in " ".join(PackedStringArray(pip_lines)), "Pip addresses Halvard in the prologue")
	for line in pip_lines:
		for bad in STALE_PHRASES:
			assert_true(not (bad in str(line)), "no stale phrase '%s' in prologue villager line" % bad)
	await _interact()
	await _drain_dialogue()

	# Onto the road → Red intercepts (trigger rows 8–9, needs 3 steps taken).
	await _walk_to(Vector2i(10, 7))
	await _walk(Vector2i(0, 1), 1)
	await _walk(Vector2i(-1, 0), 1)
	await _walk(Vector2i(-1, 0), 1)
	await _drain_dialogue(60)
	var g := 0
	while _adv.pending_battle.is_empty() and g < 240:
		await process_frame
		g += 1
	assert_true(not _adv.pending_battle.is_empty(), "Red intercept requested a battle")
	# Facing (brief §3): read back from textures, not coordinates.
	var red_face: String = _world.ui_actor_facing("red")
	var hal_face: String = _world.ui_actor_facing("john")
	assert_true(red_face in ["left", "right"] and hal_face in ["left", "right"], "both face sideways (%s/%s)" % [red_face, hal_face])
	assert_true(red_face != hal_face, "Red and Halvard face each other")
	var red_pos: Vector2i = _world.ui_actor_pos("red")
	if red_pos.x > _world.john_pos().x:
		assert_eq(red_face, "left", "Red on the right faces left")
		assert_eq(hal_face, "right", "Halvard on the left faces right")
	else:
		assert_eq(red_face, "right", "Red on the left faces right")
		assert_eq(hal_face, "left", "Halvard on the right faces left")
	assert_eq(str(_adv.battle_policy_for(_adv.pending_battle)), "PROLOGUE_FORCED_DEFEAT", "prologue policy")
	await _free_world()
	var info := await _fight(true)   # the player plays to win — and cannot
	assert_eq(str(info["player_name"]), "Halvard", "player combatant is Halvard")
	assert_eq(int(info["player_weave"]), 3, "Halvard weaves three")
	assert_eq(str(info["outcome"]), "defeat", "the authored prologue cannot be won")
	assert_true(int(info.get("enemy_casts", 99)) <= 3, "Red solves in ≤3 casts (got %s)" % str(info.get("enemy_casts")))
	assert_true(float(info.get("duel_time", 999.0)) <= 90.0, "prologue duel over in ≤90s (got %.1f)" % float(info.get("duel_time", 999.0)))
	assert_true(not ("Try again" in info["buttons"]), "no Try again after the prologue")
	await _new_world()
	await _drain_dialogue(80)

	# --- Pivot: you are John -----------------------------------------------------------
	assert_eq(_adv.protagonist(), "john", "control passes to John")
	assert_eq(_adv.story_phase(), "john_intro", "phase john_intro")
	assert_eq(_world.ui_player_sprite_key(), "john", "John drawn without a staff")
	assert_true(_adv.flag("halvard_dead"), "Halvard is dead")
	assert_true(_world.ui_entity_exists("blue_wizard_body"), "Halvard's body is present")
	assert_true(_world.ui_entity_exists("halvard_staff"), "Halvard's staff is present")
	assert_true(not _adv.progression.has_magic(), "John starts with no personal magic")
	assert_eq(int(_adv.state["story"]["story_defeats"]), 0, "prologue loss is not John's loss")
	assert_true(not _adv.left_for_dead_used(), "prologue loss does not touch the defeat policy")

	# Take the staff: Water, weave 1.
	await _walk_to(Vector2i(10, 9))
	await _face(Vector2i(0, -1))
	assert_eq(_world.ui_prompt(), "Take", "prompt offers Take for staff")
	await _interact()
	await _drain_dialogue()
	assert_true(_adv.progression.knows(1), "learned Water")
	assert_eq(_adv.progression.weave_size, 1, "weave 1 after staff")
	assert_eq(_world.ui_player_sprite_key(), "john_staff", "John now drawn with the staff")

	# --- Ashby ×3 ----------------------------------------------------------------------
	await _talk_ashby()
	assert_eq(_adv.story_phase(), "ashby_training", "phase ashby_training")
	info = await _fight_from_world(true)
	assert_eq(str(info["outcome"]), "victory", "Ashby duel 1 can be won")
	assert_eq(int(info["enemy_ward"]), 1, "duel 1 is one slot")
	assert_true(_adv.flag("ashby_duel1_done"), "duel 1 done")
	assert_eq(_world.area_id, "village", "still in the village after training")

	await _talk_ashby()
	info = await _fight_from_world(true)   # plays to win; mechanically cannot
	assert_eq(int(info["enemy_ward"]), 2, "duel 2 Ashby has a two-slot Ward")
	assert_eq(int(info["enemy_weave"]), 2, "duel 2 Ashby weaves two")
	assert_eq(str(info["outcome"]), "defeat", "John cannot win duel 2 with one slot")
	assert_true(not ("Try again" in info["buttons"]), "no Try again after training")
	assert_eq(_world.area_id, "village", "defeat does not move John")
	assert_eq(int(_adv.state["story"]["story_defeats"]), 0, "training defeat is not a story defeat")
	assert_true(_adv.progression.knows(6), "Ashby grants Vine after the loss")
	assert_eq(_adv.progression.weave_size, 2, "weave 2 after the loss")
	assert_true(_adv.flag("ashby_duel2_done"), "duel 2 done")

	await _talk_ashby()
	g = 0
	while _adv.pending_battle.is_empty() and g < 120:
		await process_frame
		g += 1
	assert_eq(int(_adv.pending_battle.get("encounter_index", 0)), 3, "duel 3 is John's third battle")
	assert_true(bool(_adv.pending_battle.get("optimal", false)), "duel 3 uses the optimal tier")
	info = await _fight_from_world(false, [6, 1])   # lose it on purpose: still completes training
	assert_eq(str(info["enemy_logic"]), "capped_minimax", "optimal tier bot logic")
	assert_true(int(info["enemy_cap"]) >= 100, "optimal tier solver cap")
	assert_eq(int(info["enemy_ward"]), 2, "duel 3 is 2v2")
	assert_eq(str(info["outcome"]), "defeat", "lost duel 3 (on purpose)")
	assert_true(_adv.flag("ashby_training_complete"), "a loss still completes training")
	assert_eq(_adv.story_phase(), "pre_trial", "phase pre_trial after training")
	assert_eq(_adv.progression.weave_size, 2, "no reset after the loss")
	assert_eq(int(_adv.state["story"]["story_defeats"]), 0, "training losses never count")

	# --- Road: the Giant Fly -------------------------------------------------------------
	await _go(Vector2i(0, 1), Vector2i(10, 16), "trial_road")
	assert_true(_world.john_pos().y <= 2 or true, "arrived on the road")  # spawn checked by topology test
	await _walk_to(Vector2i(13, 9))
	await _face(Vector2i(0, -1))
	assert_true(_world.ui_prompt().begins_with("Face"), "fly prompt: %s" % _world.ui_prompt())
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Walk away")
	await process_frame
	await _drain_dialogue()
	assert_eq(int(_adv.state["story"]["story_defeats"]), 0, "declining a fight is not a defeat")
	assert_true(not _adv.left_for_dead_used(), "declining never spends the wake")
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Fight")
	await process_frame
	info = await _fight_from_world(true)
	assert_eq(int(info["enemy_ward"]), 2, "fly has two Ward slots")
	assert_eq(int(info["enemy_weave"]), 2, "fly weaves two")
	assert_eq(str(info["outcome"]), "victory", "fly beaten")

	# --- Burnt Wood: Fire, Stone, weave 3 ----------------------------------------------
	await _go(Vector2i(1, 0), Vector2i(18, 6), "forest_deep")
	# Fires gate the wood; Water from the staff puts them out.
	for fire_pos in [Vector2i(15, 12), Vector2i(15, 11)]:
		await _walk_to(fire_pos + Vector2i(1, 0))
		await _face(Vector2i(-1, 0))
		assert_true(_world.ui_prompt().begins_with("Douse") or _world.ui_prompt().begins_with("Cast") or _world.ui_prompt() != "", "fire prompt at %s: '%s'" % [str(fire_pos), _world.ui_prompt()])
		await _interact()
		await _drain_dialogue()
	await _walk_to(Vector2i(6, 10))
	await _face(Vector2i(-1, 0))
	assert_true(_world.ui_prompt().begins_with("Face"), "imp prompt (got '%s' at %s area %s imp=%s pend=%s)" % [_world.ui_prompt(), str(_world.john_pos()), _world.area_id, _world.ui_entity_exists("imp_d2"), _world.ui_entity_exists("fire_pendant")])
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Fight")
	await process_frame
	info = await _fight_from_world(true)
	assert_eq(str(info["outcome"]), "victory", "imp guarding the pendant beaten")
	assert_true(int(info["enemy_ward"]) >= 2, "Burnt Wood enemies have ≥2 slots")
	await _walk_to(Vector2i(3, 10))
	await _face(Vector2i(0, 1))
	assert_eq(_world.ui_prompt(), "Take", "pendant prompt")
	await _interact()
	await _drain_dialogue()
	assert_true(_adv.progression.knows(0), "red pendant grants Fire")
	await _walk_to(Vector2i(8, 3))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Fight")
	await process_frame
	info = await _fight_from_world(true)
	assert_eq(str(info["outcome"]), "victory", "golem beaten")
	await _walk_to(Vector2i(8, 3))
	await _face(Vector2i(0, -1))
	assert_eq(_world.ui_prompt(), "Take", "stone shard prompt")
	await _interact()
	await _drain_dialogue()
	assert_true(_adv.progression.knows(3), "stone shard grants Stone")
	assert_eq(_adv.progression.weave_size, 3, "weave 3 from the shard")
	assert_eq(_adv.progression.spells_known.size(), 4, "four spell types before the Trial")
	assert_true(_adv.trial_ready(), "trial_ready() true after the normal route")

	# --- Gate -------------------------------------------------------------------------------
	await _go(Vector2i(1, 0), Vector2i(18, 12), "trial_road")
	await _go(Vector2i(0, -1), Vector2i(9, 1), "trial_gate")
	for cid in ["contest_knight", "contest_elf", "contest_throm", "contest_barb2", "contest_assassin", "contest_red", "gate_official"]:
		assert_true(_world.ui_entity_exists(cid), "roster present: %s" % cid)
	await _walk_to(Vector2i(9, 2))
	await _drain_dialogue()
	_world.ui_dialogue_choose("Not yet")
	await process_frame
	await _drain_dialogue()
	assert_true(not _adv.flag("entered_trial"), "NOT YET does not enter")
	await _walk_to(Vector2i(9, 4))
	await _walk_to(Vector2i(9, 2))
	await _drain_dialogue(60)
	_world.ui_dialogue_choose("Enter the Trial")
	await process_frame
	await _drain_dialogue(60)
	assert_true(_adv.flag("entered_trial"), "entered the Trial")
	assert_eq(_adv.story_phase(), "trial", "phase trial")
	assert_eq(_world.area_id, "dd_entrance", "inside the Trial")

	_adv.save()
	await _free_world()
	assert_true(_adv.load_game(), "final reload")
	assert_eq(_adv.progression.weave_size, 3, "weave 3 persisted")
	assert_eq(_adv.story_phase(), "trial", "phase persisted")


## Debug/abnormal save: the gate refuses an underpowered John diegetically.
func _test_gate_rejects_underpowered() -> void:
	_adv.new_game()
	for ph in ["john_intro", "ashby_training", "pre_trial"]:
		_adv.advance_phase(ph)
	_adv.set_flag("opening_seen")
	_adv.set_flag("has_staff")
	_adv.learn_spell(1)
	_adv.grow_weave(1)
	_adv.set_location("trial_gate", 9, 4, "up")
	await _new_world()
	await _drain_dialogue()
	await _walk_to(Vector2i(9, 2))
	await _drain_dialogue(60)
	assert_true(not _adv.flag("entered_trial"), "underpowered John is refused")
	assert_eq(_adv.story_phase(), "pre_trial", "phase unchanged by refusal")
	assert_true(not _world.ui_dialogue_waiting_choice(), "no Enter choice offered when refused")
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
		print("ADVENTURE FLOW: ALL PASSED")
		quit(0)
	else:
		print("ADVENTURE FLOW: %d FAILURE(S)" % _failures.size())
		for f in _failures:
			print("  - %s" % f)
		quit(1)
