extends SceneTree

## Headed screenshot capture for visual QA. Run without --headless.
## Usage: godot --path godot_project --script res://client/tools/capture_visual_qa.gd [--baseline]

const _RealtimeSim = preload("res://sim/realtime_duel_sim.gd")
const _DuelEvent = preload("res://sim/duel_event.gd")

const SHOTS := [
	{"file": "01_main_menu.png", "fn": "_shot_main_menu"},
	{"file": "02_difficulty_select.png", "fn": "_shot_difficulty_select"},
	{"file": "03_encounter_select.png", "fn": "_shot_encounter_select"},
	{"file": "04_ward_setup.png", "fn": "_shot_ward_setup"},
	{"file": "05_duel_start.png", "fn": "_shot_duel_start"},
	{"file": "06_duel_mid.png", "fn": "_shot_duel_mid"},
	{"file": "07_duel_dense_history.png", "fn": "_shot_dense_history"},
	{"file": "08_cast_ready.png", "fn": "_shot_cast_ready"},
	{"file": "09_auto_cast_warning.png", "fn": "_shot_auto_cast_warning"},
	{"file": "10_attack_impact.png", "fn": "_shot_attack_impact"},
	{"file": "11_feedback_reveal.png", "fn": "_shot_feedback_reveal"},
	{"file": "12_last_stand.png", "fn": "_shot_last_stand"},
	{"file": "13_victory.png", "fn": "_shot_victory"},
	{"file": "14_defeat.png", "fn": "_shot_defeat"},
	{"file": "15_clash.png", "fn": "_shot_clash"},
]

var _out_dir: String
var _audit: Dictionary = {"screenshots": [], "touch_targets": [], "text_nodes": []}
var _board: GameBoard
var _menu: Control


func _init() -> void:
	var use_baseline := false
	for a in OS.get_cmdline_user_args():
		if str(a) == "--baseline":
			use_baseline = true
	var root_path := ProjectSettings.globalize_path("res://../..")
	if not DirAccess.dir_exists_absolute(root_path + "/qa"):
		root_path = ProjectSettings.globalize_path("res://..")
	_out_dir = root_path + "/qa/screenshots/" + ("baseline" if use_baseline else "current")
	DirAccess.make_dir_recursive_absolute(_out_dir)
	call_deferred("_run")


func _run() -> void:
	await process_frame
	_ensure_encounter_session()
	await process_frame
	for spec in SHOTS:
		await _call_shot(spec)
		await process_frame
		await process_frame
	_save_audit(root_path())
	quit(0)


func root_path() -> String:
	return _out_dir.get_base_dir().get_base_dir()


func _ensure_encounter_session() -> void:
	if root.get_node_or_null("EncounterSession") != null:
		return
	var script: GDScript = load("res://client/scripts/encounter_session.gd")
	var session = script.new()
	session.name = "EncounterSession"
	root.add_child(session)


func _call_shot(spec: Dictionary) -> void:
	_clear_root()
	await process_frame
	var fn: Callable = Callable(self, spec.fn)
	await fn.call()
	await process_frame
	await process_frame
	_capture(spec.file)


func _clear_root() -> void:
	for c in root.get_children():
		if c.name == "EncounterSession":
			continue
		c.queue_free()
	_board = null
	_menu = null
	await process_frame
	_ensure_encounter_session()


func _capture(filename: String) -> void:
	var vp := root.get_viewport()
	var img := vp.get_texture().get_image()
	var path := _out_dir + "/" + filename
	img.save_png(path)
	_audit.screenshots.append(path)
	if _board != null and _board.has_method("ui_audit_capture"):
		var data: Dictionary = _board.ui_audit_capture()
		_audit.touch_targets.append_array(data.get("touch_targets", []))
		_audit.text_nodes.append_array(data.get("text_nodes", []))
	print("CAPTURE: %s" % path)


func _save_audit(repo_root: String) -> void:
	var report_path := repo_root + "/qa/reports/capture_audit.json"
	DirAccess.make_dir_recursive_absolute(report_path.get_base_dir())
	var f := FileAccess.open(report_path, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(_audit, "\t"))
		f.close()


func _shot_main_menu() -> void:
	var scene: PackedScene = load("res://client/scenes/main_menu.tscn")
	_menu = scene.instantiate()
	root.add_child(_menu)


func _shot_difficulty_select() -> void:
	await _shot_main_menu()
	if _menu.has_node("VBox/DifficultyRow"):
		_menu.get_node("VBox/DifficultyRow").show()


func _shot_encounter_select() -> void:
	await _shot_main_menu()


func _shot_ward_setup() -> void:
	await _load_board("blue_apprentice")
	_board.ui_action_pick_secret_slot(0)
	_board.ui_action_pick_magic(0)


func _shot_duel_start() -> void:
	await _shot_ward_setup()
	_board.ui_action_lock_secret()


func _shot_duel_mid() -> void:
	await _shot_duel_start()
	for _i in range(3):
		if _board.ui_can_player_cast():
			_fill_attack_pattern()
			_board.ui_action_submit_guess()
		_board.ui_advance_time(2.5)
		await process_frame


func _shot_dense_history() -> void:
	await _shot_duel_mid()
	if _board.has_method("ui_set_history_expanded"):
		_board.ui_set_history_expanded(true)


func _shot_cast_ready() -> void:
	await _shot_duel_start()
	_board.ui_advance_time(0.5)


func _shot_auto_cast_warning() -> void:
	await _shot_duel_start()
	var st = _board.game.get_current_state()
	var until_auto := float(st.get("player_time_until_auto", 8.0))
	_board.ui_advance_time(maxf(0.0, until_auto - 2.5))


func _shot_attack_impact() -> void:
	await _shot_duel_start()
	_fill_attack_pattern()
	_board.ui_action_submit_guess()
	if _board.has_method("ui_debug_hold_animation"):
		_board.ui_debug_hold_animation(true)
	await process_frame


func _shot_feedback_reveal() -> void:
	await _shot_duel_start()
	_fill_attack_pattern()
	_board.ui_action_submit_guess()
	_board.ui_advance_time(1.5)


func _shot_last_stand() -> void:
	await _load_board("eightfold_warden")
	for i in range(_board.ui_get_slot_count()):
		_board.ui_action_pick_secret_slot(i)
		_board.ui_action_pick_magic(i % 3)
	_board.ui_action_lock_secret()
	if _board.has_method("ui_debug_trigger_last_stand"):
		_board.ui_debug_trigger_last_stand()


func _shot_victory() -> void:
	await _load_board("blue_apprentice")
	if _board.has_method("ui_debug_finish_duel"):
		_board.ui_debug_finish_duel("victory")


func _shot_defeat() -> void:
	await _load_board("blue_apprentice")
	if _board.has_method("ui_debug_finish_duel"):
		_board.ui_debug_finish_duel("defeat")


func _shot_clash() -> void:
	await _load_board("blue_apprentice")
	if _board.has_method("ui_debug_finish_duel"):
		_board.ui_debug_finish_duel("clash")


func _load_board(encounter_id: String) -> void:
	var scene: PackedScene = load("res://client/scenes/game_board.tscn")
	_board = scene.instantiate()
	root.add_child(_board)
	await process_frame
	_board.ui_load_encounter(encounter_id)
	await process_frame


func _fill_attack_pattern() -> void:
	var n := _board.ui_get_slot_count()
	for s in range(n):
		_board.ui_action_pick_guess_slot(s)
		_board.ui_action_pick_magic(s % 3)
