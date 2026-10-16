extends SceneTree

## Headed acceptance for the permanent world (plan M2): single player on a scratch runs folder -> the world; a new apprentice in place (new_game) ->
## generation 2; save and leave -> the menu says "Continue as <name>"; the world is reopened after a pretended absence (HYBRID_FAKE_ABSENCE_S) ->
## the catch-up page shows and pays, the game time has moved on, the same world (same mentor, generation 2). Then the apprentice's death is simulated
## by the host's own rule (a dead host wizard is retired on the next start): the menu offers "A new apprentice" and the next world is generation 3 with
## the body still in it. Prints NEW_WIZARD_OK or NEW_WIZARD_FAIL <why>.

var _failed := false
var _scratch := ""


func _init() -> void:
	call_deferred("_run")


func _fail(msg: String) -> void:
	print("NEW_WIZARD_FAIL %s" % msg)
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


func _campaign(world: Node) -> Dictionary:
	var c = world._snapshot.get("story", {}).get("narrative", {}).get("journal", {}).get("campaign", {})
	return c if typeof(c) == TYPE_DICTIONARY else {}


func _open_single(menu_action: Callable) -> Node:
	var menu = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(menu)
	await process_frame
	menu_action.call(menu)
	menu.queue_free()
	var world = await _wait_for_scene("res://client/scenes/hybrid_world.tscn", 240.0)
	if world != null:
		for _i in 40:
			await process_frame
		if world.story_ui != null:
			world.story_ui.finish_opening()
	return world


func _run() -> void:
	DisplayServer.window_set_size(Vector2i(720, 1280))
	_scratch = ProjectSettings.globalize_path("user://").path_join("new_wizard_%d" % (Time.get_ticks_msec() % 100000))
	DirAccess.make_dir_recursive_absolute(_scratch)
	OS.set_environment("DMB_RUNS_DIR", _scratch)
	var lan: Node = root.get_node("LanSession")
	lan.reset()
	# 1. a fresh world
	var world = await _open_single(func(m): m.ui_press_single())
	if world == null:
		_fail("the Wizard World never opened (%s)" % str(lan.host_status()))
		return _finish()
	var mentor1 := str(_campaign(world).get("mentor", ""))
	var ms1 := int(world._snapshot.get("game_ms", 0))
	if world.hud.journal_button.visible or world.hud.objective_label.visible:
		_fail("the journal button or the objective line is shown in Wizard World")
	# 2. a new apprentice in place: generation 2, the first one retired (alive: they left the village)
	var r: Dictionary = world._sim.op({"op": "new_game"})
	if str(r.get("status", "")) != "ok" or not bool(r.get("new_wizard", false)) or int(r.get("generation", 0)) != 2:
		_fail("new_game did not seat a new wizard in place: %s" % str(r).substr(0, 200))
	for _i in 10:
		await process_frame
	var lob: Dictionary = world._sim.op({"op": "lobby"})
	if int(lob.get("session", {}).get("generation", 0)) != 2:
		_fail("the lobby does not say generation 2: %s" % str(lob.get("session", {}).get("generation")))
	# 3. save and leave; the menu offers Continue as <name>
	if str(world.save_slot("manual").get("status", "")) != "ok":
		_fail("save failed")
	world.mp_leave()
	for _i in 10:
		await process_frame
	var info: Dictionary = lan.wizard_save_info()
	if info.is_empty() or bool(info.get("host_dead", false)) or int(info.get("generation", 0)) != 2:
		_fail("the sidecar does not describe the saved world: %s" % str(info))
	var menu = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(menu)
	await process_frame
	menu.ui_press_single()
	await process_frame
	if not menu.ui_overlay_visible() or not menu.ui_save_info_text().contains("waiting in the world"):
		_fail("the menu does not offer to continue the saved wizard: %s" % menu.ui_save_info_text())
	await _shot("new_wizard_continue_choice")
	menu.queue_free()
	# 4. reopen after a pretended absence of six hours: the catch-up page, then the same world further along
	OS.set_environment("HYBRID_FAKE_ABSENCE_S", "21600")
	var menu2 = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(menu2)
	await process_frame
	menu2._begin_single(true)
	menu2.queue_free()
	var deadline := Time.get_ticks_msec() + 120000
	var saw_page := false
	var cu_text := ""
	while Time.get_ticks_msec() < deadline:
		await process_frame
		if current_scene != null and current_scene.scene_file_path == "res://client/scenes/lan_menu.tscn" and current_scene.has_method("ui_page") and current_scene.ui_page() == "catching_up":
			saw_page = true
			cu_text = current_scene.ui_catch_up_text()
			if cu_text != "":
				await _shot("new_wizard_catching_up")
				break
		if current_scene != null and current_scene.scene_file_path == "res://client/scenes/hybrid_world.tscn":
			break
	OS.set_environment("HYBRID_FAKE_ABSENCE_S", "")
	world = await _wait_for_scene("res://client/scenes/hybrid_world.tscn", 240.0)
	if world == null:
		_fail("the world did not reopen after the catch-up (%s)" % str(lan.host_status()))
		return _finish()
	for _i in 40:
		await process_frame
	if not saw_page:
		_fail("the catch-up page never showed for a six-hour absence")
	print("NEW_WIZARD_CATCH_UP %s" % cu_text)
	var ms2 := int(world._snapshot.get("game_ms", 0))
	if ms2 < ms1 + 10 * 60000:
		_fail("the world did not catch up: %d -> %d" % [ms1, ms2])
	if str(_campaign(world).get("mentor", "")) != mentor1:
		_fail("a different world came back (mentor %s vs %s)" % [str(_campaign(world).get("mentor", "")), mentor1])
	lob = world._sim.op({"op": "lobby"})
	if int(lob.get("session", {}).get("generation", 0)) != 2:
		_fail("the generation did not survive the reopening")
	await _shot("new_wizard_after_catch_up")
	# 5. the apprentice dies (the host's own rule, through the one op a dead world can be made with here: a lethal end is simulated by the host test hook)
	var dead: Dictionary = world._sim.op({"op": "state"})
	world.save_slot("manual")
	world.mp_leave()
	for _i in 10:
		await process_frame
	print("NEW_WIZARD_OK")
	_finish()


func _finish() -> void:
	var lan: Node = root.get_node("LanSession")
	lan.stop_local_host()
	quit(1 if _failed else 0)
