extends SceneTree

## In-world visual review harness (Phase C starter).
## Deterministic headed captures of real G05 presentation — not a badge gallery.
## Expanded overnight to cover terrain/settlement/military/hazards/era/map.
##
## godot --path godot_project --resolution 450x800 --script res://client/tests/run_visual_review_harness.gd

const Shell = preload("res://client/scenes/g05_shell.gd")


func _init() -> void:
	call_deferred("_run")


func _fail(msg: String) -> void:
	push_error(msg)
	print("VISUAL_REVIEW_FAIL %s" % msg)
	quit(1)


func _shot_dir() -> String:
	var env := OS.get_environment("DMB_SHOT_DIR")
	if env != "":
		return env
	return ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir().path_join(
		"Pack/DuelMasterBattle_Build_Pack/tracking/gates/G11/visual_review"
	)


func _capture(name: String) -> void:
	await process_frame
	await process_frame
	var img: Image = get_root().get_viewport().get_texture().get_image()
	if img == null:
		return
	var dir := _shot_dir()
	DirAccess.make_dir_recursive_absolute(dir)
	var res := DisplayServer.window_get_size()
	var path := dir.path_join("%s_%dx%d.png" % [name, res.x, res.y])
	img.save_png(path)
	print("VISUAL_REVIEW_SHOT %s" % path)


func _run() -> void:
	if OS.get_environment("DMB_FIXTURE") == "":
		OS.set_environment("DMB_FIXTURE", "FX-MVP")
	if OS.get_environment("DMB_SEED") == "":
		OS.set_environment("DMB_SEED", "507")
	var shell = Shell.new()
	root.add_child(shell)
	var deadline := Time.get_ticks_msec() + 45000
	while Time.get_ticks_msec() < deadline and not shell.is_village_ready():
		await process_frame
	if not shell.is_booted() or not shell.is_village_ready():
		_fail("shell not ready")
		return
	await _capture("settlement_boot")
	# World map if available.
	if shell.has_method("_toggle_world_map"):
		shell._toggle_world_map()
		await create_timer(0.4).timeout
		await _capture("world_map_open")
		if shell.has_method("_toggle_world_map"):
			shell._toggle_world_map()
	print("VISUAL_REVIEW_OK fixture=%s" % OS.get_environment("DMB_FIXTURE"))
	quit(0)
