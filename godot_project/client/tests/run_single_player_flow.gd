extends SceneTree

## Single player, the way a player takes it: main menu -> Play Single Player -> the private Wizard World on this device (a Python host process on a PC, the
## in-app Python on a phone) -> the world with the apprenticeship (mentor, lessons, campaign) and the AI fellow apprentice in it; save; leave; Continue.
## Saves go to a scratch folder (DMB_RUNS_DIR), never the player's. Prints SINGLE_FLOW_OK or SINGLE_FLOW_FAIL <why>. Needs a window for HYBRID_SHOT_DIR shots.

var _failed := false
var _scratch := ""


func _init() -> void:
	call_deferred("_run")


func _fail(msg: String) -> void:
	print("SINGLE_FLOW_FAIL %s" % msg)
	_failed = true


func _wait_for_scene(path: String, seconds: float) -> Node:
	var t := 0.0
	while t < seconds:
		await create_timer(0.1).timeout
		t += 0.1
		if current_scene != null and current_scene.scene_file_path == path:
			return current_scene
	return null


func _shot(name: String) -> void:
	var dir := OS.get_environment("HYBRID_SHOT_DIR")
	if dir == "":
		return
	for _i in 3:
		await process_frame
	DirAccess.make_dir_recursive_absolute(dir)
	root.get_viewport().get_texture().get_image().save_png(dir.path_join(name + ".png"))


func _run() -> void:
	DisplayServer.window_set_size(Vector2i(720, 1280))
	_scratch = ProjectSettings.globalize_path("user://").path_join("single_flow_%d" % (Time.get_ticks_msec() % 100000))
	DirAccess.make_dir_recursive_absolute(_scratch)
	OS.set_environment("DMB_RUNS_DIR", _scratch)
	var lan: Node = root.get_node("LanSession")
	lan.reset()
	var adv_before: Node = root.get_node("Adventure")
	var legacy_time := FileAccess.get_modified_time(adv_before.SAVE_PATH) if FileAccess.file_exists(adv_before.SAVE_PATH) else -1
	if lan.has_wizard_save():
		_fail("scratch saves folder is not empty")
	# --- a new campaign from the main menu
	var menu = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(menu)
	await process_frame
	await _shot("sp_main_menu")
	menu.ui_press_single()
	menu.queue_free()
	var world = await _wait_for_scene("res://client/scenes/hybrid_world.tscn", 180.0)
	if world == null:
		_fail("the Wizard World never opened (%s)" % str(lan.host_status()))
		_finish()
		return
	for _i in 120:
		await process_frame
	if not world.mp or not lan.private_session:
		_fail("single player is not a private hosted session")
	var snap: Dictionary = world._snapshot
	var story: Dictionary = snap.get("story", {})
	var nar: Dictionary = story.get("narrative", {})
	var camp: Dictionary = nar.get("journal", {}).get("campaign", {})
	if str(camp.get("stage", "")) != "training":
		_fail("the apprenticeship is not running: campaign=%s" % JSON.stringify(camp).substr(0, 200))
	if str(camp.get("mentor", "")) == "":
		_fail("no mentor in the world")
	var ai_rows := 0
	for p in snap.get("players", []):
		if bool(p.get("ai", false)):
			ai_rows += 1
	if ai_rows != 1:
		_fail("expected one AI fellow apprentice among the wizards, found %d" % ai_rows)
	if snap.get("entities", []).is_empty():
		_fail("no world entities")
	if world._art.missing.size() > 0:
		_fail("art missing: %s" % str(world._art.missing.slice(0, 8)))
	await _shot("sp_wizard_world")
	# --- the legacy adventure was never touched by launching Wizard World
	var adv: Node = root.get_node("Adventure")
	var legacy_now := FileAccess.get_modified_time(adv.SAVE_PATH) if FileAccess.file_exists(adv.SAVE_PATH) else -1
	if legacy_now != legacy_time:
		_fail("launching Wizard World wrote the old adventure's save")
	# --- save, leave, continue
	var saved: Dictionary = world.save_slot("manual")
	if str(saved.get("status", "")) != "ok":
		_fail("save failed: %s" % str(saved))
	world.mp_leave()
	for _i in 10:
		await process_frame
	if not lan.has_wizard_save():
		_fail("the saved campaign is not where the menu looks")
	menu = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(menu)
	await process_frame
	menu.ui_press_single()  # a save exists now: the menu offers Continue first
	await process_frame
	if not menu.ui_overlay_visible():
		_fail("with a saved campaign the menu should offer Continue")
	await _shot("sp_continue_choice")
	menu._begin_single(true)
	menu.queue_free()
	world = await _wait_for_scene("res://client/scenes/hybrid_world.tscn", 180.0)
	if world == null:
		_fail("Continue did not open the world")
		_finish()
		return
	for _i in 60:
		await process_frame
	var snap2: Dictionary = world._snapshot
	var camp2: Dictionary = snap2.get("story", {}).get("narrative", {}).get("journal", {}).get("campaign", {})
	if str(camp2.get("stage", "")) != "training" or str(camp2.get("mentor", "")) != str(camp.get("mentor", "x")):
		_fail("the continued campaign is not the saved one: %s" % JSON.stringify(camp2).substr(0, 200))
	var ai2 := 0
	for p in snap2.get("players", []):
		if bool(p.get("ai", false)):
			ai2 += 1
	if ai2 != 1:
		_fail("the companion did not return after Continue (%d)" % ai2)
	await _shot("sp_continued")
	world.mp_leave()
	_finish()


func _finish() -> void:
	var lan: Node = root.get_node("LanSession")
	lan.stop_local_host()
	lan.reset()
	if _scratch != "":
		OS.move_to_trash(_scratch)
	if _failed:
		quit(1)
		return
	print("SINGLE_FLOW_OK")
	quit(0)
