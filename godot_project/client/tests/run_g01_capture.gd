extends SceneTree

## Capture one frame of the playable G01 shell for the gate packet.

func _init() -> void:
	call_deferred("_go")

func _go() -> void:
	var packed = load("res://client/scenes/g01_shell.tscn")
	var scene = packed.instantiate()
	root.add_child(scene)
	await create_timer(2.5).timeout
	var img: Image = get_root().get_viewport().get_texture().get_image()
	var path := ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if path.ends_with("godot_project"):
		path = path.get_base_dir()
	path = path.path_join("Pack/DuelMasterBattle_Build_Pack/tracking/gates/G01/screenshot_wizard.png")
	var err := img.save_png(path)
	print("G01_CAPTURE path=", path, " err=", err)
	quit(0 if err == OK else 1)
