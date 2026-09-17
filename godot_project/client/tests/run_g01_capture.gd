extends SceneTree

## Capture one G01 viewport frame. Window size comes from --resolution / env.

func _init() -> void:
	call_deferred("_go")


func _go() -> void:
	var project_root := ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if project_root.ends_with("godot_project"):
		project_root = project_root.get_base_dir()
	var out_dir := project_root.path_join("Pack/DuelMasterBattle_Build_Pack/tracking/gates/G01")
	var w := int(DisplayServer.window_get_size().x)
	var h := int(DisplayServer.window_get_size().y)
	var packed = load("res://client/scenes/g01_shell.tscn")
	var scene = packed.instantiate()
	root.add_child(scene)
	await create_timer(2.8).timeout
	# Force a layout pass after shell ready.
	if scene.has_method("_fit_world_host"):
		scene._fit_world_host()
	await create_timer(0.2).timeout
	var img: Image = get_root().get_viewport().get_texture().get_image()
	var name := "screenshot_%dx%d.png" % [w, h]
	var path := out_dir.path_join(name)
	var err := img.save_png(path)
	if err != OK:
		push_error("capture failed %s err=%s" % [name, err])
		quit(1)
		return
	if w == 720 and h == 1280:
		img.save_png(out_dir.path_join("screenshot_wizard.png"))
	print("G01_CAPTURE_OK ", name, " size=", img.get_width(), "x", img.get_height())
	quit(0)
