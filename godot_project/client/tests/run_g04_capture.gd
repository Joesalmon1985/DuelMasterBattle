extends SceneTree

## Capture real rendered G04 gameplay frames (requires a working display).

const BattleShell = preload("res://client/scenes/g04_battle_shell.gd")
const HazardShell = preload("res://client/scenes/g04_hazard_shell.gd")

const OUT := "res://../Pack/DuelMasterBattle_Build_Pack/tracking/gates/G04"


func _init() -> void:
	call_deferred("_go")


func _go() -> void:
	DisplayServer.window_set_size(Vector2i(450, 800))
	OS.set_environment("DMB_FIXTURE", "FX-BATTLE")
	OS.set_environment("DMB_SEED", "404")
	var battle: Control = BattleShell.new()
	root.add_child(battle)
	await create_timer(2.5).timeout
	if battle._client == null or not battle._lease_opened:
		push_error("G04_CAPTURE battle lease failed")
		quit(1)
		return
	# Let combat animate
	await create_timer(2.5).timeout
	await _capture(battle, "screenshot_battle_450x800.png")
	await _capture(battle, "screenshot_450x800.png")
	# Combat sequence frames
	for i in range(4):
		await create_timer(0.6).timeout
		await _capture(battle, "screenshots/combat_%02d.png" % i)
	if battle._unit_nodes.size() > 0:
		var uid := str(battle._unit_nodes.keys()[0])
		battle._select_unit(uid)
		await create_timer(0.2).timeout
		await _capture(battle, "screenshot_wizard.png")
	battle.queue_free()
	await create_timer(0.3).timeout

	OS.set_environment("DMB_FIXTURE", "FX-HAZARD")
	OS.set_environment("DMB_SEED", "408")
	var hazard: Control = HazardShell.new()
	root.add_child(hazard)
	await create_timer(2.5).timeout
	if hazard._client:
		var hview: Dictionary = hazard._client.request_view_blocking(
			"player", ["hazards", "fx_hazard", "player", "clock", "board", "leases"]
		)
		print("G04_CAPTURE hazard view keys=", hview.keys(), " hazards=", hview.get("hazards", {}).keys() if hview.get("hazards") else [])
		hazard._apply_hazard_view(hview)
		print("G04_CAPTURE hex_nodes=", hazard._hex_nodes.size())
	await create_timer(0.5).timeout
	await _capture(hazard, "screenshot_hazard_450x800.png")
	if hazard._hex_nodes.is_empty() and hazard._client:
		# Retry once after another blocking view
		var retry: Dictionary = hazard._client.request_view("player", ["hazards", "fx_hazard"])
		hazard._apply_hazard_view(retry)
		print("G04_CAPTURE retry nodes=", hazard._hex_nodes.size(), " cubes=", (retry.get("hazards", {}).get("catastrophe", {}) as Dictionary).get("cubes", {}).size())
	if hazard._hex_nodes.size() > 0:
		var cid := str(hazard._hex_nodes.keys()[0])
		hazard._selected_cube = cid
		for id in hazard._hex_nodes.keys():
			hazard._hex_nodes[id].set_selected(id == cid)
		await create_timer(0.2).timeout
		await _capture(hazard, "screenshots/hazard_selected.png")
		hazard._on_duel_requested(cid)
		await create_timer(0.5).timeout
		await _capture(hazard, "screenshots/hazard_duel.png")
		hazard._duel_action("channel")
		await create_timer(0.25).timeout
		await _capture(hazard, "screenshots/hazard_channel.png")
	else:
		push_warning("G04_CAPTURE no hazard nodes after refresh")
	# Landscape layout check
	DisplayServer.window_set_size(Vector2i(1280, 720))
	await create_timer(0.4).timeout
	await _capture(hazard, "screenshot_1280x720.png")
	print("G04_CAPTURE_OK nodes=", hazard._hex_nodes.size())
	quit(0)


func _capture(node: Node, rel: String) -> void:
	await process_frame
	await process_frame
	var img: Image = root.get_viewport().get_texture().get_image()
	if img == null or img.get_width() < 8:
		push_warning("viewport capture empty for %s" % rel)
		return
	var path := ProjectSettings.globalize_path(OUT.path_join(rel))
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var err := img.save_png(path)
	print("captured ", path, " err=", err, " size=", img.get_width(), "x", img.get_height())
