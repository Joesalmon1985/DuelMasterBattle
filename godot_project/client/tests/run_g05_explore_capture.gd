extends SceneTree

## Capture G05 full-world exploration frames: home, wilderness, road, other settlement.


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
	var deadline := Time.get_ticks_msec() + 25000
	while Time.get_ticks_msec() < deadline:
		if scene.has_method("is_village_ready") and scene.is_village_ready():
			break
		await process_frame
	if not (scene.has_method("is_village_ready") and scene.is_village_ready()):
		push_error("shell not ready")
		quit(1)
		return
	await create_timer(1.5).timeout
	if scene.has_method("_fit_world_host"):
		scene._fit_world_host()
	await create_timer(0.3).timeout
	_snap(out_dir, "explore_start_settlement.png")

	# Wilderness neighbour of home (node:35 → node:30).
	if not scene.travel_to_node("node:35", "node:30"):
		push_error("travel to wilderness failed")
		quit(1)
		return
	await create_timer(1.0).timeout
	if scene.has_method("_fit_world_host"):
		scene._fit_world_host()
	_snap(out_dir, "explore_wilderness.png")

	# Road junction approach: node:30 → node:35 → node:29 (road endpoint).
	if not scene.travel_to_node("node:30", "node:35"):
		push_error("return home failed")
		quit(1)
		return
	if not scene.travel_to_node("node:35", "node:29"):
		push_error("travel to road node failed")
		quit(1)
		return
	await create_timer(1.0).timeout
	if scene.has_method("_fit_world_host"):
		scene._fit_world_host()
	_snap(out_dir, "explore_road_node.png")

	# Reach second settlement settlement:4 @ node:27 via short path.
	# node:29 → node:23 → … use known short path from board map:
	# From 29: go toward 27 via 23? Actually 27 neighbours 21,33.
	# Path from 29: 29-23-17-12 is settlement1; better 35-30-24-19-25-20-26-21-27
	var path := [
		["node:29", "node:23"],
		["node:23", "node:18"],
		["node:18", "node:24"],
		["node:24", "node:19"],
		["node:19", "node:25"],
		["node:25", "node:20"],
		["node:20", "node:26"],
		["node:26", "node:21"],
		["node:21", "node:27"],
	]
	for step in path:
		if not scene.travel_to_node(str(step[0]), str(step[1])):
			push_error("path travel failed %s→%s" % [step[0], step[1]])
			quit(1)
			return
		await process_frame
	await create_timer(1.2).timeout
	if scene.has_method("_fit_world_host"):
		scene._fit_world_host()
	_snap(out_dir, "explore_second_settlement.png")
	# Also refresh classic packet names.
	_snap(out_dir, "play_inspect.png")
	print("G05_EXPLORE_CAPTURE_OK")
	quit(0)


func _snap(out_dir: String, filename: String) -> void:
	var img: Image = get_root().get_viewport().get_texture().get_image()
	var path := out_dir.path_join(filename)
	var err := img.save_png(path)
	if err != OK:
		push_error("capture failed %s err=%s" % [filename, err])
	else:
		print("captured ", path, " ", img.get_width(), "x", img.get_height())
