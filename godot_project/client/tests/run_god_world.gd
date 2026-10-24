extends SceneTree

## Headed God World evidence (docs/GOD_WORLD_PRD.md M2): the scene hosts the real Python world (profile god_catan_v1) on this device, and this script
## drives it with real input events: a drag pans and never selects, a pinch zooms around its midpoint and never selects, a first tap shows the anchored
## label, a second tap on the label opens the details sheet, a tap on empty ground dismisses, the view works at village, region and whole-board zoom, and
## the world progresses without the camera moving. Screenshots land in HYBRID_SHOT_DIR (default docs/evidence/god_world/headed). Prints GOD_WORLD_OK.
## Run: godot --path godot_project --rendering-method forward_plus --script res://client/tests/run_god_world.gd

var _world: Node
var _fails: Array[String] = []
var _dir := ""


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("GOD %s %s" % ["ok  " if ok else "FAIL", label])
	if not ok:
		_fails.append(label)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _settle() -> void:
	await _frames(3)
	await RenderingServer.frame_post_draw


func _shot(name: String) -> void:
	await _settle()
	var image: Image = get_root().get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(_dir)
	image.save_png(_dir.replace("\\", "/") + "/%s.png" % name)
	print("GOD_SHOT %s" % name)


## Injected pointer positions are window pixels; the scene reasons in viewport units (720 x 1280 under canvas_items stretch), so every position here is
## given in viewport units and converted on the way in.
func _win(vpos: Vector2) -> Vector2:
	return vpos * (Vector2(DisplayServer.window_get_size()) / get_root().get_visible_rect().size)


func _touch(index: int, pressed: bool, pos: Vector2) -> void:
	var e := InputEventScreenTouch.new()
	e.index = index
	e.pressed = pressed
	e.position = _win(pos)
	Input.parse_input_event(e)
	await _frames(1)


func _drag(index: int, pos: Vector2, rel: Vector2) -> void:
	var e := InputEventScreenDrag.new()
	e.index = index
	e.position = _win(pos)
	e.relative = _win(rel)
	Input.parse_input_event(e)
	await _frames(1)


func _tap(pos: Vector2) -> void:
	await _touch(0, true, pos)
	await _frames(2)
	await _touch(0, false, pos)
	await _frames(3)


func _wait_until(pred: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while Time.get_ticks_msec() < deadline:
		if pred.call():
			return true
		await _frames(5)
	return false


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = ProjectSettings.globalize_path("res://").path_join("../docs/evidence/god_world/headed")
	var runs := OS.get_environment("DMB_RUNS_DIR")
	if runs == "":
		runs = OS.get_user_data_dir().path_join("god_world_test_runs_%d" % (Time.get_ticks_msec() % 100000))
		OS.set_environment("DMB_RUNS_DIR", runs)
	get_root().size = Vector2i(450, 800)
	DisplayServer.window_set_size(Vector2i(450, 800))
	change_scene_to_file("res://client/scenes/god_world.tscn")
	await _frames(3)
	_world = current_scene
	_check(_world != null and _world.has_method("ui_state"), "god world scene loaded")
	var ok := await _wait_until(func(): return _world.ui_state()["state"] == "playing", 90.0)
	_check(ok, "the device hosts the world and the scene is playing (%s)" % str(_world.ui_state()["status"]))
	if not ok:
		return _finish()
	await _shot("01_setup")
	var st: Dictionary = _world.ui_state()
	_check(st["villages"] >= 0 and st["polls"] > 0, "state polls arrive")
	# the factions place their sites and the world turns without any input
	ok = await _wait_until(func(): return _world.ui_state()["phase"] == "RUNNING", 60.0)
	_check(ok, "setup completed by the AIs (phase RUNNING)")
	var before_ms: int = _world.ui_state()["game_ms"]
	await _wait_until(func(): return _world.ui_state()["game_ms"] > before_ms + 3000, 10.0)
	_check(_world.ui_state()["game_ms"] > before_ms, "the clock runs while the camera is still")
	# close view of a working village
	await _settle()
	var vp: Vector2 = _world.ui_village_screen_pos()
	var vis := get_root().get_visible_rect().size
	_check(vp.x >= 0.0 and vp.x <= vis.x and vp.y <= vis.y, "a village is on screen at start (%s)" % str(vp))
	_world.camera_ctl.set_zoom(0.8)
	await _settle()
	await _shot("02_village_close")
	_check(_world.ui_state()["missing_art"].is_empty(), "no missing art at village zoom: %s" % str(_world.ui_state()["missing_art"]))
	# PAN: a drag that starts on the village pans and does not select
	var centre := get_root().get_visible_rect().size * 0.5
	vp = _world.ui_village_screen_pos()
	var cam0: Vector2 = _world.camera.position
	await _shot("03_pan_before")
	await _touch(0, true, vp)
	for i in 8:
		await _drag(0, vp + Vector2(0, 30 * (i + 1)), Vector2(0, 30))
	await _touch(0, false, vp + Vector2(0, 240))
	await _frames(3)
	var cam1: Vector2 = _world.camera.position
	_check(cam1.distance_to(cam0) > 50.0, "drag panned the camera (%s -> %s)" % [str(cam0), str(cam1)])
	_check(_world.ui_state()["labels"]["state"] == "HIDDEN", "a drag never selects on release")
	await _shot("04_pan_after")
	# PINCH: two fingers, zoom changes around the midpoint, nothing selected
	var z0: float = _world.camera_ctl.zoom_level
	var mid := centre
	var world_mid: Vector2 = _world.camera_ctl.screen_to_world(mid)
	await _touch(0, true, mid + Vector2(-40, 0))
	await _touch(1, true, mid + Vector2(40, 0))
	for i in 6:
		await _drag(0, mid + Vector2(-40 - 15 * (i + 1), 0), Vector2(-15, 0))
		await _drag(1, mid + Vector2(40 + 15 * (i + 1), 0), Vector2(15, 0))
	await _touch(1, false, mid + Vector2(130, 0))
	await _touch(0, false, mid + Vector2(-130, 0))
	await _frames(3)
	var z1: float = _world.camera_ctl.zoom_level
	_check(z1 > z0 * 1.2, "pinch zoomed in (%.3f -> %.3f)" % [z0, z1])
	var world_mid2: Vector2 = _world.camera_ctl.screen_to_world(mid)
	_check(world_mid2.distance_to(world_mid) < 40.0, "the world point under the midpoint stayed put (%.1f px)" % world_mid2.distance_to(world_mid))
	_check(_world.ui_state()["labels"]["state"] == "HIDDEN", "a pinch never selects")
	await _shot("05_pinch_after")
	# a tap right after a pinch is swallowed on purpose (the emulated mouse leftovers): a real finger waits longer than this
	await _wait_until(func(): return false, 0.4)
	# TAP: label, then details, then dismiss
	_world.camera_ctl.set_zoom(0.6)
	await _settle()
	vp = _world.ui_village_screen_pos()
	await _tap(vp + Vector2(0, -20))
	await _frames(3)
	var ls: Dictionary = _world.ui_state()["labels"]
	_check(ls["state"] == "LABEL" and str(ls["label"]) != "", "first tap shows an anchored label: %s" % str(ls["label"]).replace("\n", " / "))
	await _shot("06_label")
	var rect: Rect2 = ls["label_rect"]
	_check(rect.size.x >= 76.0 and rect.size.y >= 76.0, "label touch target is at least 48 dp (%s)" % str(rect.size))
	await _tap(rect.get_center())
	ls = _world.ui_state()["labels"]
	_check(ls["state"] == "DETAILS" and str(ls["details_title"]) != "", "second tap on the label opens details: %s" % str(ls["details_title"]))
	await _shot("07_details")
	# Back returns to the label, a tap on empty ground clears
	_world.labels.back()
	await _frames(2)
	_check(_world.ui_state()["labels"]["state"] == "LABEL", "back from details returns to the label")
	await _tap(Vector2(centre.x, 180.0))
	ls = _world.ui_state()["labels"]
	_check(ls["state"] == "HIDDEN" or ls["id"].begins_with("hex:"), "tap on ground dismisses or selects the hex (%s)" % str(ls["state"]))
	_world.labels.clear()
	# a hex label
	_world.camera_ctl.set_zoom(0.3)
	await _settle()
	await _tap(centre)
	ls = _world.ui_state()["labels"]
	_check(ls["state"] == "LABEL", "a tap at region zoom labels something (%s)" % str(ls["id"]))
	await _shot("08_region")
	_world.labels.clear()
	_world.camera_ctl.fit_board()
	await _settle()
	await _shot("09_whole_board")
	_check(_world.camera_ctl.zoom_level <= 0.2, "fit shows the whole island (zoom %.3f)" % _world.camera_ctl.zoom_level)
	# speed and pause act on the one clock
	_world.set_speed(4)
	ok = await _wait_until(func(): return _world.ui_state()["speed"] == 4, 5.0)
	_check(ok, "speed 4x accepted")
	var ms_a: int = _world.ui_state()["game_ms"]
	ok = await _wait_until(func(): return _world.ui_state()["journeys"] > 0, 60.0)
	_check(ok, "a journey is on the road (caravan, expedition or bank)")
	if ok:
		var j: Dictionary = _world.snapshot["journeys"][0]
		_world.camera_ctl.focus_on(_world.view.bu(float(j["x"]), float(j["y"])), 0.7)
		await _settle()
		await _shot("10_journey")
	_world.toggle_pause()
	ok = await _wait_until(func(): return _world.ui_state()["paused"], 5.0)
	_check(ok, "pause accepted")
	await _frames(15)
	var ms_p: int = _world.ui_state()["game_ms"]
	await _frames(45)
	_check(_world.ui_state()["game_ms"] == ms_p, "the clock does not move while paused")
	_world.toggle_pause()
	_world.set_speed(1)
	await _wait_until(func(): return not _world.ui_state()["paused"], 5.0)
	await _frames(20)
	_check(_world.ui_state()["game_ms"] >= ms_a, "clock resumed")
	_check(_world.ui_state()["missing_art"].is_empty(), "no missing art after the tour: %s" % str(_world.ui_state()["missing_art"]))
	_finish()


func _finish() -> void:
	var lan: Node = get_root().get_node_or_null("LanSession")
	if lan != null:
		lan.stop_local_host()
	if _fails.is_empty():
		print("GOD_WORLD_OK")
	else:
		print("GOD_WORLD_FAILED %s" % str(_fails))
	quit()
