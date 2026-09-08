extends SceneTree

## Headed screenshot capture for visual QA. Run WITHOUT --headless:
##   godot --path godot_project --resolution 720x1280 --script res://client/tools/capture_visual_qa.gd -- --screenshot-mode
## Writes qa/screenshots/current/*.png and qa/reports/capture_audit.json

const _RealtimeSim = preload("res://sim/realtime_duel_sim.gd")

const SHOTS := [
	{"file": "01_main_menu.png", "fn": "_shot_main_menu"},
	{"file": "02_how_to_play.png", "fn": "_shot_how_to_play"},
	{"file": "03_ward_setup_empty.png", "fn": "_shot_ward_setup_empty"},
	{"file": "04_ward_setup_full.png", "fn": "_shot_ward_setup_full"},
	{"file": "05_duel_start_charging.png", "fn": "_shot_duel_start"},
	{"file": "06_guess_incomplete_blocked.png", "fn": "_shot_blocked"},
	{"file": "07_cast_ready.png", "fn": "_shot_cast_ready"},
	{"file": "08_after_cast_result.png", "fn": "_shot_after_cast"},
	{"file": "09_dense_history.png", "fn": "_shot_dense_history"},
	{"file": "10_rival_history_tab.png", "fn": "_shot_rival_tab"},
	{"file": "11_warning.png", "fn": "_shot_warning"},
	{"file": "12_pause_menu.png", "fn": "_shot_pause"},
	{"file": "13_victory.png", "fn": "_shot_victory"},
	{"file": "14_defeat.png", "fn": "_shot_defeat"},
]

var _out_dir: String
var _audit: Dictionary = {"screenshots": [], "touch_targets": [], "text_nodes": []}
var _board
var _menu


func _init() -> void:
	var root_path := ProjectSettings.globalize_path("res://..")
	_out_dir = root_path + "/qa/screenshots/current"
	DirAccess.make_dir_recursive_absolute(_out_dir)
	call_deferred("_run")


func _run() -> void:
	await process_frame
	_ensure_autoloads()
	await process_frame
	for spec in SHOTS:
		await _call_shot(spec)
	_save_audit()
	quit(0)


func _ensure_autoloads() -> void:
	if root.get_node_or_null("EncounterSession") == null:
		var s = load("res://client/scripts/encounter_session.gd").new()
		s.name = "EncounterSession"
		root.add_child(s)
	if root.get_node_or_null("Sfx") == null:
		var s2 = load("res://client/scripts/sfx.gd").new()
		s2.name = "Sfx"
		root.add_child(s2)


func _call_shot(spec: Dictionary) -> void:
	var fn: Callable = Callable(self, spec.fn)
	await fn.call()
	await process_frame
	await process_frame
	await process_frame
	_capture(spec.file)


func _capture(file: String) -> void:
	var img: Image = root.get_viewport().get_texture().get_image()
	var path := _out_dir + "/" + file
	img.save_png(path)
	_audit["screenshots"].append(file)
	print("shot ", file)
	if _board != null and is_instance_valid(_board) and _board.has_method("ui_audit_capture"):
		var a: Dictionary = _board.ui_audit_capture()
		for t in a.get("touch_targets", []):
			t["shot"] = file
			_audit["touch_targets"].append(t)


func _clear() -> void:
	if _menu != null and is_instance_valid(_menu):
		_menu.queue_free()
		_menu = null
	if _board != null and is_instance_valid(_board):
		_board.queue_free()
		_board = null


func _fresh_board() -> void:
	_clear()
	await process_frame
	_board = load("res://client/scenes/game_board.tscn").instantiate()
	root.add_child(_board)
	await process_frame
	if _board.ui_is_overlay_visible():
		_board.ui_dismiss_overlay()


func _to_duel(ward: Array = [0, 1, 3, 4]) -> void:
	await _fresh_board()
	for s in ward:
		_board.ui_action_pick_spell(s)
	_board.ui_action_lock_ward()
	await process_frame
	_board.game.debug_set_enemy_ward([9, 6, 0, 9])


func _shot_main_menu() -> void:
	_clear()
	await process_frame
	_menu = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(_menu)


func _shot_how_to_play() -> void:
	if _menu == null:
		await _shot_main_menu()
		await process_frame
	_menu.ui_show_help()


func _shot_ward_setup_empty() -> void:
	await _fresh_board()


func _shot_ward_setup_full() -> void:
	await _fresh_board()
	for s in [0, 1, 9, 4]:
		_board.ui_action_pick_spell(s)


func _shot_duel_start() -> void:
	await _to_duel()
	_board.ui_advance_time(1.5)


func _shot_blocked() -> void:
	await _to_duel()
	_board.game.debug_set_enemy_cast_at(999.0)
	_board.ui_action_pick_spell(9)
	_board.ui_action_pick_spell(6)
	_board.ui_advance_time(6.0)
	_board.game.debug_set_enemy_cast_at(999.0)
	_board.ui_advance_time(0.01)


func _shot_cast_ready() -> void:
	await _to_duel()
	_board.game.debug_set_enemy_cast_at(999.0)
	for s in [9, 6, 6, 1]:
		_board.ui_action_pick_spell(s)
	_board.ui_advance_time(6.0)
	_board.game.debug_set_enemy_cast_at(999.0)
	_board.ui_advance_time(0.01)


func _shot_after_cast() -> void:
	await _to_duel()
	_board.game.debug_set_enemy_cast_at(999.0)
	for s in [9, 6, 6, 1]:
		_board.ui_action_pick_spell(s)
	_board.ui_advance_time(6.0)
	_board.ui_action_cast()
	_board.game.debug_set_enemy_cast_at(999.0)
	_board.ui_advance_time(0.5)


func _shot_dense_history() -> void:
	await _to_duel()
	var guesses := [[0, 0, 1, 1], [3, 3, 4, 4], [6, 6, 9, 9], [9, 6, 3, 9], [9, 6, 1, 9]]
	var n := 0
	for g in guesses:
		# Let the rival cast twice so its tab has content, then hold it back.
		_board.game.debug_set_enemy_cast_at(8.0 if n < 2 else 999.0)
		n += 1
		_board.ui_advance_time(6.0)
		_board.ui_action_clear()
		for s in g:
			_board.ui_action_pick_spell(s)
		_board.ui_action_cast()
		_board.ui_advance_time(4.0)
	_board.game.debug_set_enemy_cast_at(999.0)
	_board.ui_advance_time(2.0)


func _shot_rival_tab() -> void:
	await _shot_dense_history()
	_board.ui_action_history_tab(true)


func _shot_warning() -> void:
	await _to_duel()
	_board.game.debug_set_enemy_cast_at(999.0)
	for s in [9, 6, 6, 1]:
		_board.ui_action_pick_spell(s)
	_board.ui_advance_time(54.0)
	_board.game.debug_set_enemy_cast_at(999.0)
	_board.ui_advance_time(0.01)


func _shot_pause() -> void:
	await _to_duel()
	_board.ui_advance_time(3.0)
	_board.ui_action_menu()


func _shot_victory() -> void:
	await _shot_dense_history()
	_board.ui_debug_finish_duel("victory")


func _shot_defeat() -> void:
	await _shot_dense_history()
	_board.ui_debug_finish_duel("defeat")


func _save_audit() -> void:
	var reports := ProjectSettings.globalize_path("res://..") + "/qa/reports"
	DirAccess.make_dir_recursive_absolute(reports)
	var f := FileAccess.open(reports + "/capture_audit.json", FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(_audit, "  "))
