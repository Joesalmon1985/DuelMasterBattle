extends SceneTree

## Capture G01 shell screenshots at required viewports.

const SIZES := [
	Vector2i(450, 800),
	Vector2i(720, 1280),
	Vector2i(1280, 720),
]


func _init() -> void:
	call_deferred("_go")


func _go() -> void:
	var project_root := ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if project_root.ends_with("godot_project"):
		project_root = project_root.get_base_dir()
	var out_dir := project_root.path_join("Pack/DuelMasterBattle_Build_Pack/tracking/gates/G01")
	var packed = load("res://client/scenes/g01_shell.tscn")
	var scene = packed.instantiate()
	root.add_child(scene)
	await create_timer(2.8).timeout
	var ok_count := 0
	for size in SIZES:
		DisplayServer.window_set_size(size)
		await create_timer(0.35).timeout
		var img: Image = get_root().get_viewport().get_texture().get_image()
		var name := "screenshot_%dx%d.png" % [size.x, size.y]
		var path := out_dir.path_join(name)
		var err := img.save_png(path)
		if err == OK:
			ok_count += 1
			print("G01_CAPTURE_OK ", name)
		else:
			push_error("capture failed %s err=%s" % [name, err])
	# Keep canonical alias for packet.
	var primary := out_dir.path_join("screenshot_720x1280.png")
	var alias := out_dir.path_join("screenshot_wizard.png")
	if FileAccess.file_exists(primary):
		var img2 := Image.load_from_file(primary)
		if img2:
			img2.save_png(alias)
	if ok_count < SIZES.size():
		quit(1)
		return
	print("G01_CAPTURE_ALL_OK count=", ok_count)
	quit(0)
