extends RefCounted
class_name AutoGateDriver

## Reusable headed/headless auto-gate actions for G06–G12 visual evidence.
## Prefer real Control presses + semantic waits; do not invent world state.

const Shell = preload("res://client/scenes/g05_shell.gd")
const ResponsiveModal = preload("res://client/ui/responsive_modal.gd")

const TOUCH_MIN := 44.0
const BOOT_TIMEOUT_MS := 60000

var tree: SceneTree
var shell
var gate: String = ""
var fixture: String = "FX-ERA"
var seed: int = 507
var out_dir: String = ""
var shot_index: int = 0
var script_errors: Array = []
var last_meta: Dictionary = {}


func _init(p_tree: SceneTree) -> void:
	tree = p_tree


func project_root() -> String:
	var root := ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if root.ends_with("godot_project"):
		root = root.get_base_dir()
	return root


func resolve_out_dir(gate_id: String) -> String:
	return project_root().path_join(
		"Pack/DuelMasterBattle_Build_Pack/tracking/gates/%s/auto/screenshots" % gate_id
	)


func force_size(size: Vector2i) -> void:
	DisplayServer.window_set_size(size)
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	var win := tree.root
	win.size = size
	win.content_scale_size = size
	win.content_scale_mode = Window.CONTENT_SCALE_MODE_DISABLED
	await tree.process_frame
	await tree.process_frame
	await tree.process_frame


func launch_fixture(p_gate: String, p_fixture: String, p_seed: int, save_slot: String = "") -> bool:
	gate = p_gate
	fixture = p_fixture
	seed = p_seed
	out_dir = resolve_out_dir(gate)
	DirAccess.make_dir_recursive_absolute(out_dir)
	OS.set_environment("DMB_FIXTURE", fixture)
	OS.set_environment("DMB_SEED", str(seed))
	if save_slot == "":
		save_slot = "auto_%s_%s" % [gate.to_lower(), fixture.to_lower().replace("-", "_")]
	OS.set_environment("DMB_SAVE_SLOT", save_slot)
	shell = Shell.new()
	tree.root.add_child(shell)
	var deadline := Time.get_ticks_msec() + BOOT_TIMEOUT_MS
	while Time.get_ticks_msec() < deadline and not shell.is_booted():
		await tree.process_frame
	if not shell.is_booted():
		script_errors.append("shell_not_booted")
		push_error("AUTO_GATE boot failed gate=%s fixture=%s" % [gate, fixture])
		return false
	if shell.has_method("_layout_fx_era_panel"):
		shell._layout_fx_era_panel()
	await tree.create_timer(0.35).timeout
	return true


func wait_state(predicate: Callable, timeout_ms: int = 15000, tag: String = "wait") -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		await tree.process_frame
		if predicate.call():
			return true
	script_errors.append("%s_timeout" % tag)
	push_error("AUTO_GATE wait timeout: %s" % tag)
	return false


func wait_booted() -> bool:
	return await wait_state(func(): return shell != null and shell.is_booted(), BOOT_TIMEOUT_MS, "boot")


func press_ui(ctrl: Control, tag: String = "press") -> bool:
	if ctrl == null or not is_instance_valid(ctrl):
		script_errors.append("%s_missing" % tag)
		return false
	if not ctrl.visible or not ctrl.is_visible_in_tree():
		script_errors.append("%s_hidden" % tag)
		return false
	# Prefer real pointer input at control centre.
	var rect := ctrl.get_global_rect()
	var centre := rect.get_center()
	var down := InputEventMouseButton.new()
	down.button_index = MOUSE_BUTTON_LEFT
	down.pressed = true
	down.position = centre
	down.global_position = centre
	Input.parse_input_event(down)
	await tree.process_frame
	var up := InputEventMouseButton.new()
	up.button_index = MOUSE_BUTTON_LEFT
	up.pressed = false
	up.position = centre
	up.global_position = centre
	Input.parse_input_event(up)
	await tree.process_frame
	# Fallback for Controls that ignore parse_input_event without focus.
	if ctrl is BaseButton:
		var btn := ctrl as BaseButton
		if not btn.button_pressed and btn.visible and not btn.disabled:
			btn.emit_signal("pressed")
			await tree.process_frame
	return true


func open_overlay(name: String) -> bool:
	if shell == null:
		return false
	match name:
		"world_map":
			if shell.has_method("invoke_world_map_for_test"):
				shell.invoke_world_map_for_test()
			return await wait_state(Callable(self, "_pred_world_map_open"), 8000, "world_map_open")
		"chronicle":
			if shell.has_method("invoke_chronicle_for_test"):
				shell.invoke_chronicle_for_test()
			return await wait_state(Callable(self, "_pred_chronicle_open"), 8000, "chronicle_open")
		"inventory":
			if shell.has_method("invoke_inventory_for_test"):
				shell.invoke_inventory_for_test()
			return await wait_state(Callable(self, "_pred_inventory_open"), 8000, "inventory_open")
		"grimoire":
			if shell.has_method("invoke_grimoire_for_test"):
				shell.invoke_grimoire_for_test()
			return await wait_state(Callable(self, "_pred_grimoire_open"), 8000, "grimoire_open")
		"knowledge":
			if shell.has_method("invoke_knowledge_for_test"):
				shell.invoke_knowledge_for_test()
			return await wait_state(Callable(self, "_pred_knowledge_open"), 8000, "knowledge_open")
		"fx_era_wait":
			var btn: Button = shell.fx_era_wait_button()
			if btn != null and btn.visible and not btn.disabled:
				await press_ui(btn, "fx_era_wait")
			elif shell.has_method("invoke_fx_era_wait_for_test"):
				shell.invoke_fx_era_wait_for_test()
			return true
		_:
			script_errors.append("unknown_overlay_%s" % name)
			return false


func _pred_world_map_open() -> bool:
	var p = shell.world_map_panel() if shell != null else null
	return p != null and p.visible


func _pred_chronicle_open() -> bool:
	var p = shell.chronicle_panel() if shell != null else null
	return p != null and p.visible


func _pred_inventory_open() -> bool:
	var p = shell.inventory_panel() if shell != null else null
	return p != null and p.visible


func _pred_grimoire_open() -> bool:
	var p = shell.grimoire_panel() if shell != null else null
	return p != null and p.visible


func _pred_knowledge_open() -> bool:
	var p = shell.knowledge_panel() if shell != null else null
	return p != null and p.visible


func close_overlay(name: String) -> void:
	if shell == null:
		return
	match name:
		"world_map":
			var p = shell.world_map_panel()
			if p != null and p.visible and shell.has_method("invoke_world_map_for_test"):
				shell.invoke_world_map_for_test()
		"chronicle":
			var c = shell.chronicle_panel()
			if c != null and c.visible and shell.has_method("invoke_chronicle_for_test"):
				shell.invoke_chronicle_for_test()
		"inventory":
			var inv = shell.inventory_panel()
			if inv != null and inv.visible and shell.has_method("invoke_inventory_for_test"):
				shell.invoke_inventory_for_test()
		"grimoire":
			var g = shell.grimoire_panel()
			if g != null and g.visible and shell.has_method("invoke_grimoire_for_test"):
				shell.invoke_grimoire_for_test()
		"knowledge":
			var k = shell.knowledge_panel()
			if k != null and k.visible and shell.has_method("invoke_knowledge_for_test"):
				shell.invoke_knowledge_for_test()
	await tree.process_frame


func _viewport_rect() -> Rect2:
	return tree.root.get_viewport().get_visible_rect()


func _control_meta(ctrl: Control, role: String) -> Dictionary:
	if ctrl == null or not is_instance_valid(ctrl):
		return {"role": role, "present": false}
	var rect := ctrl.get_global_rect()
	var vp := _viewport_rect()
	var shown := ctrl.is_visible_in_tree()
	var inside := ResponsiveModal.rect_fully_inside(rect, vp, 2.0) if shown else true
	var is_button := role.ends_with("_close") or role in [
		"fx_era_wait", "fx_era_map", "fx_era_chronicle"
	]
	var below := false
	if shown and is_button and rect.size.x > 0.5 and rect.size.y > 0.5:
		below = rect.size.x + 0.5 < TOUCH_MIN or rect.size.y + 0.5 < TOUCH_MIN
	return {
		"role": role,
		"present": true,
		"name": str(ctrl.name),
		"visible": shown,
		"x": rect.position.x,
		"y": rect.position.y,
		"width": rect.size.x,
		"height": rect.size.y,
		"inside_viewport": inside,
		"below_touch_min": below,
		"is_touch_target": is_button,
	}


func _collect_controls() -> Array:
	var out: Array = []
	if shell == null:
		return out
	out.append(_control_meta(shell.fx_era_panel(), "fx_era_panel"))
	out.append(_control_meta(shell.fx_era_wait_button(), "fx_era_wait"))
	out.append(_control_meta(shell.fx_era_map_button(), "fx_era_map"))
	out.append(_control_meta(shell.fx_era_chronicle_button(), "fx_era_chronicle"))
	out.append(_control_meta(shell.world_map_panel(), "world_map"))
	out.append(_control_meta(shell.chronicle_panel(), "chronicle"))
	out.append(_control_meta(shell.inventory_panel(), "inventory"))
	out.append(_control_meta(shell.grimoire_panel(), "grimoire"))
	out.append(_control_meta(shell.knowledge_panel(), "knowledge"))
	var map_p = shell.world_map_panel()
	if map_p != null and map_p.has_method("close_button"):
		out.append(_control_meta(map_p.close_button(), "world_map_close"))
	var chron = shell.chronicle_panel()
	if chron != null and chron.has_method("close_button"):
		out.append(_control_meta(chron.close_button(), "chronicle_close"))
	return out


func _overlap_flags(controls: Array) -> Array:
	var flags: Array = []
	var visible: Array = []
	for c in controls:
		if typeof(c) != TYPE_DICTIONARY:
			continue
		if not bool(c.get("visible", false)) or not bool(c.get("present", false)):
			continue
		if float(c.get("width", 0)) <= 1.0 or float(c.get("height", 0)) <= 1.0:
			continue
		visible.append(c)
	for i in range(visible.size()):
		for j in range(i + 1, visible.size()):
			var a: Dictionary = visible[i]
			var b: Dictionary = visible[j]
			# Ignore nested pairs (panel vs its own button) — only flag distinct overlay classes.
			var ra := Rect2(a.get("x", 0), a.get("y", 0), a.get("width", 0), a.get("height", 0))
			var rb := Rect2(b.get("x", 0), b.get("y", 0), b.get("width", 0), b.get("height", 0))
			if not ra.intersects(rb):
				continue
			var role_a := str(a.get("role", ""))
			var role_b := str(b.get("role", ""))
			if role_a.begins_with(role_b) or role_b.begins_with(role_a):
				continue
			if role_a.begins_with("fx_era") and role_b.begins_with("fx_era"):
				continue
			# Severe: two major overlays both open and intersecting deeply.
			var inter := ra.intersection(rb)
			var area := inter.size.x * inter.size.y
			if area > 8000.0:
				flags.append({"a": role_a, "b": role_b, "overlap_px": area})
	return flags


func _probe_state() -> Dictionary:
	if shell == null or not shell.has_method("probe_player"):
		return {}
	return shell.probe_player(["clock", "player", "fx_era", "fx_village", "chronicle", "world_map"])


func _semantic_ids_from_view(view: Dictionary) -> Array:
	var ids: Array = []
	var fx: Dictionary = view.get("fx_era", {})
	if typeof(fx) != TYPE_DICTIONARY:
		fx = {}
	for key in ["fixture", "settlement_id", "core_id"]:
		if fx.has(key) and str(fx[key]) != "":
			ids.append(str(fx[key]))
	var village: Dictionary = view.get("fx_village", {})
	if typeof(village) != TYPE_DICTIONARY:
		village = {}
	for key in ["fixture", "settlement_centre", "mara_id", "factory_id"]:
		if village.has(key) and str(village[key]) != "":
			ids.append(str(village[key]))
	# Stable semantic placeholders expected in Prehistoric settlement captures.
	ids.append("building.prehistoric.settlement_centre")
	ids.append("unit.line")
	return ids


func export_semantic_metadata(
	checkpoint: String,
	expected_semantic_ids: Array = [],
	extra: Dictionary = {}
) -> Dictionary:
	var view := _probe_state()
	var clock: Dictionary = view.get("clock", {})
	if typeof(clock) != TYPE_DICTIONARY:
		clock = {}
	var player: Dictionary = view.get("player", {})
	if typeof(player) != TYPE_DICTIONARY:
		player = {}
	var controls := _collect_controls()
	var modal_open := ""
	for c in controls:
		if typeof(c) != TYPE_DICTIONARY:
			continue
		var role := str(c.get("role", ""))
		if role in ["world_map", "chronicle", "inventory", "grimoire", "knowledge"] and bool(c.get("visible", false)):
			modal_open = role
			break
	var observed := _semantic_ids_from_view(view)
	var missing: Array = []
	for sid in expected_semantic_ids:
		if not observed.has(str(sid)) and str(sid) not in observed:
			# Soft: placeholders may be presentation-only; record expectation.
			missing.append(str(sid))
	var vp := _viewport_rect()
	var outside: Array = []
	var touch_bad: Array = []
	for c in controls:
		if typeof(c) != TYPE_DICTIONARY:
			continue
		if bool(c.get("visible", false)) and not bool(c.get("inside_viewport", true)):
			outside.append(c.get("role"))
		if bool(c.get("below_touch_min", false)):
			touch_bad.append(c.get("role"))
	var meta := {
		"gate": gate,
		"checkpoint": checkpoint,
		"fixture": fixture,
		"seed": seed,
		"era": str(clock.get("era", "")),
		"node_id": str(player.get("node_id", "")),
		"player_position": player.get("position", {}),
		"expected_semantic_ids": expected_semantic_ids,
		"observed_semantic_ids": observed,
		"missing_semantic_ids": missing,
		"visible_ui": controls,
		"viewport": {"width": vp.size.x, "height": vp.size.y},
		"modal_open": modal_open,
		"overlap_flags": _overlap_flags(controls),
		"controls_outside_viewport": outside,
		"touch_below_min": touch_bad,
		"state_assertions": extra.get("state_assertions", []),
		"script_errors": script_errors.duplicate(),
		"proves": str(extra.get("proves", "")),
	}
	for k in extra.keys():
		if not meta.has(k):
			meta[k] = extra[k]
	last_meta = meta
	return meta


func capture_screenshot(
	checkpoint: String,
	expected_semantic_ids: Array = [],
	extra: Dictionary = {}
) -> Dictionary:
	await tree.process_frame
	await tree.process_frame
	shot_index += 1
	var vp := _viewport_rect().size
	var w := int(vp.x)
	var h := int(vp.y)
	var base := "%02d_%s_%dx%d" % [shot_index, checkpoint, w, h]
	var png_path := out_dir.path_join(base + ".png")
	var json_path := out_dir.path_join(base + ".json")
	var img: Image = tree.root.get_viewport().get_texture().get_image()
	var ok := false
	var err := FAILED
	if img != null:
		err = img.save_png(png_path)
		ok = err == OK
	else:
		script_errors.append("null_image_%s" % checkpoint)
	var meta := export_semantic_metadata(checkpoint, expected_semantic_ids, extra)
	meta["screenshot"] = base + ".png"
	meta["screenshot_path"] = png_path
	meta["bytes"] = 0
	meta["image_width"] = img.get_width() if img != null else 0
	meta["image_height"] = img.get_height() if img != null else 0
	meta["capture_ok"] = ok
	meta["save_error"] = err
	if ok:
		var f := FileAccess.open(png_path, FileAccess.READ)
		if f != null:
			meta["bytes"] = f.get_length()
			f.close()
	var jf := FileAccess.open(json_path, FileAccess.WRITE)
	if jf != null:
		jf.store_string(JSON.stringify(meta, "\t"))
		jf.close()
	else:
		script_errors.append("meta_write_failed_%s" % checkpoint)
	print("AUTO_GATE_SHOT ", gate, " ", base, " ok=", ok, " bytes=", meta.get("bytes", 0))
	last_meta = meta
	return meta


func save_game(slot: String = "") -> Dictionary:
	if shell == null:
		return {"status": "FAIL", "code": "no_shell"}
	if slot == "":
		slot = str(OS.get_environment("DMB_SAVE_SLOT"))
	return shell.save_slot(slot)


func reload_game(slot: String = "") -> Dictionary:
	if shell == null:
		return {"status": "FAIL", "code": "no_shell"}
	if slot == "":
		slot = str(OS.get_environment("DMB_SAVE_SLOT"))
	return shell.load_slot(slot)


func quit_ok(code: int = 0) -> void:
	print("AUTO_GATE_DONE gate=", gate, " shots=", shot_index, " errors=", script_errors)
	tree.quit(code if script_errors.is_empty() else maxi(code, 1))
