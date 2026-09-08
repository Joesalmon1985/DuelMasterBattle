extends SceneTree

## Real-time playtest: runs the real game loop with REAL wall-clock time
## (no ui_advance_time), synthesising taps as InputEvents at button positions.
## Verifies pacing: 5 s lock, rival casts on its own, auto-cast at 60 s.
## Run headed:  godot --path godot_project --resolution 720x1280 --script res://client/tools/realtime_playtest.gd
## Or headless: godot --headless --path godot_project --script res://client/tools/realtime_playtest.gd

const _RealtimeSim = preload("res://sim/realtime_duel_sim.gd")
const _CastButton = preload("res://client/components/cast_button.gd")

var _board
var _failures: Array = []
var _log: Array = []


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	if root.get_node_or_null("EncounterSession") == null:
		var s = load("res://client/scripts/encounter_session.gd").new()
		s.name = "EncounterSession"
		root.add_child(s)
	if root.get_node_or_null("Sfx") == null:
		var s2 = load("res://client/scripts/sfx.gd").new()
		s2.name = "Sfx"
		root.add_child(s2)
	root.get_node("EncounterSession").set_difficulty("medium")
	_board = load("res://client/scenes/game_board.tscn").instantiate()
	root.add_child(_board)
	await process_frame
	if _board.ui_is_overlay_visible():
		_board.ui_dismiss_overlay()
	await process_frame

	await process_frame
	await process_frame
	_note("tray slot 0 rect: %s  lock rect: %s  viewport: %s" % [str(_board._tray_slots[0].get_global_rect()), str(_board._lock_btn.get_global_rect()), str(root.get_visible_rect())])
	# --- Ward setup with real taps ---
	for id in [0, 1, 3, 4]:
		await _tap(_board._tray_slots[_tray_index(id)])
	_check(_board.game.can_lock_player_ward(), "ward complete via taps")
	await _tap(_board._lock_btn)
	_check(_board.ui_get_phase() == _RealtimeSim.Phase.DUELING, "lock via tap starts duel")
	if _board.ui_get_phase() != _RealtimeSim.Phase.DUELING:
		_report()
		return
	var t0 := Time.get_ticks_msec()

	# --- Try to cast immediately: should be blocked (locked window) ---
	for id in [0, 0, 1, 1]:
		await _tap(_board._tray_slots[_tray_index(id)])
	_check(_board.ui_get_cast_button_state() == _CastButton.State.CHARGING, "charging right after lock")
	await _tap(_board._cast_button._button)
	_check(_board.game.player_history.size() == 0, "tap while charging does not cast")

	# --- Wait for real 5 s window ---
	var guard := 0
	while not _board.game.is_player_window_open() and guard < 1200:
		await process_frame
		guard += 1
	var opened_ms := Time.get_ticks_msec() - t0
	_note("window opened after %d ms" % opened_ms)
	_check(opened_ms >= 4900 and opened_ms <= 5600, "window opens ~5 s wall-clock (%d ms)" % opened_ms)
	await process_frame
	_check(_board.ui_get_cast_button_state() == _CastButton.State.READY, "READY state when open with full guess")
	await _tap(_board._cast_button._button)
	_check(_board.game.player_history.size() == 1, "tap casts when ready")
	_check(_board.ui_get_result_banner_visible(), "result banner after real cast")

	# --- Rival acts on its own within its window (medium: 14–26 s) ---
	var waited := 0.0
	while _board.game.enemy_history.size() == 0 and waited < 40.0:
		await create_timer(0.25).timeout
		waited += 0.25
	_note("rival first cast after ~%.1f s" % waited)
	_check(_board.game.enemy_history.size() >= 1, "rival casts on its own")
	_check(waited >= 5.0 and waited <= 30.0, "rival pacing within band (%.1f s)" % waited)

	# --- Let the second window open, leave guess half-built, wait for auto-cast? Too long (60 s);
	#     instead verify WARNING state appears by fast-forwarding only the sim clock. ---
	guard = 0
	while not _board.game.is_player_window_open() and guard < 1200:
		await process_frame
		guard += 1
	await _tap(_board._tray_slots[_tray_index(9)])
	await process_frame
	_check(_board.ui_get_cast_button_state() == _CastButton.State.BLOCKED, "BLOCKED with partial guess")
	await _tap(_board._cast_button._button)
	_check(_board.game.player_history.size() == 1, "blocked tap does not cast")
	# Jump the sim clock so ~8 s remain in this window (independent of how long
	# the rival took above).
	var until_auto: float = float(_board.game.get_current_state()["player_time_until_auto"])
	_board.game.advance_time_for_test(maxf(0.0, until_auto - 8.0))
	await process_frame
	await process_frame
	_check(_board.ui_get_cast_button_state() == _CastButton.State.BLOCKED, "still blocked in warning zone")
	for id in [9, 9, 9]:
		await _tap(_board._tray_slots[_tray_index(id)])
	await process_frame
	_check(_board.ui_get_cast_button_state() == _CastButton.State.WARNING, "WARNING under 10 s with full guess")
	# wait real time for auto-cast (< 10 s left)
	var before: int = _board.game.player_history.size()
	waited = 0.0
	while _board.game.player_history.size() == before and waited < 15.0:
		await create_timer(0.25).timeout
		waited += 0.25
	_note("auto-cast fired after %.1f s of real time" % waited)
	_check(_board.game.player_history.size() == before + 1, "auto-cast fires when window expires")
	_check(_board.game.player_history[-1].was_auto_cast, "auto flag")

	# --- Pause: nothing should advance ---
	await _tap(_board._menu_btn)
	_check(_board.ui_is_overlay_visible(), "pause overlay opens")
	var dt0: float = _board.game.duel_time
	await create_timer(1.0).timeout
	_check(absf(_board.game.duel_time - dt0) < 0.001, "duel time frozen while paused")
	_board.ui_dismiss_overlay()
	await create_timer(0.5).timeout
	_check(_board.game.duel_time > dt0 + 0.3, "duel time resumes after unpause")

	_report()


func _tray_index(spell_id: int) -> int:
	for i in range(_board._tray_slots.size()):
		if _board._tray_slots[i].slot_index == spell_id:
			return i
	return 0


func _tap(ctrl: Control) -> void:
	# push_input expects window (screen) coordinates; convert from canvas space.
	var pos: Vector2 = root.get_final_transform() * ctrl.get_global_rect().get_center()
	var motion := InputEventMouseMotion.new()
	motion.position = pos
	motion.global_position = pos
	root.push_input(motion)
	await process_frame
	var hovered := root.gui_get_hovered_control()
	if hovered != ctrl and not (hovered != null and ctrl.is_ancestor_of(hovered)):
		_note("tap at %s hovered %s (wanted %s)" % [str(pos), str(hovered), str(ctrl)])
	var down := InputEventMouseButton.new()
	down.button_index = MOUSE_BUTTON_LEFT
	down.pressed = true
	down.position = pos
	down.global_position = pos
	root.push_input(down)
	await process_frame
	var up := InputEventMouseButton.new()
	up.button_index = MOUSE_BUTTON_LEFT
	up.pressed = false
	up.position = pos
	up.global_position = pos
	root.push_input(up)
	await process_frame
	await process_frame


func _check(cond: bool, msg: String) -> void:
	_log.append(("PASS " if cond else "FAIL ") + msg)
	if not cond:
		_failures.append(msg)


func _note(msg: String) -> void:
	_log.append("NOTE " + msg)


func _report() -> void:
	for l in _log:
		print(l)
	if _failures.is_empty():
		print("REALTIME PLAYTEST: ALL PASSED")
		quit(0)
	else:
		print("REALTIME PLAYTEST: FAILED (%d)" % _failures.size())
		quit(1)
