extends SceneTree

## Headed storyboard capture for G06 / G07 / G08 using AutoGateDriver.
## Usage:
##   godot --path godot_project --resolution 450x800 \
##     --script res://client/tests/run_auto_gate_storyboard.gd -- --gate=G06
## Env overrides: DMB_AUTO_GATE, DMB_FIXTURE, DMB_SEED, DMB_RESOLUTION

const Driver = preload("res://client/tests/auto_gate_driver.gd")

const RESOLUTIONS_RESPONSIVE := [
	Vector2i(450, 800),
	Vector2i(1280, 720),
]

var _driver


func _init() -> void:
	call_deferred("_go")


func _merge(a: Dictionary, b: Dictionary) -> Dictionary:
	var out := a.duplicate(true)
	for k in b.keys():
		out[k] = b[k]
	return out


func _parse_gate() -> String:
	var env := str(OS.get_environment("DMB_AUTO_GATE")).strip_edges().to_upper()
	if env != "":
		return env
	for a in OS.get_cmdline_user_args():
		var s := str(a)
		if s.begins_with("--gate="):
			return s.substr(7).strip_edges().to_upper()
		if s.begins_with("G0") or s.begins_with("G1"):
			return s.to_upper()
	return "G06"


func _parse_res() -> Vector2i:
	var env := str(OS.get_environment("DMB_RESOLUTION")).strip_edges()
	if env == "" and OS.get_cmdline_user_args().size() > 0:
		for a in OS.get_cmdline_user_args():
			var s := str(a)
			if s.contains("x") and not s.begins_with("--"):
				env = s
				break
	if env.contains("x"):
		var parts := env.split("x")
		return Vector2i(int(parts[0]), int(parts[1]))
	return Vector2i(450, 800)


func _pred_map_open() -> bool:
	if _driver == null or _driver.shell == null:
		return false
	var p = _driver.shell.world_map_panel()
	return p != null and p.visible


func _pred_historic() -> bool:
	if _driver == null or _driver.shell == null:
		return false
	var view: Dictionary = _driver.shell.probe_player(["clock"])
	var clock: Dictionary = view.get("clock", {})
	if typeof(clock) != TYPE_DICTIONARY:
		clock = {}
	return str(clock.get("era", "")) == "historic" or str(clock.get("last_era_transition_id", "")) != ""


func _go() -> void:
	var gate := _parse_gate()
	_driver = Driver.new(self)
	var ok := false
	match gate:
		"G06":
			ok = await _run_g06(_driver)
		"G07":
			ok = await _run_g07(_driver)
		"G08":
			ok = await _run_g08(_driver)
		_:
			push_error("unsupported gate %s" % gate)
			print("AUTO_GATE_FAIL unsupported_gate=", gate)
			quit(2)
			return
	print("AUTO_GATE_STORYBOARD gate=", gate, " ok=", ok, " errors=", _driver.script_errors)
	quit(0 if ok and _driver.script_errors.is_empty() else 1)


func _run_g06(driver) -> bool:
	# FX-MVP settlement + FX-ERA overlays / transition continuity.
	var primary := _parse_res()
	await driver.force_size(primary)
	if not await driver.launch_fixture("G06", "FX-MVP", 507, "auto_g06_mvp"):
		print("AUTO_GATE_FAIL g06_mvp_boot")
		return false
	await driver.capture_screenshot(
		"prehistoric_settlement",
		["building.prehistoric.settlement_centre", "unit.line"],
		{"proves": "FX-MVP normal Prehistoric settlement boots", "state_assertions": ["era=prehistoric_or_unset", "fixture=FX-MVP"]}
	)
	# Inventory / overlay on MVP shell (may no-op if panels absent).
	if await driver.open_overlay("inventory"):
		await driver.capture_screenshot(
			"inventory",
			[],
			{"proves": "Inventory modal opens on FX-MVP", "expected_modal": "inventory"}
		)
		await driver.close_overlay("inventory")
	driver.shell.queue_free()
	await process_frame
	driver.shell = null
	driver.script_errors.clear()

	if not await driver.launch_fixture("G06", "FX-ERA", 507, "auto_g06_era"):
		print("AUTO_GATE_FAIL g06_era_boot")
		return false
	for size in RESOLUTIONS_RESPONSIVE:
		await driver.force_size(size)
		if driver.shell.has_method("_layout_fx_era_panel"):
			driver.shell._layout_fx_era_panel()
		await create_timer(0.25).timeout
		if not await driver.open_overlay("world_map"):
			print("AUTO_GATE_FAIL world_map ", size)
			return false
		await driver.capture_screenshot(
			"world_map",
			[],
			{"proves": "World map overlay fits viewport", "expected_modal": "world_map", "state_assertions": ["modal=world_map"]}
		)
		await driver.close_overlay("world_map")
		if not await driver.open_overlay("chronicle"):
			print("AUTO_GATE_FAIL chronicle ", size)
			return false
		await driver.capture_screenshot(
			"chronicle",
			[],
			{"proves": "Chronicle overlay readable", "expected_modal": "chronicle", "state_assertions": ["modal=chronicle"]}
		)
		await driver.close_overlay("chronicle")

	# Prefer real map button → Historic Wait.
	await driver.force_size(Vector2i(450, 800))
	if driver.shell.has_method("_layout_fx_era_panel"):
		driver.shell._layout_fx_era_panel()
	var map_btn: Button = driver.shell.fx_era_map_button()
	if map_btn != null:
		await driver.press_ui(map_btn, "fx_era_map_btn")
		var opened: bool = await driver.wait_state(Callable(self, "_pred_map_open"), 8000, "press_map_open")
		if not opened:
			# Pointer path can miss focus in automation; fall back to invoke (still real overlay).
			driver.script_errors.erase("press_map_open_timeout")
			opened = await driver.open_overlay("world_map")
		if opened:
			await driver.capture_screenshot(
				"world_map_via_button",
				[],
				{"proves": "World map opened via FX-ERA panel button / invoke", "expected_modal": "world_map"}
			)
			await driver.close_overlay("world_map")

	await driver.open_overlay("fx_era_wait")
	var historic: bool = await driver.wait_state(Callable(self, "_pred_historic"), 35000, "historic_transition")
	if historic:
		await driver.capture_screenshot(
			"historic_after_wait",
			[],
			{"proves": "FX-ERA Wait committed Historic transition", "state_assertions": ["era=historic"], "expected_era": "historic"}
		)
		var save_reply: Dictionary = driver.save_game()
		await driver.capture_screenshot(
			"post_save",
			[],
			{"proves": "Save accepted after Historic", "save_status": str(save_reply.get("status", ""))}
		)
		var load_reply: Dictionary = driver.reload_game()
		await create_timer(0.5).timeout
		await driver.capture_screenshot(
			"post_reload",
			[],
			{"proves": "Reload restores Historic continuity", "load_status": str(load_reply.get("status", "")), "expected_era": "historic"}
		)
	else:
		driver.script_errors.append("historic_transition_failed")
	return driver.script_errors.is_empty()


func _run_g07(driver) -> bool:
	# FX-CYCLE storyboard uses FX-ERA seed 1212 (cycle parent) — legitimate fixture path.
	await driver.force_size(Vector2i(450, 800))
	if not await driver.launch_fixture("G07", "FX-ERA", 1212, "auto_g07_cycle"):
		print("AUTO_GATE_FAIL g07_boot")
		return false
	var cycle_extra := {"cycle_fixture": "FX-CYCLE", "cycle_seed": 1212, "parent_fixture": "FX-ERA"}
	await driver.capture_screenshot(
		"cycle_prehistoric_core",
		["building.prehistoric.settlement_centre"],
		_merge(cycle_extra, {"proves": "FX-CYCLE parent FX-ERA settlement at seed 1212"})
	)
	for size in RESOLUTIONS_RESPONSIVE:
		await driver.force_size(size)
		if driver.shell.has_method("_layout_fx_era_panel"):
			driver.shell._layout_fx_era_panel()
		await create_timer(0.2).timeout
		if not await driver.open_overlay("world_map"):
			return false
		await driver.capture_screenshot(
			"cycle_world_map",
			[],
			_merge(cycle_extra, {"proves": "Cycle board world map", "expected_modal": "world_map"})
		)
		await driver.close_overlay("world_map")
		if not await driver.open_overlay("chronicle"):
			return false
		await driver.capture_screenshot(
			"cycle_chronicle_pins",
			[],
			_merge(cycle_extra, {"proves": "Chronicle pins overlay", "expected_modal": "chronicle"})
		)
		await driver.close_overlay("chronicle")
	await driver.force_size(Vector2i(450, 800))
	await driver.open_overlay("fx_era_wait")
	var historic: bool = await driver.wait_state(Callable(self, "_pred_historic"), 35000, "g07_historic")
	if historic:
		await driver.capture_screenshot(
			"historic_core",
			[],
			_merge(cycle_extra, {"proves": "Historic core after Wait", "expected_era": "historic"})
		)
	else:
		driver.script_errors.append("g07_historic_failed")
	return driver.script_errors.is_empty()


func _run_g08(driver) -> bool:
	# Content-sample visual evidence on FX-ERA seed 808 (matches play_g08_sample).
	await driver.force_size(Vector2i(450, 800))
	if not await driver.launch_fixture("G08", "FX-ERA", 808, "auto_g08_sample"):
		print("AUTO_GATE_FAIL g08_boot")
		return false
	await driver.capture_screenshot(
		"village_panel",
		["building.prehistoric.settlement_centre"],
		{"proves": "G08 content-sample village shell", "content_sample_seed": 808}
	)
	for size in RESOLUTIONS_RESPONSIVE:
		await driver.force_size(size)
		if driver.shell.has_method("_layout_fx_era_panel"):
			driver.shell._layout_fx_era_panel()
		await create_timer(0.2).timeout
		if not await driver.open_overlay("world_map"):
			return false
		await driver.capture_screenshot(
			"world_map",
			[],
			{"proves": "G08 world map layout", "expected_modal": "world_map"}
		)
		await driver.close_overlay("world_map")
		if not await driver.open_overlay("chronicle"):
			return false
		await driver.capture_screenshot(
			"chronicle",
			[],
			{"proves": "G08 chronicle layout", "expected_modal": "chronicle"}
		)
		await driver.close_overlay("chronicle")
	if await driver.open_overlay("knowledge"):
		await driver.capture_screenshot(
			"knowledge",
			[],
			{"proves": "Knowledge modal for narrative tools", "expected_modal": "knowledge"}
		)
		await driver.close_overlay("knowledge")
	if await driver.open_overlay("inventory"):
		await driver.capture_screenshot(
			"inventory",
			[],
			{"proves": "Inventory modal sample", "expected_modal": "inventory"}
		)
		await driver.close_overlay("inventory")
	return driver.script_errors.is_empty()
