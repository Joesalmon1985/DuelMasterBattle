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
	await create_timer(0.8).timeout
	# Before production units exist.
	_save(out_dir, "screenshot_450x800.png")
	_save(out_dir.path_join("screenshots"), "before_production.png")
	_save(out_dir, "screenshot_wizard.png")
	# Advance authoritative production so units appear.
	var view: Dictionary = shell._client.request_view("economy", ["clock", "units"])
	var seq := int(view.get("clock", {}).get("clock_sequence", 0))
	for index in range(10):
		seq += 1
		shell._client.send_command(
			"capture-advance-%d" % index,
			"AdvanceGame",
			{"delta_ms": 10000, "clock_sequence": seq},
		)
	await create_timer(1.0).timeout
	var units_view: Dictionary = shell._client.request_view("economy", ["units", "industry", "fx_industry"])
	var unit_n: int = units_view.get("units", {}).size()
	if shell._economy:
		shell._economy.refresh(true)
	await create_timer(0.8).timeout
	_save(out_dir.path_join("screenshots"), "after_unit_production.png")
	print("G03_CAPTURE units_after_advance=", unit_n)
	# Obstruction: place wizard on the worker and toggle manual block.
	if shell._area and shell._area._wizard and shell._workers:
		var worker = shell._workers.worker_for_person(
			str((shell._economy._last_view.get("industry_workers", [{}])[0]).get("person_id", ""))
		)
		if worker:
			shell._area._wizard.global_position = worker.global_position
			shell._workers.set_wizard_world_position(worker.global_position)
	shell._manual_path_block = true
	if shell._workers:
		shell._workers.set_manual_path_block(true)
	await create_timer(0.6).timeout
	_save(out_dir.path_join("screenshots"), "worker_path_blocked.png")
	shell._manual_path_block = false
	if shell._workers:
		shell._workers.set_manual_path_block(false)
	shell._client.send_command("capture-damage", "Interact", {"action": "industry_damage"})
	await create_timer(0.4).timeout
	shell._client.send_command("capture-strike", "Interact", {"action": "industry_strike"})
	await create_timer(0.5).timeout
	if shell._economy:
		shell._economy.refresh(true)
	await create_timer(0.4).timeout
	_save(out_dir.path_join("screenshots"), "damaged_bottleneck.png")
	_save(out_dir.path_join("screenshots"), "strike_stopped.png")
	print("G03_CAPTURE_OK before after blocked damaged strike")
	if shell._launcher:
		shell._launcher.stop()
	quit(0)


func _save(dir: String, name: String) -> void:
	var image := get_root().get_viewport().get_texture().get_image()
	var error := image.save_png(dir.path_join(name))
	if error != OK:
		push_error("G03 capture failed: %s" % name)
