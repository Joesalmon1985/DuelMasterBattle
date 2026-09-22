extends SceneTree

## Single-resolution FX-ERA layout capture. Args: WxH out_dir

const Shell = preload("res://client/scenes/g05_shell.gd")


func _init() -> void:
	call_deferred("_go")


func _go() -> void:
	var args := OS.get_cmdline_user_args()
	var res_str := "450x800"
	var out_dir := ""
	if args.size() >= 1:
		res_str = str(args[0])
	if args.size() >= 2:
		out_dir = str(args[1])
	var parts := res_str.split("x")
	var w := int(parts[0]) if parts.size() >= 1 else 450
	var h := int(parts[1]) if parts.size() >= 2 else 800
	DisplayServer.window_set_size(Vector2i(w, h))
	OS.set_environment("DMB_FIXTURE", "FX-ERA")
	OS.set_environment("DMB_SEED", "507")
	OS.set_environment("DMB_SAVE_SLOT", "fx_era_layout_capture")
	if out_dir == "":
		var project_root := ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
		if project_root.ends_with("godot_project"):
			project_root = project_root.get_base_dir()
		out_dir = project_root.path_join(
			"Pack/DuelMasterBattle_Build_Pack/tracking/gates/G06/layout_captures"
		)
	DirAccess.make_dir_recursive_absolute(out_dir)
	var shell = Shell.new()
	root.add_child(shell)
	var deadline := Time.get_ticks_msec() + 45000
	while Time.get_ticks_msec() < deadline and not shell.is_booted():
		await process_frame
	if not shell.is_booted():
		print("FX_ERA_CAPTURE_FAIL boot")
		quit(1)
		return
	if shell.has_method("_layout_fx_era_panel"):
		shell._layout_fx_era_panel()
	await create_timer(0.5).timeout
	var tag := "%dx%d" % [w, h]
	_save(out_dir, "village_%s.png" % tag)
	shell.invoke_world_map_for_test()
	await create_timer(0.6).timeout
	_save(out_dir, "world_map_%s.png" % tag)
	shell.invoke_world_map_for_test()
	await process_frame
	shell.invoke_chronicle_for_test()
	await create_timer(0.5).timeout
	_save(out_dir, "chronicle_%s.png" % tag)
	print("FX_ERA_CAPTURE_OK ", tag, " dir=", out_dir)
	quit(0)


func _save(out_dir: String, name: String) -> void:
	var img: Image = get_root().get_viewport().get_texture().get_image()
	if img == null:
		push_error("no image for %s" % name)
		return
	var path := out_dir.path_join(name)
	var err := img.save_png(path)
	if err != OK:
		push_error("save failed %s" % name)
		return
	print("FX_ERA_CAPTURE_FRAME ", name, " ", img.get_width(), "x", img.get_height())
