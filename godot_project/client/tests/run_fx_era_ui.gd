extends SceneTree

## FX-ERA control-surface regression — panel visibility + map/wait paths.
## godot --headless --path godot_project --script res://client/tests/run_fx_era_ui.gd

const Shell = preload("res://client/scenes/g05_shell.gd")


func _init() -> void:
	call_deferred("_run")


func _fail(msg: String) -> void:
	push_error(msg)
	print("FX_ERA_UI_FAIL:%s" % msg)
	quit(1)


func _run() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-ERA")
	OS.set_environment("DMB_SEED", "507")
	OS.set_environment("DMB_SAVE_SLOT", "fx_era_ui_test")
	var shell = Shell.new()
	root.add_child(shell)
	var deadline := Time.get_ticks_msec() + 45000
	while Time.get_ticks_msec() < deadline and not shell.is_booted():
		await process_frame
	if not shell.is_booted():
		_fail("shell_not_booted")
		return

	var panel: Control = shell.fx_era_panel()
	if panel == null:
		_fail("panel_missing")
		return
	if not panel.visible:
		_fail("panel_not_visible")
		return
	var wait_btn: Button = shell.fx_era_wait_button()
	var map_btn: Button = shell.fx_era_map_button()
	var chron_btn: Button = shell.fx_era_chronicle_button()
	if wait_btn == null or map_btn == null or chron_btn == null:
		_fail("buttons_missing")
		return
	if not wait_btn.visible or wait_btn.disabled:
		_fail("wait_button_not_ready")
		return
	if not map_btn.visible or not chron_btn.visible:
		_fail("map_or_chronicle_hidden")
		return

	# Panel must intersect the viewport (not off-screen).
	await process_frame
	var vp := root.get_viewport().get_visible_rect()
	var rect := panel.get_global_rect()
	if not vp.intersects(rect):
		_fail("panel_rect_outside_viewport:%s_vs_%s" % [str(rect), str(vp)])
		return

	# World Map open via shared path.
	shell.invoke_world_map_for_test()
	# Allow deferred open if clock was in flight.
	var map_deadline := Time.get_ticks_msec() + 8000
	var map_panel: Control = shell.world_map_panel()
	while Time.get_ticks_msec() < map_deadline:
		await process_frame
		if map_panel != null and map_panel.visible:
			break
	if map_panel == null or not map_panel.visible:
		_fail("map_not_visible")
		return
	if not shell.is_game_time_paused():
		_fail("map_did_not_pause")
		return
	# Close via toggle.
	shell.invoke_world_map_for_test()
	await process_frame
	if map_panel.visible:
		_fail("map_did_not_close")
		return

	# Chronicle open.
	shell.invoke_chronicle_for_test()
	await process_frame
	var chron: Control = shell.chronicle_panel()
	if chron == null or not chron.visible:
		_fail("chronicle_not_visible")
		return
	shell.invoke_chronicle_for_test()
	await process_frame

	# Wait button end-to-end → Historic.
	shell.invoke_fx_era_wait_for_test()
	var wait_deadline := Time.get_ticks_msec() + 30000
	var historic := false
	while Time.get_ticks_msec() < wait_deadline:
		await process_frame
		var view: Dictionary = shell.probe_player(["clock", "fx_era"])
		var clock: Dictionary = view.get("clock", {})
		if typeof(clock) != TYPE_DICTIONARY:
			clock = {}
		if str(clock.get("era", "")) == "historic" or str(clock.get("last_era_transition_id", "")) != "":
			historic = true
			break
	if not historic:
		_fail("wait_did_not_commit_historic")
		return
	if wait_btn.visible and not wait_btn.disabled:
		# After transition the button should be hidden or disabled.
		_fail("wait_button_still_active_after_historic")
		return

	print("FX_ERA_UI_OK")
	quit(0)
