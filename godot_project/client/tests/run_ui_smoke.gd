extends SceneTree

## Headless UI smoke test: drives the real GameBoard through a full duel using
## the ui_* API and checks the screen tells the truth at each step.

const _RealtimeSim = preload("res://sim/realtime_duel_sim.gd")
const _CastButton = preload("res://client/components/cast_button.gd")

var _failures: Array = []
var _board


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	_ensure_autoloads()
	await process_frame
	await _test_main_menu()
	await process_frame
	await _test_full_duel_flow()
	await process_frame
	await _test_timer_states_and_auto_cast()
	await process_frame
	await _test_play_again_resets()
	_report()


func _ensure_autoloads() -> void:
	if root.get_node_or_null("EncounterSession") == null:
		var s = load("res://client/scripts/encounter_session.gd").new()
		s.name = "EncounterSession"
		root.add_child(s)
	if root.get_node_or_null("Sfx") == null:
		var s2 = load("res://client/scripts/sfx.gd").new()
		s2.name = "Sfx"
		root.add_child(s2)
	if root.get_node_or_null("Adventure") == null:
		var s3 = load("res://client/scripts/adventure.gd").new()
		s3.name = "Adventure"
		root.add_child(s3)


func _new_board():
	var scene: PackedScene = load("res://client/scenes/game_board.tscn")
	var b = scene.instantiate()
	root.add_child(b)
	if not b.has_method("ui_get_phase"):
		_failures.append("game_board.gd failed to load (parse error)")
		_report()
	return b


func _test_main_menu() -> void:
	var menu = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(menu)
	await process_frame
	assert_true(menu.ui_has_help_panel(), "menu builds")
	menu.ui_action_select_difficulty("hard")
	assert_eq(menu.ui_get_selected_difficulty(), "hard", "difficulty selectable")
	menu.ui_show_help()
	assert_true(menu.ui_is_overlay_visible(), "help overlay opens")
	menu.queue_free()
	await process_frame
	root.get_node("EncounterSession").set_difficulty("medium")


func _test_full_duel_flow() -> void:
	_board = _new_board()
	await process_frame
	if _board.ui_is_overlay_visible():
		_board.ui_dismiss_overlay()
	assert_eq(_board.ui_get_phase(), _RealtimeSim.Phase.WARD_SETUP, "starts in ward setup")
	assert_eq(_board.ui_get_tray_count(), 6, "six spells in tray")
	assert_eq(_board.ui_get_selected_locus(), 0, "first locus selected by default")

	# Build a ward by tapping spells: selection should auto-advance.
	_board.ui_action_pick_spell(0)
	assert_eq(_board.ui_get_selected_locus(), 1, "selection advances after placing")
	_board.ui_action_pick_spell(1)
	_board.ui_action_pick_spell(3)
	assert_true(not _board.game.can_lock_player_ward(), "cannot lock with 3 of 4")
	_board.ui_action_lock_ward()
	assert_eq(_board.ui_get_phase(), _RealtimeSim.Phase.WARD_SETUP, "lock refused when incomplete")
	_board.ui_action_pick_spell(4)
	assert_eq(_board.ui_get_locus_values(), [0, 1, 3, 4], "ward shows chosen spells")
	# Tap selected filled locus twice to clear it, then refill.
	_board.ui_action_select_locus(2)
	_board.ui_action_select_locus(2)
	assert_eq(_board.ui_get_locus_values()[2], -1, "double tap clears a locus")
	_board.ui_action_pick_spell(9)
	assert_eq(_board.ui_get_locus_values(), [0, 1, 9, 4], "refilled locus")
	_board.ui_action_lock_ward()
	await process_frame
	assert_eq(_board.ui_get_phase(), _RealtimeSim.Phase.DUELING, "lock starts duel")
	assert_eq(_board.ui_get_locus_values(), [-1, -1, -1, -1], "guess builder empty at duel start")
	assert_eq(_board.ui_get_cast_button_state(), _CastButton.State.CHARGING, "cast button charging at t=0")
	assert_true(not _board.ui_get_rival_ward_revealed(), "rival ward hidden")

	# Cast button in thumb zone.
	var r: Rect2 = _board.ui_get_cast_button_rect()
	assert_true(r.size.x >= 120 and r.size.y >= 120, "cast button large enough (%s)" % str(r.size))
	assert_true(r.get_center().y / 1280.0 > 0.6, "cast button in lower part of screen (%.2f)" % (r.get_center().y / 1280.0))

	# Build a guess and try to cast too early.
	for s in [0, 0, 1, 1]:
		_board.ui_action_pick_spell(s)
	assert_true(not _board.ui_can_player_cast(), "cannot cast before 5s")
	_board.ui_action_cast()
	assert_eq(_board.game.player_history.size(), 0, "early cast ignored")
	_board.ui_advance_time(5.2)
	await process_frame
	assert_true(_board.ui_can_player_cast(), "castable after 5s with full guess")
	assert_eq(_board.ui_get_cast_button_state(), _CastButton.State.READY, "cast button READY")
	_board.ui_action_cast()
	await process_frame
	assert_eq(_board.game.player_history.size(), 1, "cast recorded")
	assert_true(_board.ui_get_result_banner_visible(), "result banner visible after cast")
	assert_true(_board.ui_get_result_text() != "", "result text present")
	assert_eq(_board.ui_get_visible_history_count(), 1, "history shows the cast")
	assert_eq(_board.ui_get_cast_button_state(), _CastButton.State.CHARGING, "window re-locks after cast")

	# Incomplete guess with open window → BLOCKED state.
	_board.ui_advance_time(5.2)
	_board.ui_action_pick_spell(3)
	await process_frame
	assert_eq(_board.ui_get_cast_button_state(), _CastButton.State.BLOCKED, "blocked while guess incomplete")
	_board.ui_action_cast()
	assert_eq(_board.game.player_history.size(), 1, "blocked cast ignored")

	# Copy previous cast from history into builder.
	_board.ui_action_tap_history_row(0)
	assert_eq(_board.ui_get_locus_values(), [0, 0, 1, 1], "history row copies into guess")
	_board.ui_action_clear()
	assert_eq(_board.ui_get_locus_values(), [-1, -1, -1, -1], "clear empties guess")

	# Rival tab.
	_board.ui_action_history_tab(true)
	assert_true(_board.ui_get_visible_history_count() >= 0, "rival tab renders")
	_board.ui_action_history_tab(false)

	# Play the duel out to a result, guessing the rival's ward when we "know" it.
	var enemy: Array = _board.game.get_enemy_ward()
	var safety := 0
	while _board.ui_get_phase() != _RealtimeSim.Phase.FINISHED and safety < 200:
		if _board.ui_can_player_cast():
			_board.ui_action_cast()
		elif _board.game.is_player_window_open():
			_board.ui_action_clear()
			for s in enemy:
				_board.ui_action_pick_spell(int(s))
		_board.ui_advance_time(1.0)
		await process_frame
		safety += 1
	assert_eq(_board.ui_get_phase(), _RealtimeSim.Phase.FINISHED, "duel reached a result")
	assert_true(_board.game.result != null and _board.game.result.outcome == "victory", "player wins by guessing the ward (%s)" % (_board.game.result.outcome if _board.game.result else "none"))
	await process_frame
	assert_true(_board.ui_get_rival_ward_revealed(), "rival ward revealed at end")
	# Result overlay appears after a short delay in normal mode.
	await create_timer(1.2).timeout
	assert_true(_board.ui_is_result_visible(), "result overlay shown")
	_board.queue_free()
	await process_frame


func _test_timer_states_and_auto_cast() -> void:
	_board = _new_board()
	await process_frame
	if _board.ui_is_overlay_visible():
		_board.ui_dismiss_overlay()
	for s in [0, 1, 3, 4]:
		_board.ui_action_pick_spell(s)
	_board.ui_action_lock_ward()
	await process_frame
	_board.game.debug_set_enemy_cast_at(999.0)
	_board.ui_action_pick_spell(0)
	_board.ui_action_pick_spell(0)
	_board.ui_advance_time(5.5)
	_board.game.debug_set_enemy_cast_at(999.0)
	await process_frame
	assert_eq(_board.ui_get_cast_button_state(), _CastButton.State.BLOCKED, "blocked with half a guess")
	_board.ui_advance_time(46.0)  # t = 51.5 → < 10 s left
	_board.game.debug_set_enemy_cast_at(999.0)
	await process_frame
	assert_eq(_board.ui_get_cast_button_state(), _CastButton.State.BLOCKED, "still blocked in warning zone when incomplete")
	_board.ui_action_pick_spell(1)
	_board.ui_action_pick_spell(1)
	await process_frame
	assert_eq(_board.ui_get_cast_button_state(), _CastButton.State.WARNING, "warning state under 10s with full guess")
	_board.ui_action_clear()
	_board.ui_action_pick_spell(9)
	_board.ui_advance_time(9.0)  # past 60 → auto cast
	await process_frame
	assert_eq(_board.game.player_history.size(), 1, "auto cast fired at 60s")
	assert_true(_board.game.player_history[0].was_auto_cast, "auto flag set")
	assert_eq(int(_board.game.player_history[0].pattern_by_locus[0]), 9, "auto cast kept chosen spell")
	assert_true(_board.ui_get_result_banner_visible(), "auto cast shows result")
	_board.queue_free()
	await process_frame


func _test_play_again_resets() -> void:
	_board = _new_board()
	await process_frame
	if _board.ui_is_overlay_visible():
		_board.ui_dismiss_overlay()
	for s in [0, 1, 3, 4]:
		_board.ui_action_pick_spell(s)
	_board.ui_action_lock_ward()
	await process_frame
	_board.ui_advance_time(5.2)
	for s in [0, 0, 1, 1]:
		_board.ui_action_pick_spell(s)
	_board.ui_action_cast()
	await process_frame
	_board.ui_debug_finish_duel("defeat")
	await create_timer(1.2).timeout
	assert_true(_board.ui_is_result_visible(), "defeat result shown")
	_board.ui_action_play_again()
	await process_frame
	assert_eq(_board.ui_get_phase(), _RealtimeSim.Phase.WARD_SETUP, "play again returns to ward setup")
	assert_true(not _board.ui_is_result_visible(), "result hidden after play again")
	assert_eq(_board.ui_get_visible_history_count(), 0, "history cleared")
	assert_eq(_board.ui_get_locus_values(), [-1, -1, -1, -1], "builder cleared")
	assert_true(not _board.ui_get_result_banner_visible(), "result banner hidden")
	assert_eq(_board.ui_get_selected_locus(), 0, "selection reset")
	# Second full game reaches dueling again.
	for s in [9, 9, 6, 6]:
		_board.ui_action_pick_spell(s)
	_board.ui_action_lock_ward()
	await process_frame
	assert_eq(_board.ui_get_phase(), _RealtimeSim.Phase.DUELING, "second duel starts")
	_board.queue_free()
	await process_frame


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
