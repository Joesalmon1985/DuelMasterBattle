extends SceneTree

const _RealtimeSim = preload("res://sim/realtime_duel_sim.gd")

var _failures: Array = []
var _board


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	_test_main_menu_loads()
	await process_frame
	await _test_blue_apprentice_flow()
	await process_frame
	await _test_archmage_duel_flow()
	_report()


func _test_main_menu_loads() -> void:
	var menu_scene: PackedScene = load("res://client/scenes/main_menu.tscn")
	assert_true(menu_scene != null, "main menu scene loads")
	var menu = menu_scene.instantiate()
	root.add_child(menu)
	await process_frame
	assert_true(menu.has_node("Margin/VBox/StartDuelButton"), "Start duel button exists")
	assert_true(menu.has_node("Margin/VBox/EncounterRow/EncounterOption"), "encounter option exists")
	assert_true(menu.has_node("Margin/VBox/DifficultyRow/DifficultyOption"), "difficulty option exists")
	if menu.has_method("ui_has_help_panel"):
		assert_true(menu.ui_has_help_panel(), "main menu help panel exists")
	menu.queue_free()
	await process_frame


func _test_blue_apprentice_flow() -> void:
	var board_scene: PackedScene = load("res://client/scenes/game_board.tscn")
	_board = board_scene.instantiate()
	root.add_child(_board)
	await process_frame

	_board.ui_load_encounter("blue_apprentice")
	await process_frame

	assert_eq(_board.ui_get_slot_count(), 1, "blue apprentice has 1 locus")
	assert_true(_board.ui_has_point_headers(), "locus headers match slot count")
	assert_true(_board.ui_get_visible_history_row_count() <= 3, "history peek collapsed by default")
	assert_true(not _board.ui_is_help_visible(), "help not visible during duel setup")

	_board.ui_action_pick_secret_slot(0)
	_board.ui_action_pick_magic(0)
	await process_frame

	_board.ui_action_lock_secret()
	await process_frame
	assert_true(_board.ui_is_human_turn(), "duel starts in realtime phase")

	_board.ui_action_pick_guess_slot(0)
	await process_frame
	assert_true(_board.ui_is_picker_open(), "picker opens on locus tap")
	var picker_above: bool = _board.ui_get_picker_above_locus()
	assert_true(picker_above or _board.ui_has_essence_tray(), "picker above locus or essence tray available")
	_board.ui_action_pick_magic(0)
	assert_eq(_board.ui_get_visible_magic_count(), 3, "attack picker shows 3 essences")
	assert_true(_board.ui_can_player_cast(), "fast cast test mode allows cast")
	var cast_size: Vector2 = _board.ui_get_cast_button_size()
	assert_true(cast_size.x >= 48 or cast_size.y >= 48, "cast button has touch target")
	_board.ui_action_submit_guess()
	await process_frame
	assert_true(_board.ui_get_cast_button_center_y_ratio() > 0.55, "cast button in thumb zone")
	assert_true(_board.ui_has_essence_tray(), "essence tray visible in duel")
	_board.ui_advance_time(1.0)
	await process_frame

	assert_eq(_board.ui_get_visible_human_guess_count(), 1, "human attack row visible")
	assert_true(_board.ui_get_enemy_tell_visible(), "enemy tell visible")

	_board.queue_free()
	await process_frame


func _test_archmage_duel_flow() -> void:
	var board_scene: PackedScene = load("res://client/scenes/game_board.tscn")
	_board = board_scene.instantiate()
	root.add_child(_board)
	await process_frame

	_board.ui_load_encounter("archmage_duel")
	assert_true(_board.ui_has_wizard_portraits(), "wizard composite hosts exist")
	assert_eq(_board.ui_get_slot_count(), 4, "archmage has 4 loci")

	for i in range(4):
		_board.ui_action_pick_secret_slot(i)
		_board.ui_action_pick_magic(i)
	await process_frame
	_board.ui_action_lock_secret()
	await process_frame

	assert_true(_board.ui_is_human_turn(), "duel starts in realtime phase")

	for s in range(4):
		_board.ui_action_pick_guess_slot(s)
		_board.ui_action_pick_magic(s)
	_board.ui_action_submit_guess()
	await process_frame
	_board.ui_advance_time(2.0)
	await process_frame

	assert_eq(_board.ui_get_visible_human_guess_count(), 1, "human attack feedback row visible")
	var human_fb: String = _board.ui_get_human_feedback_text()
	assert_true(
		"Fracture" in human_fb or "Echo" in human_fb or "Fade" in human_fb,
		"human feedback uses Fracture/Echo/Fade"
	)

	var safety := 0
	while _board.game.phase != _RealtimeSim.Phase.FINISHED and safety < 120:
		if _board.ui_can_player_cast():
			for s in range(4):
				_board.ui_action_pick_guess_slot(s)
				_board.ui_action_pick_magic((s + safety) % DmbConstants.NUM_COLOURS)
			_board.ui_action_submit_guess()
		_board.ui_advance_time(3.0)
		await process_frame
		safety += 1

	assert_true(_board.game.phase == _RealtimeSim.Phase.FINISHED, "reached finished state")
	assert_true(_board.ui_is_result_visible(), "result panel visible")

	_board.ui_action_restart()
	await process_frame
	assert_true(_board.game.phase == _RealtimeSim.Phase.WARD_SETUP, "restart fresh state")
	assert_true(not _board.ui_is_result_visible(), "result hidden after restart")

	_board.queue_free()


func assert_true(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)


func assert_eq(a, b, msg: String) -> void:
	if a != b:
		_failures.append("%s: expected %s got %s" % [msg, str(b), str(a)])


func _report() -> void:
	if _failures.is_empty():
		print("UI SMOKE: ALL PASSED")
		quit(0)
	else:
		print("UI SMOKE: FAILED")
		for f in _failures:
			print("  - %s" % f)
		quit(1)
