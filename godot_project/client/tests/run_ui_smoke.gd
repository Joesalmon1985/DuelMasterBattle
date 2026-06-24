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
	menu.queue_free()
	await process_frame


func _test_full_human_vs_bot_flow() -> void:
	var board_scene: PackedScene = load("res://client/scenes/game_board.tscn")
	_board = board_scene.instantiate()
	root.add_child(_board)
	await process_frame

	# Secret setup: click slot opens picker, pick magic fills slot
	assert_false(_board.ui_get_lock_button_enabled(), "lock disabled before pegs")
	_board.ui_action_pick_secret_slot(0)
	assert_true(_board.ui_is_picker_open(), "picker opens on secret slot click")
	_board.ui_action_pick_magic(0)
	assert_eq(_board.ui_get_secret_slot_value(0), 0, "secret slot 0 filled")
	_board.ui_action_pick_secret_slot(1)
	assert_true(_board.ui_is_picker_open(), "picker opens on secret slot 1")
	_board.ui_action_pick_magic(1)
	_board.ui_action_pick_secret_slot(2)
	_board.ui_action_pick_magic(2)
	_board.ui_action_pick_secret_slot(3)
	_board.ui_action_pick_magic(3)
	await process_frame
	assert_true(_board.ui_get_lock_button_enabled(), "lock enabled after 4 pegs")

	_board.ui_action_lock_secret()
	await _wait_bot_phase_done()
	assert_true(_board.ui_secret_is_hidden(), "secret hidden after lock")
	assert_true(_board.ui_get_visible_bot_guess_count() > 0, "bot made guesses")
	var bot_count := _board.ui_get_visible_bot_guess_count()
	assert_true(bot_count <= DmbConstants.MAX_GUESSES, "bot stopped within 12")
	assert_true(_board.ui_get_bot_feedback_count() == bot_count, "feedback per bot guess")
	var fb_text := _board.ui_get_bot_feedback_text()
	assert_true("Hit:" in fb_text or "Weakness:" in fb_text, "feedback uses Hit/Weakness wording")

	assert_true(_board.ui_get_human_guess_row_active(), "human guess row active")

	var safety := 0
	while _board.game.phase != DmbSequentialDuelGame.GamePhase.FINISHED and safety < 12:
		for s in range(4):
			_board.ui_action_pick_guess_slot(s)
			assert_true(_board.ui_is_picker_open(), "picker opens on guess slot click")
			_board.ui_action_pick_magic((s + safety) % DmbConstants.NUM_COLOURS)
			assert_true(_board.ui_get_guess_slot_value(s) >= 0, "guess slot filled")
		_board.ui_action_submit_guess()
		await process_frame
		safety += 1

	assert_true(_board.game.phase == DmbSequentialDuelGame.GamePhase.FINISHED, "reached finished state")
	assert_true(_board.ui_is_result_visible(), "result panel visible")

	_board.ui_action_restart()
	await process_frame
	assert_true(_board.game.phase == DmbSequentialDuelGame.GamePhase.HUMAN_SETUP, "restart fresh state")
	assert_false(_board.ui_is_result_visible(), "result hidden after restart")
	assert_eq(_board.ui_get_visible_bot_guess_count(), 0, "bot board cleared")

	_board.queue_free()


func _wait_bot_phase_done() -> void:
	var safety := 0
	while _board.game.phase == DmbSequentialDuelGame.GamePhase.BOT_GUESSING and safety < 30:
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
