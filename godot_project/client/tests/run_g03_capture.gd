extends SceneTree

const G03Shell = preload("res://client/scenes/g03_shell.gd")


func _init() -> void:
	call_deferred("_go")


func _go() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-INDUSTRY")
	OS.set_environment("DMB_SEED", "303")
	var project_root := ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if project_root.ends_with("godot_project"):
		project_root = project_root.get_base_dir()
	var out_dir := project_root.path_join("Pack/DuelMasterBattle_Build_Pack/tracking/gates/G03")
	DirAccess.make_dir_recursive_absolute(out_dir.path_join("screenshots"))
	var shell: Control = G03Shell.new()
	root.add_child(shell)
	await create_timer(3.0).timeout
	shell._force_playable_focus()
	await create_timer(0.5).timeout
	_save(out_dir, "screenshot_450x800.png")
	_save(out_dir, "screenshot_wizard.png")
	shell._manual_path_block = true
	await create_timer(0.4).timeout
	_save(out_dir.path_join("screenshots"), "worker_path_blocked.png")
	shell._client.send_command("capture-damage", "Interact", {"action": "industry_damage"})
	await create_timer(0.6).timeout
	if shell._economy:
		shell._economy.refresh(true)
	await create_timer(0.4).timeout
	_save(out_dir.path_join("screenshots"), "damaged_bottleneck.png")
	print("G03_CAPTURE_OK 450x800 worker_path_blocked damaged_bottleneck")
	if shell._launcher:
		shell._launcher.stop()
	quit(0)


func _save(dir: String, name: String) -> void:
	var image := get_root().get_viewport().get_texture().get_image()
	var error := image.save_png(dir.path_join(name))
	if error != OK:
		push_error("G03 capture failed: %s" % name)
