extends SceneTree

## In-world visual review harness — real G05/G04 presentation, not a badge gallery.
## Captures deterministic owner-review frames for terrain, settlement, military,
## local combat, Ward Duel, hazards, era, and world map legibility.
##
## Env:
##   DMB_VISUAL_REVIEW_SUITE = settlement|map|combat|hazard|era|ward|all (default all)
##   DMB_SHOT_DIR = output directory
##   DMB_FIXTURE / DMB_SEED overridden per scenario
##
## godot --path godot_project --resolution 450x800 --script res://client/tests/run_visual_review_harness.gd

const Shell = preload("res://client/scenes/g05_shell.gd")
const BattleShell = preload("res://client/scenes/g04_battle_shell.gd")
const HazardShell = preload("res://client/scenes/g04_hazard_shell.gd")

var _shot_count := 0


func _init() -> void:
	call_deferred("_run")


func _fail(msg: String) -> void:
	push_error(msg)
	print("VISUAL_REVIEW_FAIL %s" % msg)
	quit(1)


func _suite() -> String:
	var s := OS.get_environment("DMB_VISUAL_REVIEW_SUITE")
	return s if s != "" else "all"


func _shot_dir() -> String:
	var env := OS.get_environment("DMB_SHOT_DIR")
	if env != "":
		return env
	return ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir().path_join(
		"Pack/DuelMasterBattle_Build_Pack/tracking/gates/G11/visual_review"
	)


func _capture(name: String) -> void:
	await process_frame
	await process_frame
	var img: Image = get_root().get_viewport().get_texture().get_image()
	if img == null:
		push_warning("no image for %s" % name)
		return
	var dir := _shot_dir()
	DirAccess.make_dir_recursive_absolute(dir)
	var res := DisplayServer.window_get_size()
	var path := dir.path_join("%s_%dx%d.png" % [name, res.x, res.y])
	var err := img.save_png(path)
	if err != OK:
		push_warning("save failed %s" % path)
		return
	_shot_count += 1
	print("VISUAL_REVIEW_SHOT %s" % path)


func _wait_ready(shell, timeout_ms: int = 45000) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if shell.has_method("is_village_ready") and shell.is_village_ready():
			return true
		if shell.get("_boot_done") == true and shell.get("_client") != null:
			# G04 shells
			return true
		await process_frame
	return false


func _clear_root() -> void:
	for child in root.get_children():
		child.queue_free()
	await process_frame
	await process_frame


func _run_settlement_and_map() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-WORLD-LAYERS")
	OS.set_environment("DMB_SEED", "507")
	OS.set_environment("DMB_SAVE_SLOT", "visual_review_layers")
	var shell = Shell.new()
	root.add_child(shell)
	if not await _wait_ready(shell):
		_fail("FX-WORLD-LAYERS not ready")
		return
	await create_timer(0.6).timeout
	await _capture("settlement_workers_production")
	# World map — node numbers must remain readable.
	if shell.has_method("_toggle_world_map") or shell.has_method("_open_world_map_now"):
		if shell.has_method("_open_world_map_now"):
			shell._open_world_map_now()
		else:
			shell._toggle_world_map()
		await create_timer(0.5).timeout
		await _capture("world_map_nodes_readable")
		if shell.has_method("_toggle_world_map"):
			shell._toggle_world_map()
	# Travel west for wilderness / terrain sample.
	if shell.has_method("travel_to_node"):
		shell.travel_to_node("node:35", "node:30")
		await create_timer(0.8).timeout
		await _capture("terrain_wilderness_sample")
	await _clear_root()


func _run_mvp_era_map() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-ERA")
	OS.set_environment("DMB_SEED", "507")
	OS.set_environment("DMB_SAVE_SLOT", "visual_review_era")
	var shell = Shell.new()
	root.add_child(shell)
	if not await _wait_ready(shell):
		_fail("FX-ERA not ready")
		return
	await create_timer(0.6).timeout
	await _capture("era_near_historic_panel")
	if shell.has_method("_open_world_map_now"):
		shell._open_world_map_now()
		await create_timer(0.5).timeout
		await _capture("era_world_map")
	await _clear_root()


func _run_local_combat() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-BATTLE")
	OS.set_environment("DMB_SEED", "404")
	OS.set_environment("DMB_SAVE_SLOT", "visual_review_battle")
	var battle: Control = BattleShell.new()
	root.add_child(battle)
	await create_timer(2.5).timeout
	await _capture("local_combat_military_shapes")
	await _clear_root()


func _run_hazards() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-HAZARD")
	OS.set_environment("DMB_SEED", "408")
	OS.set_environment("DMB_SAVE_SLOT", "visual_review_hazard")
	var hazard: Control = HazardShell.new()
	root.add_child(hazard)
	await create_timer(2.5).timeout
	await _capture("hazards_manifestations")
	await _clear_root()


func _run_ward_duel() -> void:
	## Reuse FX-MVP path to a challengeable cube; assert clean duel frame.
	OS.set_environment("DMB_FIXTURE", "FX-MVP")
	OS.set_environment("DMB_SEED", "507")
	OS.set_environment("DMB_SAVE_SLOT", "visual_review_ward")
	var shell = Shell.new()
	root.add_child(shell)
	if not await _wait_ready(shell):
		_fail("FX-MVP not ready for ward")
		return
	var path := ["node:35", "node:30", "node:36", "node:31", "node:37"]
	for i in range(path.size() - 1):
		if not shell.travel_to_node(str(path[i]), str(path[i + 1])):
			_fail("travel failed on ward path")
			return
		await process_frame
	await _capture("ward_before_challenge")
	if not shell.start_hazard_challenge("cube:1"):
		_fail("ward challenge failed")
		return
	await create_timer(0.6).timeout
	var clean: Dictionary = shell.presentation_assert_ward_clean()
	if not bool(clean.get("ok", false)):
		_fail("ward leaks: %s" % str(clean.get("leaks")))
		return
	await _capture("ward_duel_clean")
	await _clear_root()


func _run() -> void:
	var suite := _suite()
	DirAccess.make_dir_recursive_absolute(_shot_dir())
	if suite in ["all", "settlement", "map"]:
		await _run_settlement_and_map()
	if suite in ["all", "era"]:
		await _run_mvp_era_map()
	if suite in ["all", "combat"]:
		await _run_local_combat()
	if suite in ["all", "hazard"]:
		await _run_hazards()
	if suite in ["all", "ward"]:
		await _run_ward_duel()
	if _shot_count < 1:
		_fail("no screenshots captured")
		return
	print("VISUAL_REVIEW_OK shots=%s suite=%s" % [_shot_count, suite])
	quit(0)
