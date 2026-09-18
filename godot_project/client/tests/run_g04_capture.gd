extends SceneTree

const BattleShell = preload("res://client/scenes/g04_battle_shell.gd")
const HazardShell = preload("res://client/scenes/g04_hazard_shell.gd")


func _init() -> void:
	call_deferred("_go")


func _go() -> void:
	var project_root := ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if project_root.ends_with("godot_project"):
		project_root = project_root.get_base_dir()
	var out_dir := project_root.path_join("Pack/DuelMasterBattle_Build_Pack/tracking/gates/G04")
	DirAccess.make_dir_recursive_absolute(out_dir.path_join("screenshots"))

	OS.set_environment("DMB_FIXTURE", "FX-BATTLE")
	OS.set_environment("DMB_SEED", "404")
	var battle: Control = BattleShell.new()
	root.add_child(battle)
	await create_timer(2.5).timeout
	if battle.has_method("_force_playable_focus"):
		battle._force_playable_focus()
	await create_timer(0.5).timeout
	_save(out_dir, "screenshot_battle_450x800.png")
	_save(out_dir.path_join("screenshots"), "battle_labelled_units.png")
	_save(out_dir, "screenshot_450x800.png")
	battle.queue_free()
	await create_timer(0.4).timeout

	OS.set_environment("DMB_FIXTURE", "FX-HAZARD")
	OS.set_environment("DMB_SEED", "408")
	var hazard: Control = HazardShell.new()
	root.add_child(hazard)
	await create_timer(2.5).timeout
	if hazard.has_method("_force_playable_focus"):
		hazard._force_playable_focus()
	await create_timer(0.5).timeout
	_save(out_dir, "screenshot_hazard_450x800.png")
	_save(out_dir.path_join("screenshots"), "hazard_hexes_treatment.png")
	_save(out_dir, "screenshot_wizard.png")
	# Landscape capture via viewport size change if supported.
	DisplayServer.window_set_size(Vector2i(1280, 720))
	await create_timer(0.4).timeout
	_save(out_dir, "screenshot_1280x720.png")
	DisplayServer.window_set_size(Vector2i(720, 1280))
	await create_timer(0.4).timeout
	_save(out_dir, "screenshot_720x1280.png")
	print("G04_CAPTURE_OK")
	quit(0)


func _save(dir: String, name: String) -> void:
	await create_timer(0.05).timeout
	var img: Image = get_root().get_viewport().get_texture().get_image()
	var path := dir.path_join(name)
	var error := img.save_png(path)
	if error != OK:
		push_error("G04 capture failed: %s" % name)
	else:
		print("wrote ", path)
