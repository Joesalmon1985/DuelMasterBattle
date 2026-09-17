extends SceneTree

## Capture real G02 FX-CARGO gameplay frames (not text placeholders).

const Migrated = preload("res://client/core/migrated_runtime.gd")
const G02Shell = preload("res://client/scenes/g02_shell.gd")


func _init() -> void:
	call_deferred("_go")


func _go() -> void:
	Migrated.enable()
	OS.set_environment("DMB_FIXTURE", "FX-CARGO")
	OS.set_environment("DMB_SEED", "202")

	var project_root := ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if project_root.ends_with("godot_project"):
		project_root = project_root.get_base_dir()
	var out_dir := project_root.path_join("Pack/DuelMasterBattle_Build_Pack/tracking/gates/G02")
	var shot_dir := out_dir.path_join("screenshots")
	DirAccess.make_dir_recursive_absolute(shot_dir)

	var w := int(DisplayServer.window_get_size().x)
	var h := int(DisplayServer.window_get_size().y)
	var shell: Control = G02Shell.new()
	root.add_child(shell)
	await create_timer(3.0).timeout
	if shell.has_method("_force_playable_focus"):
		shell._force_playable_focus()
	if shell.has_method("_fit_world_host"):
		shell._fit_world_host()
	await create_timer(0.4).timeout

	if shell._client == null or shell._area == null:
		push_error("G02 capture: shell failed to boot")
		quit(1)
		return

	# Ensure economy panel expanded so warehouse/cart are visible in the frame.
	if shell._economy != null:
		shell._economy._expanded = true
		shell._economy._apply_expanded()
		shell._economy.refresh()
	await create_timer(0.2).timeout

	var dims := _save(out_dir, "screenshot_%dx%d.png" % [w, h])
	print("G02_CAPTURE_OK screenshot_%dx%d.png capture=%dx%d" % [w, h, dims.x, dims.y])
	if w == 450 and h == 800:
		_save(out_dir, "screenshot_wizard.png")
		_save(shot_dir, "warehouse_cart.png")
		print("G02_CAPTURE_OK warehouse_cart.png capture=%dx%d" % [dims.x, dims.y])

		# Blocked-route gameplay frame
		shell._client.send_command("cap-start", "Interact", {"action": "start_delivery"})
		shell._client.send_command("cap-block", "Interact", {"action": "place_route_block"})
		var node := str(shell._client.request_view("player").get("player", {}).get("node_id", "node:1"))
		shell._client.send_command("cap-w1", "Wait", {"current_node": node, "press_id": "cap-w1"})
		if shell._economy:
			shell._economy.refresh()
		shell._refresh_counters(false)
		await create_timer(0.35).timeout
		var blocked := _save(shot_dir, "blocked_route.png")
		print("G02_CAPTURE_OK blocked_route.png capture=%dx%d" % [blocked.x, blocked.y])

	if shell._launcher:
		shell._launcher.stop()
	quit(0)


func _save(dir: String, name: String) -> Vector2i:
	var img: Image = get_root().get_viewport().get_texture().get_image()
	var path := dir.path_join(name)
	var err := img.save_png(path)
	if err != OK:
		push_error("capture failed %s err=%s" % [name, err])
		return Vector2i.ZERO
	return Vector2i(img.get_width(), img.get_height())
