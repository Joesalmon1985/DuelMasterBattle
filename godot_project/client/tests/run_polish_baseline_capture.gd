extends SceneTree

## P0/P9 polish baseline + SB frames from FX-MVP seed 507.
## Env: DMB_SHOT_DIR, DMB_CAPTURE_IDS (comma list, default B01,B02,B03)

const Shell = preload("res://client/scenes/g05_shell.gd")


func _init() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-MVP")
	if OS.get_environment("DMB_SEED").is_empty():
		OS.set_environment("DMB_SEED", "507")
	call_deferred("_run")


func _shot_dir() -> String:
	var env := OS.get_environment("DMB_SHOT_DIR")
	if env != "":
		# Resolve relative paths against project root (parent of godot_project).
		if env.is_absolute_path():
			return env
		var project_root := ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
		if project_root.ends_with("godot_project"):
			project_root = project_root.get_base_dir()
		return project_root.path_join(env)
	return ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir().path_join(
		"Pack/DuelMasterBattle_Build_Pack/tracking/polish/captures"
	)


func _ids() -> PackedStringArray:
	var raw := OS.get_environment("DMB_CAPTURE_IDS")
	if raw == "":
		return PackedStringArray(["B01", "B02", "B03"])
	return raw.split(",", false)


func _capture(name: String) -> void:
	await process_frame
	await process_frame
	var img: Image = get_root().get_viewport().get_texture().get_image()
	if img == null:
		push_error("no image %s" % name)
		quit(1)
		return
	var dir := _shot_dir()
	DirAccess.make_dir_recursive_absolute(dir)
	var res := DisplayServer.window_get_size()
	var path := dir.path_join("%s_%dx%d.png" % [name, res.x, res.y])
	var err := img.save_png(path)
	if err != OK:
		push_error("save failed %s" % path)
		quit(1)
		return
	print("POLISH_SHOT %s %dx%d" % [path, img.get_width(), img.get_height()])


func _wait_ready(shell, timeout_ms: int = 60000) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if shell.has_method("is_village_ready") and shell.is_village_ready():
			return true
		if shell.get("_boot_done") == true and shell.get("_client") != null:
			return true
		await process_frame
	return false


func _run() -> void:
	var packed = load("res://client/scenes/g05_shell.tscn")
	if packed == null:
		# Script-only shell fallback
		var shell = Shell.new()
		root.add_child(shell)
		if not await _wait_ready(shell):
			push_error("shell not ready")
			quit(1)
			return
		await _sequence(shell)
		quit(0)
		return
	var scene = packed.instantiate()
	root.add_child(scene)
	if not await _wait_ready(scene):
		push_error("shell not ready")
		quit(1)
		return
	await _sequence(scene)
	print("POLISH_CAPTURE_OK")
	quit(0)


func _sequence(shell) -> void:
	var want := _ids()
	if "B01" in want or "SB01" in want or "SB02" in want:
		await _capture("B01")
	if "B02" in want:
		if shell.has_method("invoke_map_for_test"):
			shell.invoke_map_for_test()
		elif shell.has_method("_toggle_map"):
			shell._toggle_map()
		await process_frame
		await process_frame
		await _capture("B02")
		if shell.has_method("_toggle_map"):
			shell._toggle_map()
	if "B03" in want:
		# Best-effort Observe nearby person via test hooks if present
		if shell.has_method("invoke_observe_nearest_for_test"):
			shell.invoke_observe_nearest_for_test()
		await process_frame
		await process_frame
		await _capture("B03")
	if "SB01" in want or "SB02" in want:
		if shell.has_method("_toggle_spellbook"):
			shell._toggle_spellbook()
		await process_frame
		await process_frame
		await _capture("SB02" if OS.get_environment("DMB_PLAYTEST_REVIEW") == "1" else "SB01")
