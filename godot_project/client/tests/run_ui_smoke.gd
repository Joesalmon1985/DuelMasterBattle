extends SceneTree

var _failures: Array = []
var _board: GameBoard


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	_test_main_menu_loads()
	await process_frame
	await _test_full_human_vs_bot_flow()
	_report()


func _test_main_menu_loads() -> void:
	var menu_scene: PackedScene = load("res://client/scenes/main_menu.tscn")
	assert_true(menu_scene != null, "main menu scene loads")
	var menu = menu_scene.instantiate()
	root.add_child(menu)
	await process_frame
	assert_true(menu.has_node("VBox/HumanVsBotButton"), "Human vs Bot button exists")
	if menu.has_method("ui_has_help_panel"):
		assert_true(menu.ui_has_help_panel(), "main menu help panel exists")
	menu.queue_free()
	await process_frame


func _test_full_human_vs_bot_flow() -> void:
	var board_scene: PackedScene = load("res://client/scenes/game_board.tscn")
	_board = board_scene.instantiate()
	root.add_child(_board)
	await process_frame

	_board.ui_set_bot_pacing(0.0)
	assert_true(_board.ui_has_wizard_portraits(), "wizard portrait textures loaded")
	assert_true(_board.ui_has_point_headers(), "help panel buttons exist")

	for i in range(4):
		_board.ui_action_pick_secret_slot(i)
		_board.ui_action_pick_magic(i)
	await process_frame
	_board.ui_action_lock_secret()
	await process_frame

	assert_true(_board.ui_is_human_turn(), "duel starts on human turn")
	assert_false(_board.ui_is_bot_turn(), "not bulk bot phase after lock")
	assert_eq(_board.ui_get_visible_bot_guess_count(), 0, "no bot rows before first bot turn")

	for s in range(4):
		_board.ui_action_pick_guess_slot(s)
		_board.ui_action_pick_magic(s)
	_board.ui_action_submit_guess()
	await process_frame
	await _wait_bot_turn_done()

	assert_eq(_board.ui_get_visible_human_guess_count(), 1, "human attack feedback row visible")
	var human_fb := _board.ui_get_human_feedback_text()
	assert_true(
		"Hit:" in human_fb or "Weakness:" in human_fb or "Unaffected:" in human_fb,
		"human feedback uses Hit/Weakness/Unaffected"
	)

	var bot_after := _board.ui_get_visible_bot_guess_count()
	assert_eq(bot_after, 1, "bot makes exactly one visible attack")

	if _board.game.phase != DmbSequentialDuelGame.GamePhase.FINISHED:
		assert_true(_board.ui_is_human_turn(), "turn returns to human after bot attack")

		for s in range(4):
			_board.ui_action_pick_guess_slot(s)
			_board.ui_action_pick_magic((s + 1) % DmbConstants.NUM_COLOURS)
		_board.ui_action_submit_guess()
		await process_frame
		assert_eq(_board.ui_get_visible_human_guess_count(), 2, "second human feedback row visible")

	var safety := 0
	while _board.game.phase != DmbSequentialDuelGame.GamePhase.FINISHED and safety < 24:
		if _board.ui_is_human_turn():
			for s in range(4):
				_board.ui_action_pick_guess_slot(s)
				_board.ui_action_pick_magic((s + safety + 2) % DmbConstants.NUM_COLOURS)
			_board.ui_action_submit_guess()
			await process_frame
			if _board.game.phase == DmbSequentialDuelGame.GamePhase.BOT_TURN:
				await _wait_bot_turn_done()
		elif _board.ui_is_bot_turn():
			await _wait_bot_turn_done()
		safety += 1

	assert_true(_board.game.phase == DmbSequentialDuelGame.GamePhase.FINISHED, "reached finished state")
	assert_true(_board.ui_is_result_visible(), "result panel visible")

	_board.ui_action_restart()
	await process_frame
	assert_true(_board.game.phase == DmbSequentialDuelGame.GamePhase.HUMAN_SETUP, "restart fresh state")
	assert_false(_board.ui_is_result_visible(), "result hidden after restart")
	assert_eq(_board.ui_get_visible_bot_guess_count(), 0, "bot board cleared")
	assert_eq(_board.ui_get_visible_human_guess_count(), 0, "human board cleared")

	_board.queue_free()


func _wait_bot_turn_done() -> void:
	var safety := 0
	while _board.ui_is_bot_turn() and safety < 30:
		await process_frame
		safety += 1
	await process_frame


func assert_true(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)


func assert_false(cond: bool, msg: String) -> void:
	assert_true(not cond, msg)


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
