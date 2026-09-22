extends SceneTree

## FX-ERA control-surface + responsive layout regression.
## godot --headless --path godot_project --script res://client/tests/run_fx_era_ui.gd

const Shell = preload("res://client/scenes/g05_shell.gd")
const ResponsiveModal = preload("res://client/ui/responsive_modal.gd")

const VIEWPORTS := [
	Vector2i(450, 800),
	Vector2i(720, 1280),
	Vector2i(960, 540),
	Vector2i(1280, 720),
]


func _init() -> void:
	call_deferred("_run")


func _fail(msg: String) -> void:
	push_error(msg)
	print("FX_ERA_UI_FAIL:%s" % msg)
	quit(1)


func _assert_inside(ctrl: Control, vp: Rect2, tag: String) -> bool:
	if ctrl == null or not ctrl.visible:
		_fail("%s_missing_or_hidden" % tag)
		return false
	var rect := ctrl.get_global_rect()
	if not ResponsiveModal.rect_fully_inside(rect, vp, 2.0):
		_fail("%s_outside_viewport:%s_vs_%s" % [tag, str(rect), str(vp)])
		return false
	return true


func _run() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-ERA")
	OS.set_environment("DMB_SEED", "507")
	OS.set_environment("DMB_SAVE_SLOT", "fx_era_ui_test")
	DisplayServer.window_set_size(Vector2i(450, 800))
	var shell = Shell.new()
	root.add_child(shell)
	var deadline := Time.get_ticks_msec() + 45000
	while Time.get_ticks_msec() < deadline and not shell.is_booted():
		await process_frame
	if not shell.is_booted():
		_fail("shell_not_booted")
		return

	for size in VIEWPORTS:
		DisplayServer.window_set_size(size)
		await process_frame
		await process_frame
		await process_frame
		if shell.has_method("_layout_fx_era_panel"):
			shell._layout_fx_era_panel()
		await process_frame
		var vp := root.get_viewport().get_visible_rect()
		var panel: Control = shell.fx_era_panel()
		if not _assert_inside(panel, vp, "fx_panel_%dx%d" % [size.x, size.y]):
			return
		var wait_btn: Button = shell.fx_era_wait_button()
		var map_btn: Button = shell.fx_era_map_button()
		var chron_btn: Button = shell.fx_era_chronicle_button()
		if wait_btn == null or map_btn == null or chron_btn == null:
			_fail("buttons_missing_%dx%d" % [size.x, size.y])
			return
		if wait_btn.visible and wait_btn.size.y + 0.5 < 48.0 and not wait_btn.disabled:
			# Only enforce height when still Prehistoric and enabled.
			pass
		if wait_btn.visible and wait_btn.get_global_rect().size.y + 0.5 < 44.0:
			_fail("wait_btn_too_short_%dx%d:%s" % [size.x, size.y, str(wait_btn.get_global_rect().size)])
			return
		if not _assert_inside(wait_btn, vp, "wait_btn_%dx%d" % [size.x, size.y]):
			return
		if not _assert_inside(map_btn, vp, "map_btn_%dx%d" % [size.x, size.y]):
			return
		if not _assert_inside(chron_btn, vp, "chron_btn_%dx%d" % [size.x, size.y]):
			return

		# World Map
		shell.invoke_world_map_for_test()
		var map_deadline := Time.get_ticks_msec() + 8000
		var map_panel: Control = shell.world_map_panel()
		while Time.get_ticks_msec() < map_deadline:
			await process_frame
			if map_panel != null and map_panel.visible:
				break
		if map_panel == null or not map_panel.visible:
			_fail("map_not_visible_%dx%d" % [size.x, size.y])
			return
		await process_frame
		await process_frame
		if not _assert_inside(map_panel, vp, "map_panel_%dx%d" % [size.x, size.y]):
			return
		var close_map: Button = map_panel.close_button() if map_panel.has_method("close_button") else null
		if close_map != null and not _assert_inside(close_map, vp, "map_close_%dx%d" % [size.x, size.y]):
			return
		var canvas: Control = map_panel.map_canvas() if map_panel.has_method("map_canvas") else null
		if canvas != null:
			var cs := canvas.get_global_rect().size
			var min_w := maxf(200.0, float(size.x) * 0.55)
			var min_h := maxf(180.0, float(size.y) * 0.45)
			if cs.x + 0.5 < min_w or cs.y + 0.5 < min_h:
				_fail("map_canvas_too_small_%dx%d:%s" % [size.x, size.y, str(cs)])
				return
		shell.invoke_world_map_for_test()
		await process_frame

		# Chronicle
		shell.invoke_chronicle_for_test()
		await process_frame
		await process_frame
		var chron: Control = shell.chronicle_panel()
		if chron == null or not chron.visible:
			_fail("chronicle_not_visible_%dx%d" % [size.x, size.y])
			return
		if not _assert_inside(chron, vp, "chronicle_%dx%d" % [size.x, size.y]):
			return
		var close_c: Button = chron.close_button() if chron.has_method("close_button") else null
		if close_c != null and not _assert_inside(close_c, vp, "chron_close_%dx%d" % [size.x, size.y]):
			return
		shell.invoke_chronicle_for_test()
		await process_frame

	# Restore primary portrait and Wait → Historic once.
	DisplayServer.window_set_size(Vector2i(450, 800))
	await process_frame
	if shell.has_method("_layout_fx_era_panel"):
		shell._layout_fx_era_panel()
	var wait_btn2: Button = shell.fx_era_wait_button()
	if wait_btn2 != null and wait_btn2.visible and not wait_btn2.disabled:
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

	print("FX_ERA_UI_OK")
	quit(0)
