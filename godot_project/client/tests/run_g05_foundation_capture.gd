extends SceneTree

## Capture Village Foundation baseline viewport (+ optional full-settlement note).


func _init() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-VILLAGE")
	if OS.get_environment("DMB_SEED").is_empty():
		OS.set_environment("DMB_SEED", "507")
	call_deferred("_go")


func _go() -> void:
	var project_root := ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if project_root.ends_with("godot_project"):
		project_root = project_root.get_base_dir()
	var out_dir := project_root.path_join("Pack/DuelMasterBattle_Build_Pack/tracking/gates/G05")
	var packed = load("res://client/scenes/g05_shell.tscn")
	var scene = packed.instantiate()
	root.add_child(scene)
	await create_timer(4.0).timeout
	if scene.has_method("_fit_world_host"):
		scene._fit_world_host()
	await create_timer(0.5).timeout
	var img: Image = get_root().get_viewport().get_texture().get_image()
	var path := out_dir.path_join("village_foundation.png")
	var err := img.save_png(path)
	if err != OK:
		push_error("foundation capture failed err=%s" % err)
		quit(1)
		return
	img.save_png(out_dir.path_join("play_inspect.png"))
	print("G05_FOUNDATION_CAPTURE_OK ", path, " size=", img.get_width(), "x", img.get_height())
	quit(0)
