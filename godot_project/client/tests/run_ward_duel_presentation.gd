extends SceneTree

## Ward Duel presentation leak regression — real G05 / FX-MVP route.
## Travels west toward an active demon hex, opens retained Ward Duel, asserts
## world presentation is hidden/non-interactive during duel, then restored once.
##
## godot --headless --path godot_project --script res://client/tests/run_ward_duel_presentation.gd
## Optional headed screenshots:
##   DMB_WARD_DUEL_SHOTS=1 DMB_SHOT_DIR=... --resolution 450x800

const Shell = preload("res://client/scenes/g05_shell.gd")
const VillageTestRunner = preload("res://client/scripts/village_test_runner.gd")

## Deterministic west-first path from node:35 toward cube:1 (hex:1,-2) on seed 507.
const TRAVEL_PATH := ["node:35", "node:30", "node:36", "node:31", "node:37"]
const TARGET_CUBE := "cube:1"


func _init() -> void:
	call_deferred("_run")


func _fail(msg: String) -> void:
	push_error(msg)
	print("WARD_DUEL_PRESENTATION_FAIL %s" % msg)
	quit(1)


func _dict(v) -> Dictionary:
	return v if typeof(v) == TYPE_DICTIONARY else {}


func _shots_enabled() -> bool:
	return OS.get_environment("DMB_WARD_DUEL_SHOTS") in ["1", "true", "TRUE", "yes"]


func _shot_dir() -> String:
	var env := OS.get_environment("DMB_SHOT_DIR")
	if env != "":
		return env
	return ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir().path_join(
		"Pack/DuelMasterBattle_Build_Pack/tracking/gates/G11/ward_duel_leak"
	)


func _capture(name: String) -> void:
	if not _shots_enabled():
		return
	await process_frame
	await process_frame
	var img: Image = get_root().get_viewport().get_texture().get_image()
	if img == null:
		push_warning("screenshot failed: %s" % name)
		return
	var dir := _shot_dir()
	DirAccess.make_dir_recursive_absolute(dir)
	var res := DisplayServer.window_get_size()
	var path := dir.path_join("%s_%dx%d.png" % [name, res.x, res.y])
	var err := img.save_png(path)
	if err != OK:
		push_warning("save_png failed %s err=%s" % [path, err])
	else:
		print("WARD_DUEL_SHOT %s" % path)


func _count_named(root: Node, name: String) -> int:
	var n := 0
	if root == null:
		return 0
	if root.name == name:
		n += 1
	for child in root.get_children():
		n += _count_named(child, name)
	return n


func _hazard_entity(area: Dictionary, cube_id: String) -> Dictionary:
	for raw in area.get("entities", []):
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var e: Dictionary = raw
		if str(e.get("kind", "")) == "hazard" and str(e.get("cube_id", e.get("id", ""))) == cube_id:
			return e
	return {}


func _run() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-MVP")
	OS.set_environment("DMB_SEED", "507")
	OS.set_environment("DMB_SAVE_SLOT", "g05_ward_duel_presentation")
	var shell = Shell.new()
	root.add_child(shell)
	var deadline := Time.get_ticks_msec() + 45000
	while Time.get_ticks_msec() < deadline and not shell.is_village_ready():
		await process_frame
	if not shell.is_booted() or not shell.is_village_ready():
		_fail("FX-MVP shell not ready")
		return
	var ow = shell.overworld()
	if ow == null or not ow.visible:
		_fail("overworld missing or already hidden before encounter")
		return
	if shell.presentation_mode_name() != "WORLD":
		_fail("expected WORLD mode before encounter, got %s" % shell.presentation_mode_name())
		return
	await _capture("01_before_encounter")

	# Travel west/north along the real board until cube:1 is on the local area.
	for i in range(TRAVEL_PATH.size() - 1):
		var frm: String = str(TRAVEL_PATH[i])
		var too: String = str(TRAVEL_PATH[i + 1])
		if not shell.travel_to_node(frm, too):
			_fail("Travel %s→%s failed: %s" % [frm, too, shell.last_travel_feedback()])
			return
		await process_frame
		await process_frame

	var area: Dictionary = VillageTestRunner.get_area()
	var hazard := _hazard_entity(area, TARGET_CUBE)
	if hazard.is_empty():
		# Area may need a fresh view after travel.
		shell.reproject_from_python()
		await process_frame
		area = VillageTestRunner.get_area()
		hazard = _hazard_entity(area, TARGET_CUBE)
	if hazard.is_empty():
		_fail("hazard %s not present on local area after travel" % TARGET_CUBE)
		return
	if not bool(hazard.get("bridge_challenge", false)):
		_fail("hazard %s not challengeable" % TARGET_CUBE)
		return

	var workers_before := 0
	if shell.get("_workers") != null:
		workers_before = shell._workers.get_child_count() if shell._workers is Node else 0
	var overworld_children_before := ow.get_child_count()

	if not shell.start_hazard_challenge(TARGET_CUBE):
		_fail("start_hazard_challenge rejected for %s" % TARGET_CUBE)
		return
	await process_frame
	await process_frame
	await create_timer(0.4).timeout

	if shell.presentation_mode_name() != "WARD_DUEL":
		_fail("expected WARD_DUEL mode, got %s" % shell.presentation_mode_name())
		return
	var clean: Dictionary = shell.presentation_assert_ward_clean()
	if not bool(clean.get("ok", false)):
		_fail("ward duel presentation leaks: %s" % str(clean.get("leaks", [])))
		return
	if ow.visible:
		_fail("Overworld still visible during Ward Duel")
		return
	if ow.process_mode != Node.PROCESS_MODE_DISABLED:
		_fail("Overworld still processing during Ward Duel")
		return
	if shell._duel_adapter == null or not shell._duel_adapter.is_active():
		_fail("duel adapter inactive after challenge")
		return
	var board = shell._duel_adapter._board
	if board == null or not is_instance_valid(board) or not board.visible:
		_fail("GameBoard not visible during Ward Duel")
		return
	# Shell UI / chrome must not sit over the duel.
	if shell._ui_layer != null and shell._ui_layer.visible:
		_fail("ShellUILayer still visible during Ward Duel")
		return
	if shell._status != null and shell._status.visible:
		_fail("StatusLabel still visible during Ward Duel")
		return
	await _capture("02_clean_ward_duel")

	# Finish via retained board Continue path (same as player).
	board.ui_debug_finish_duel("victory")
	var wait_result := Time.get_ticks_msec() + 3000
	while Time.get_ticks_msec() < wait_result and not board.ui_is_result_visible():
		await create_timer(0.1).timeout
	if board.ui_is_result_visible():
		# Click Continue if present.
		var labels: Array = board.ui_overlay_button_labels()
		if labels.has("Continue"):
			if not board.ui_pointer_press_overlay_button("Continue"):
				# Fallback: direct finished callback.
				shell._duel_adapter._on_board_finished("victory", {})
		else:
			shell._duel_adapter._on_board_finished("victory", {})
	else:
		shell._duel_adapter._on_board_finished("victory", {})

	await process_frame
	await create_timer(0.5).timeout
	# Wait until adapter tears down.
	var tear_deadline := Time.get_ticks_msec() + 4000
	while Time.get_ticks_msec() < tear_deadline and shell._duel_adapter != null and shell._duel_adapter.is_active():
		await create_timer(0.1).timeout

	var restored: Dictionary = shell.presentation_assert_world_restored()
	if not bool(restored.get("ok", false)):
		_fail("world not restored cleanly: %s" % str(restored.get("issues", [])))
		return
	ow = shell.overworld()
	if ow == null or not ow.visible:
		_fail("Overworld not visible after duel")
		return
	if ow.process_mode == Node.PROCESS_MODE_DISABLED:
		_fail("Overworld still disabled after duel")
		return
	if shell.presentation_mode_name() == "WARD_DUEL":
		_fail("still in WARD_DUEL after finish")
		return
	# No duplicated overworld roots.
	if _count_named(shell, "Overworld") != 1:
		_fail("expected exactly one Overworld, got %s" % _count_named(shell, "Overworld"))
		return
	if shell._duel_host != null and shell._duel_host.visible:
		_fail("DuelHost still visible after return")
		return
	# Worker / actor fan-out must not explode from a single duel cycle.
	if shell.get("_workers") != null and shell._workers is Node:
		var workers_after: int = shell._workers.get_child_count()
		if workers_after > workers_before + 8:
			_fail("worker children ballooned %s→%s" % [workers_before, workers_after])
			return
	if ow.get_child_count() > overworld_children_before + 12:
		_fail("overworld children ballooned %s→%s" % [overworld_children_before, ow.get_child_count()])
		return

	await _capture("03_returned_world")
	print("WARD_DUEL_PRESENTATION_OK mode=%s cube=%s" % [shell.presentation_mode_name(), TARGET_CUBE])
	quit(0)
