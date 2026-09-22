extends SceneTree

## Capture FX-ERA responsive UI screenshots for G06 early checkpoint.
## Prefer headed for accurate GLES; headless still saves frames when possible.

const Shell = preload("res://client/scenes/g05_shell.gd")

const SIZES := [
	Vector2i(450, 800),
	Vector2i(960, 540),
	Vector2i(1280, 720),
]


func _init() -> void:
	call_deferred("_go")


func _force_size(size: Vector2i) -> void:
	DisplayServer.window_set_size(size)
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	var win := get_root()
	win.size = size
	# content_scale keeps logical layout matching the requested resolution.
	win.content_scale_size = size
	win.content_scale_mode = Window.CONTENT_SCALE_MODE_DISABLED


func _go() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-ERA")
	OS.set_environment("DMB_SEED", "507")
	OS.set_environment("DMB_SAVE_SLOT", "fx_era_layout_capture")
	var project_root := ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if project_root.ends_with("godot_project"):
		project_root = project_root.get_base_dir()
	var out_dir := project_root.path_join(
		"Pack/DuelMasterBattle_Build_Pack/tracking/gates/G06/layout_captures"
	)
	DirAccess.make_dir_recursive_absolute(out_dir)
	var shell = Shell.new()
	root.add_child(shell)
	var deadline := Time.get_ticks_msec() + 45000
	while Time.get_ticks_msec() < deadline and not shell.is_booted():
		await process_frame
	if not shell.is_booted():
		push_error("FX-ERA shell failed to boot for capture")
		print("FX_ERA_CAPTURE_FAIL")
		quit(1)
		return
	var ok := 0
	for size in SIZES:
		_force_size(size)
		await process_frame
		await process_frame
		await process_frame
		if shell.has_method("_layout_fx_era_panel"):
			shell._layout_fx_era_panel()
		await create_timer(0.45).timeout
		var got := get_root().get_viewport().get_visible_rect().size
		print("FX_ERA_CAPTURE_VP requested=", size, " visible=", got)
		ok += _save(out_dir, "village_%dx%d.png" % [size.x, size.y])
		shell.invoke_world_map_for_test()
		await create_timer(0.55).timeout
		ok += _save(out_dir, "world_map_%dx%d.png" % [size.x, size.y])
		shell.invoke_world_map_for_test()
		await process_frame
		shell.invoke_chronicle_for_test()
		await create_timer(0.45).timeout
		ok += _save(out_dir, "chronicle_%dx%d.png" % [size.x, size.y])
		shell.invoke_chronicle_for_test()
		await process_frame
	print("FX_ERA_CAPTURE_OK count=", ok, " dir=", out_dir)
	quit(0 if ok >= SIZES.size() else 1)


func _save(out_dir: String, name: String) -> int:
	await process_frame
	var img: Image = get_root().get_viewport().get_texture().get_image()
	if img == null:
		push_error("no viewport image for %s" % name)
		return 0
	var path := out_dir.path_join(name)
	var err := img.save_png(path)
	if err != OK:
		push_error("save failed %s err=%s" % [name, err])
		return 0
	print("FX_ERA_CAPTURE_FRAME ", name, " ", img.get_width(), "x", img.get_height())
	return 1
