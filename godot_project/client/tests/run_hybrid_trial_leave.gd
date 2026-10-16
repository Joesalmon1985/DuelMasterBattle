extends SceneTree

## Headed probe: in through the gate and straight back out through the door; the map must be drawn where the wizard stands afterwards.
## Prints the camera, the avatar and the canvas transform, then HYBRID_TRIAL_OK. Env as run_hybrid_trial_a_d.gd.

var _lan: Node
var _world: Node
var _dir := ""


func _init() -> void:
	call_deferred("_run")


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _shot(name: String) -> void:
	if _dir == "":
		return
	await _frames(3)
	DirAccess.make_dir_recursive_absolute(_dir)
	root.get_viewport().get_texture().get_image().save_png(_dir.path_join(name + ".png"))


func _state() -> String:
	return "john_pos=%s john=%s cam=%s zoom=%s xf=%s area=%s active=%s snapshot_player=%s" % [str(_world._john_pos), str(_world._john.position), str(_world._camera.position),
		str(_world._camera.zoom), str(_world.get_viewport().get_canvas_transform()), str(_world.area_id), str(_world.trial_mode.active), str(_world._snapshot.get("player", {}))]


func _run() -> void:
	DisplayServer.window_set_size(Vector2i(720, 1280))
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	var port := int(OS.get_environment("HYBRID_LAN_PORT"))
	var code := OS.get_environment("HYBRID_LAN_CODE")
	_lan = root.get_node("/root/LanSession")
	_lan.reset()
	_lan.mode = "join"
	_lan.player_name = "GodotPlayer"
	var hello: Dictionary = _lan.connect_and_hello("127.0.0.1", port, code, "GodotPlayer")
	if str(hello.get("status", "")) != "ok":
		print("HYBRID_TRIAL_FAIL hello")
		quit(1)
		return
	var deadline := Time.get_ticks_msec() + 60000
	while Time.get_ticks_msec() < deadline:
		var lob: Dictionary = _lan.sim.op({"op": "lobby"})
		if str(lob.get("session", {}).get("state", "")) == "playing":
			break
		await create_timer(0.3).timeout
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	await _frames(40)
	_world.story_ui.finish_opening()
	await _frames(5)
	var gate: Dictionary = {}
	for e in _world._snapshot.get("entities", []):
		if typeof(e) == TYPE_DICTIONARY and str(e.get("kind", "")) == "trial_gate":
			gate = e
	_world._sim.op({"op": "teleport", "tx": int(gate["tx"]), "ty": int(gate["ty"]) + 1})
	_world.refresh_snapshot()
	_world._place_john_from_snapshot()
	await _frames(6)
	print("TRIAL before: " + _state())
	await _shot("leave01_before")
	_world.trial_mode.enter()
	await _frames(10)
	print("TRIAL inside: " + _state())
	# the camera must follow the wizard however the view is zoomed, even standing at the very edge of a small zone
	for zoom_px in [52.0, 110.0, 30.0]:
		_world.set_zoom_px(zoom_px, false)
		await _frames(6)
		var centre: Vector2 = _world._camera.get_screen_center_position()
		var want: Vector2 = _world._john.position + Vector2(_world.TPX * 0.5, _world.TPX * 0.5)
		print("TRIAL camera zoom_px=%s centre=%s player=%s off_by=%s" % [str(zoom_px), str(centre), str(want), str((centre - want).length())])
		if (centre - want).length() > 2.0:
			print("HYBRID_TRIAL_FAIL camera is not on the player at zoom_px=%s" % str(zoom_px))
	_world.set_zoom_px(52.0, false)
	await _frames(4)
	_world.trial_mode.leave()
	await _frames(3)
	print("TRIAL after 3 frames: " + _state())
	await _frames(20)
	print("TRIAL after 23 frames: " + _state())
	await _shot("leave02_after")
	print("HYBRID_TRIAL_OK")
	await _frames(2)
	quit(0)
