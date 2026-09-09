extends SceneTree

## FULL RUN: gate → Fang. One continuous run through every zone with only
## in-dungeon magic (Water from the staff at start; Fire, Stone, Vine, Light,
## Shadow all earned inside). Composed from the per-slice flow tests; this is
## the P6 acceptance test in DEATHTRAP_OVERHAUL_PLAN.md.
##
## godot --headless --path godot_project --script res://client/tests/run_full_run.gd

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
	await _test_full_run()
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


func _drain_dialogue(max_lines: int = 80) -> void:
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
	for i in range(pc.weave_size):
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


func _go_west(expect: String) -> void:
	await _walk_to(Vector2i(1, 7))
	await _walk(Vector2i(-1, 0), 1)
	var g := 0
	while _world.area_id != expect and g < 120:
		await process_frame
		g += 1
	assert_eq(_world.area_id, expect, "travelled west to " + expect)



# ---------------------------------------------------------------------------------

func _test_full_run() -> void:
	# Canonical Trial-entry state (brief §14): Water+Vine+Fire+Stone, weave 3.
	_adv.new_game()
	for ph in ["john_intro", "ashby_training", "pre_trial", "trial"]:
		_adv.advance_phase(ph)
	_adv.set_flag("opening_seen")
	_adv.set_flag("duel_seen")
	_adv.set_flag("has_staff")
	_adv.set_flag("entered_trial")
	_adv.learn_spell(1)
	_adv.learn_spell(6)
	_adv.learn_spell(0)
	_adv.learn_spell(3)
	_adv.grow_weave(3)
	_adv.start_run()
	assert_true(_adv.run_active(), "run active")
	await _new_world()
	await _drain_dialogue()
	var out := ""
	var g := 0
	await _drain_dialogue()
	assert_eq(_world.area_id, "dd_entrance", "the attempt starts at the entrance")
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
	# The torch: Ivy's toll later. Stand above it (row 13 is the pickup row).
	await _walk_to(Vector2i(5, 12))
	await _face(Vector2i(0, 1))
	await _interact()
	await _drain_dialogue()
	assert_true(_adv.run_flag("picked_dd_torch"), "torch taken in the galleries")
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


	# ---- Zone E: Trialmaster (Stone via dice/cobra, forced Throm duel)
	await _drain_dialogue()
	await _walk_to(Vector2i(1, 5))
	await _walk(Vector2i(-1, 0), 1)
	g = 0
	while _world.area_id != "dd_trialmaster" and g < 120:
		await process_frame
		g += 1
	assert_eq(_world.area_id, "dd_trialmaster", "entered the Trialmaster complex")
	await _walk_to(Vector2i(9, 5))
	await _face(Vector2i(0, -1))
	assert_true(_world.ui_prompt().begins_with("Talk"), "dwarf prompt")
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Accept the test")
	await process_frame
	await _drain_dialogue()
	_world.ui_dialogue_choose("More than 8")
	await process_frame
	await _drain_dialogue()
	_world.ui_dialogue_choose("Hold its gaze")
	await process_frame
	await _drain_dialogue()
	assert_true(_adv.run_flag("dwarf_map"), "earned the Dwarf's map (D1)")
	assert_true(_adv.run_flag("trial_ready"), "trial ready after tests")
	assert_true(_world.ui_entity_exists("throm_arena"), "Throm is sent in")
	await _walk_to(Vector2i(4, 8))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Fight")
	await process_frame
	out = await _fight_from_world(true)
	assert_eq(out, "victory", "Throm duel won")
	assert_true(_adv.run_flag("trial_done"), "trial done after the duel")
	assert_eq(str(_adv.run_state()["contestants"].get("throm", "")), "dead", "Throm is dead")

	# ---- Zones C/I: gems
	await _drain_dialogue()

	# West into the idol cavern; two guardians, then the Emerald.
	await _walk_to(Vector2i(1, 8))
	await _walk(Vector2i(-1, 0), 1)
	g = 0
	while _world.area_id != "dd_idol" and g < 120:
		await process_frame
		g += 1
	assert_eq(_world.area_id, "dd_idol", "reached the idol cavern")
	for stand_fight in [[Vector2i(6, 9), "guard_idol1"], [Vector2i(12, 9), "guard_idol2"]]:
		await _walk_to(stand_fight[0])
		await _face(Vector2i(0, -1))
		await _interact()
		await _drain_dialogue()
		_world.ui_dialogue_choose("Fight")
		await process_frame
		out = await _fight_from_world(true)
		assert_eq(out, "victory", "guardian beaten")
		assert_true(_adv.marked("defeated", stand_fight[1]), "guardian recorded")
	await _walk_to(Vector2i(8, 3))
	await _face(Vector2i(0, 1))
	assert_eq(_world.ui_prompt(), "Take", "emerald prompt")
	await _interact()
	await _drain_dialogue()
	assert_true(_adv.has_gem("emerald"), "Emerald taken")
	# The other eye: tempting, wrong.
	await _walk_to(Vector2i(11, 3))
	await _face(Vector2i(0, 1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Take it")
	await process_frame
	await _drain_dialogue()
	assert_true(_adv.run_flag("idol_alarmed"), "false eye alarms the idol")

	# West to the grotto; the Elf first, then the snake.
	await _walk_to(Vector2i(1, 8))
	await _walk(Vector2i(-1, 0), 1)
	g = 0
	while _world.area_id != "dd_grotto" and g < 120:
		await process_frame
		g += 1
	assert_eq(_world.area_id, "dd_grotto", "reached the grotto")
	await _walk_to(Vector2i(9, 9))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Drive it off")
	await process_frame
	await _drain_dialogue()
	await _walk_to(Vector2i(10, 7))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Fight")
	await process_frame
	out = await _fight_from_world(true)
	assert_eq(out, "victory", "boa beaten")
	await _walk_to(Vector2i(9, 9))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Stay with her")
	await process_frame
	await _drain_dialogue()
	assert_true(_adv.flag("diamond_clue"), "diamond clue learned")
	# Bread heals the false-eye wound; charm teaches Vine.
	await _walk_to(Vector2i(8, 8))
	await _face(Vector2i(0, 1))
	await _interact()
	await _drain_dialogue()
	assert_true(not ("wounded" in _adv.run_state().get("conditions", [])), "bread heals")
	await _walk_to(Vector2i(11, 8))
	await _face(Vector2i(0, 1))
	await _interact()
	await _drain_dialogue()
	assert_true(_adv.run_flag("has_elf_charm"), "took the elf's charm (D1)")
	assert_eq(_adv.progression.weave_size, 4, "weave 4 (from the red book) still held")

	# West to the vaults; sapphire, iron key, real diamond, false diamond refused.
	await _walk_to(Vector2i(1, 7))
	await _walk(Vector2i(-1, 0), 1)
	g = 0
	while _world.area_id != "dd_vaults" and g < 120:
		await process_frame
		g += 1
	assert_eq(_world.area_id, "dd_vaults", "reached the vaults")
	await _walk_to(Vector2i(9, 3))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	assert_true(_adv.has_gem("sapphire"), "Sapphire taken")
	assert_true(_adv.run_flag("iron_key"), "iron key found with the Sapphire")
	await _walk_to(Vector2i(11, 2))
	await _walk(Vector2i(0, -1), 1)
	g = 0
	while _world.area_id != "dd_vault_inner" and g < 120:
		await process_frame
		g += 1
	assert_eq(_world.area_id, "dd_vault_inner", "iron key opens the inner vault")
	await _walk_to(Vector2i(7, 5))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	assert_true(_adv.has_gem("diamond"), "Diamond taken")
	await _walk_to(Vector2i(6, 7))
	await _walk(Vector2i(0, 1), 1)
	g = 0
	while _world.area_id != "dd_vaults" and g < 120:
		await process_frame
		g += 1
	await _walk_to(Vector2i(14, 11))
	await _face(Vector2i(0, 1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Leave it")
	await process_frame
	await _drain_dialogue()
	assert_true(not ("wounded" in _adv.run_state().get("conditions", [])), "false diamond refused safely")
	assert_true(_adv.has_gem("emerald") and _adv.has_gem("sapphire") and _adv.has_gem("diamond"), "all three gems held")

	# Journal from the pause menu.
	_world._on_menu()
	await process_frame
	await _drain_dialogue()
	_world.ui_dialogue_choose("Journal")
	await process_frame
	await _drain_dialogue()
	_world.ui_dialogue_choose("Continue")
	await process_frame
	await _drain_dialogue()
	assert_true("Emerald" in _adv.notebook_text(), "journal lists the Emerald")
	assert_true("diamond" in _adv.notebook_text(), "journal keeps the diamond clue")

	# ---- Zones H/G/F: pacifist galleries
	await _drain_dialogue()

	# Service layer: free the prisoner (weakness clue), pay Ivy with the torch.
	await _go_west("dd_service")
	await _walk_to(Vector2i(6, 7))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Free him")
	await process_frame
	await _drain_dialogue()
	assert_true(_adv.run_flag("blood_weakness"), "prisoner gives the weakness")
	await _walk_to(Vector2i(12, 7))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Offer the torch")
	await process_frame
	await _drain_dialogue()
	assert_true(_adv.run_flag("ivy_paid"), "Ivy takes the torch")

	# Mirror gallery: smash the mirrors, take the Light.
	await _go_west("dd_mirror")
	await _walk_to(Vector2i(10, 5))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Smash them")
	await process_frame
	await _drain_dialogue()
	assert_true(_adv.marked("defeated", "demon_mirror1"), "smashing defeats the demon")
	await _walk_to(Vector2i(10, 3))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	assert_true(_adv.progression.knows(4), "learned Light from the shard")

	# Bloodbeast: weakness rides in, Shadow comes out.
	await _go_west("dd_blood")
	await _walk_to(Vector2i(12, 8))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Fight")
	await process_frame
	var w := 0
	while _adv.pending_battle.is_empty() and w < 120:
		await process_frame
		w += 1
	assert_true(_adv.pending_battle.get("ward_ban", []).has(6), "Vine banned from the beast's Ward")
	out = await _fight_from_world(true)
	assert_eq(out, "victory", "bloodbeast beaten")
	assert_true(_adv.progression.knows(5), "learned Shadow after the beast")

	# Grub gallery: duel, boulder run, trapped chest.
	await _go_west("dd_grub")
	await _walk_to(Vector2i(10, 8))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Fight")
	await process_frame
	out = await _fight_from_world(true)
	assert_eq(out, "victory", "rock grub beaten")
	await _walk_to(Vector2i(10, 6))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Run!")
	await process_frame
	await _drain_dialogue()
	assert_true(not ("wounded" in _adv.run_state().get("conditions", [])), "outran the boulder")
	await _walk_to(Vector2i(15, 9))
	await _face(Vector2i(0, 1))
	await _interact()
	await _drain_dialogue()
	assert_true(_world.ui_dialogue_waiting_choice(), "chest offers a choice")
	_world.ui_dialogue_choose("Jam the lid with Stone")
	await process_frame
	await _drain_dialogue()
	assert_true(_adv.run_flag("chest_gold"), "Stone jams the trap: gold, no wound")
	assert_true(not ("wounded" in _adv.run_state().get("conditions", [])), "chest opened safely with Stone")

	# Troglodytes: join the ritual, no duel needed.
	await _go_west("dd_troglodytes")
	await _walk_to(Vector2i(10, 6))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Join the ritual")
	await process_frame
	await _drain_dialogue()
	assert_true(_adv.run_flag("trog_rite"), "ritual accepted")

	# ---- Zones J/K: finale
	await _drain_dialogue()
	await _go_west("dd_manticore")

	# Optional: settle it with the Red Wizard first.
	await _walk_to(Vector2i(14, 9))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Fight")
	await process_frame
	out = await _fight_from_world(true)
	assert_eq(out, "victory", "Red Wizard beaten")

	# The Manticore: last creature gate.
	await _walk_to(Vector2i(10, 7))
	await _face(Vector2i(0, -1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Fight")
	await process_frame
	out = await _fight_from_world(true)
	assert_eq(out, "victory", "manticore beaten")

	# Igbut: wrong order wounds, right order opens.
	await _go_west("dd_igbut")
	await _walk_to(Vector2i(8, 5))
	await _face(Vector2i(0, 1))
	await _interact()
	await _drain_dialogue()
	_world.ui_dialogue_choose("Face the door")
	await process_frame
	await _drain_dialogue()
	_world.ui_dialogue_choose("Emerald, Sapphire, Diamond")
	await process_frame
	await _drain_dialogue()
	assert_true("wounded" in _adv.run_state().get("conditions", []), "wrong order blasts")
	_world.ui_dialogue_choose("Sapphire, Emerald, Diamond")
	await process_frame
	await _drain_dialogue(80)
	assert_true(_adv.flag("dungeon_complete"), "Champion of the Trial")
	assert_eq(_world.area_id, "trial_gate", "emerged at the gate")

	assert_true(_adv.progression.knows(4) and _adv.progression.knows(5), "Light and Shadow earned inside the Trial")
	assert_eq(_adv.progression.weave_size, 4, "fourth weave slot earned inside the Trial")
	assert_eq(_adv.progression.spells_known.size(), 6, "six kinds of magic by the end")
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
		print("FULL RUN: ALL PASSED")
		quit(0)
	else:
		print("FULL RUN: %d FAILURE(S)" % _failures.size())
		for f in _failures:
			print("  - %s" % f)
		quit(1)
