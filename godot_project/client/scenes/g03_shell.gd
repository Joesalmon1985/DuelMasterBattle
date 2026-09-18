extends "res://client/scenes/g02_shell.gd"

const IndustryView = preload("res://client/debug/industry_view.gd")
const WorkerControllerScript = preload("res://client/world/worker_controller.gd")
const G03_SAVE_SLOT := "g03_playtest"
const TILE := 64.0

var _workers
var _manual_path_block := false
var _sites_layer: Node2D
var _units_layer: Node2D
var _site_nodes: Dictionary = {}
var _progress_bars: Dictionary = {}
var _unit_nodes: Dictionary = {}
var _assembly_marker: Node2D
var _last_unit_ids: Dictionary = {}
var _links_layer: Node2D
var _selected_building := ""
var _focus_label: Label
var _mouse_was_down := false


func _ready() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-INDUSTRY")
	OS.set_environment("DMB_SEED", "303")
	super()
	if _economy:
		_economy.queue_free()
	_economy = IndustryView.new()
	_ui_root.add_child(_economy)
	_economy.bind_client(_client)
	_economy.action_requested.connect(_on_industry_action)
	_economy.worker_path_toggled.connect(_on_path_toggled)
	_sites_layer = Node2D.new()
	_sites_layer.name = "IndustrySites"
	_world_host.add_child(_sites_layer)
	_links_layer = Node2D.new()
	_links_layer.name = "IndustryLinks"
	_world_host.add_child(_links_layer)
	_units_layer = Node2D.new()
	_units_layer.name = "IndustryUnits"
	_world_host.add_child(_units_layer)
	_workers = WorkerControllerScript.new()
	_world_host.add_child(_workers)
	_workers.layout_diagnostic.connect(func(pid, msg): _log("%s %s" % [pid, msg]))
	_focus_label = Label.new()
	_focus_label.position = Vector2(12, 70)
	_focus_label.add_theme_font_size_override("font_size", 13)
	_focus_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_focus_label.custom_minimum_size = Vector2(280, 0)
	_ui_root.add_child(_focus_label)
	_set_status("Python-backed FX-INDUSTRY — per-connection carriers")
	_prompt.text = "Tap a building for its connections. Block path is presentation-only."


func _process(delta: float) -> void:
	super(delta)
	if _workers == null or _economy == null:
		return
	var view: Dictionary = _economy._last_view
	if view.is_empty():
		return
	_ensure_sites(view)
	_update_sites(view)
	_update_units(view)
	_draw_connections(view)
	var rows: Array = view.get("industry_workers", [])
	_workers.apply_projection(rows)
	var frozen := _paused or not _focus or _bridge_down
	_workers.set_frozen(frozen)
	_workers.set_manual_path_block(_manual_path_block)
	if _area and _area._wizard:
		_workers.set_wizard_world_position(_area._wizard.global_position)
	if not frozen:
		_workers.tick(delta)
	var mouse_down := Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT)
	if (mouse_down and not _mouse_was_down) or Input.is_action_just_pressed("ui_accept"):
		_try_select_building(view)
	_mouse_was_down = mouse_down


func _on_path_toggled(blocked: bool) -> void:
	_manual_path_block = blocked
	_prompt.text = "Worker path %s (presentation only — production continues)." % (
		"blocked" if blocked else "cleared"
	)


func _ensure_sites(view: Dictionary) -> void:
	var fx: Dictionary = view.get("fx_industry", {})
	var layout: Dictionary = fx.get("layout", {})
	var sites: Array = layout.get("sites", [])
	if sites.is_empty() or not _site_nodes.is_empty():
		if _assembly_marker == null and layout.has("assembly"):
			_build_assembly(layout.get("assembly", {}))
		return
	for site_variant in sites:
		var site: Dictionary = site_variant
		var site_id := str(site.get("id", ""))
		if site_id.is_empty():
			continue
		var node := Node2D.new()
		node.name = site_id.validate_node_name()
		_sites_layer.add_child(node)
		var grid: Array = site.get("grid", [0, 0])
		node.position = Vector2(float(grid[0]) * TILE + TILE * 0.5, float(grid[1]) * TILE + TILE * 0.5)
		var rect := Polygon2D.new()
		rect.name = "Rect"
		rect.polygon = PackedVector2Array([
			Vector2(-44, -32), Vector2(44, -32), Vector2(44, 32), Vector2(-44, 32)
		])
		rect.color = Color(str(site.get("color", "#888888")))
		node.add_child(rect)
		var door := Polygon2D.new()
		door.name = "Entrance"
		door.polygon = PackedVector2Array([
			Vector2(-11, 28), Vector2(11, 28), Vector2(11, 38), Vector2(-11, 38)
		])
		door.color = Color(0.12, 0.12, 0.12, 0.9)
		node.add_child(door)
		var label := Label.new()
		label.name = "Label"
		label.text = str(site.get("label", site_id))
		label.position = Vector2(-48, -58)
		label.add_theme_font_size_override("font_size", 11)
		label.mouse_filter = Control.MOUSE_FILTER_IGNORE
		node.add_child(label)
		if str(site.get("kind", "")) == "factory":
			var bar_bg := Polygon2D.new()
			bar_bg.name = "ProgressBg"
			bar_bg.polygon = PackedVector2Array([
				Vector2(-40, 36), Vector2(40, 36), Vector2(40, 44), Vector2(-40, 44)
			])
			bar_bg.color = Color(0.1, 0.1, 0.1, 0.8)
			node.add_child(bar_bg)
			var bar := Polygon2D.new()
			bar.name = "Progress"
			bar.polygon = PackedVector2Array([
				Vector2(-40, 36), Vector2(-40, 36), Vector2(-40, 44), Vector2(-40, 44)
			])
			bar.color = Color(0.35, 0.85, 0.4)
			node.add_child(bar)
			var pct := Label.new()
			pct.name = "ProgressLabel"
			pct.position = Vector2(-40, 46)
			pct.add_theme_font_size_override("font_size", 10)
			pct.mouse_filter = Control.MOUSE_FILTER_IGNORE
			node.add_child(pct)
			_progress_bars[site_id] = {"bar": bar, "label": pct}
		_site_nodes[site_id] = node
	_build_assembly(layout.get("assembly", {}))


func _build_assembly(assembly: Dictionary) -> void:
	if assembly.is_empty() or _assembly_marker != null:
		return
	_assembly_marker = Node2D.new()
	_assembly_marker.name = "Assembly"
	_sites_layer.add_child(_assembly_marker)
	var grid: Array = assembly.get("grid", [7, 9])
	_assembly_marker.position = Vector2(float(grid[0]) * TILE + TILE * 0.5, float(grid[1]) * TILE + TILE * 0.5)
	var pad := Polygon2D.new()
	pad.polygon = PackedVector2Array([
		Vector2(-70, -20), Vector2(70, -20), Vector2(70, 20), Vector2(-70, 20)
	])
	pad.color = Color(0.25, 0.25, 0.28, 0.55)
	_assembly_marker.add_child(pad)
	var label := Label.new()
	label.text = str(assembly.get("label", "Assembly"))
	label.position = Vector2(-60, -18)
	label.add_theme_font_size_override("font_size", 11)
	_assembly_marker.add_child(label)


func _update_sites(view: Dictionary) -> void:
	var buildings: Dictionary = view.get("buildings", {})
	var industry: Dictionary = view.get("industry", {})
	var fx: Dictionary = view.get("fx_industry", {})
	var rates: Dictionary = {}
	var reasons: Dictionary = {}
	for event_variant in industry.get("events", []):
		var event: Dictionary = event_variant
		if event.get("kind") == "industry_rates":
			rates = event.get("rates", {})
		elif event.get("kind") == "industry_shortage":
			reasons = event.get("reasons", {})
	var processor_id: String = str(fx.get("processor_id", ""))
	var processor: Dictionary = buildings.get(processor_id, {})
	var health: float = float(processor.get("health", 100))
	var max_health: float = maxf(float(processor.get("max_health", 100)), 1.0)
	var health_ratio: float = health / max_health
	if _site_nodes.has(processor_id):
		var proc_node: Node2D = _site_nodes[processor_id]
		var rect: Polygon2D = proc_node.get_node_or_null("Rect")
		if rect:
			rect.color = Color("#c47a2c").lerp(Color(0.45, 0.12, 0.12), 1.0 - health_ratio)
		var label: Label = proc_node.get_node_or_null("Label")
		if label:
			label.text = "%s\nhealth %d%%" % [
				str(processor.get("label", "Processor")),
				int(round(health_ratio * 100.0)),
			]
	for factory_id in fx.get("factory_ids", []):
		var factory: Dictionary = industry.get("factories", {}).get(factory_id, {})
		var meter: float = _fraction_to_float(factory.get("meter", 0))
		var rate: float = _fraction_to_float(rates.get(factory_id, 0))
		var bars: Dictionary = _progress_bars.get(factory_id, {})
		if bars.has("bar"):
			var bar: Polygon2D = bars["bar"]
			var width: float = clampf(meter, 0.0, 1.0) * 80.0
			bar.polygon = PackedVector2Array([
				Vector2(-40, 36), Vector2(-40.0 + width, 36), Vector2(-40.0 + width, 44), Vector2(-40, 44)
			])
		if bars.has("label"):
			var lbl: Label = bars["label"]
			var cause: String = str(reasons.get(factory_id, "running"))
			lbl.text = "%d%%  %.3f/s  %s" % [int(round(meter * 100.0)), rate, cause]


func _update_units(view: Dictionary) -> void:
	var units: Dictionary = view.get("units", {})
	var fx: Dictionary = view.get("fx_industry", {})
	var layout: Dictionary = fx.get("layout", {})
	var sites: Array = layout.get("sites", [])
	var factory_pos: Dictionary = {}
	for site_variant in sites:
		var site: Dictionary = site_variant
		if str(site.get("kind", "")) != "factory":
			continue
		factory_pos[str(site.get("unit_def_id", ""))] = site
	var seen: Dictionary = {}
	for unit_id in units.keys():
		seen[unit_id] = true
		var unit: Dictionary = units[unit_id]
		var def_id: String = str(unit.get("definition_id", ""))
		if _unit_nodes.has(unit_id):
			continue
		var site: Dictionary = factory_pos.get(def_id, {})
		var spawn: Vector2 = Vector2(7.0 * TILE, 9.0 * TILE)
		if not site.is_empty():
			var grid: Array = site.get("grid", [7, 7])
			spawn = Vector2(float(grid[0]) * TILE + 20.0, float(grid[1]) * TILE + 48.0)
		var node := Node2D.new()
		node.name = str(unit_id).validate_node_name()
		_units_layer.add_child(node)
		node.position = spawn
		var body := Polygon2D.new()
		body.polygon = PackedVector2Array([
			Vector2(-14, -14), Vector2(14, -14), Vector2(14, 14), Vector2(-14, 14)
		])
		body.color = Color(str(site.get("color", "#cccccc")))
		node.add_child(body)
		var label := Label.new()
		label.text = _short_unit_name(def_id)
		label.position = Vector2(-20, -30)
		label.add_theme_font_size_override("font_size", 10)
		node.add_child(label)
		node.set_meta("target", _assembly_slot(def_id))
		# Snap then ease toward the assembly slot so units are readable immediately.
		node.position = node.get_meta("target")
		_unit_nodes[unit_id] = node
		_last_unit_ids[unit_id] = def_id
	# Count label near assembly.
	if _assembly_marker:
		var counts: Dictionary = {}
		for def_id2 in _last_unit_ids.values():
			counts[def_id2] = int(counts.get(def_id2, 0)) + 1
		var count_label: Label = _assembly_marker.get_node_or_null("Counts")
		if count_label == null:
			count_label = Label.new()
			count_label.name = "Counts"
			count_label.position = Vector2(-66, 4)
			count_label.add_theme_font_size_override("font_size", 11)
			_assembly_marker.add_child(count_label)
		var parts: PackedStringArray = PackedStringArray()
		for def_id3 in ["unit.ancient.skirmisher", "unit.ancient.line", "unit.ancient.heavy"]:
			if counts.has(def_id3):
				parts.append("%s×%d" % [_short_unit_name(def_id3), int(counts[def_id3])])
		count_label.text = "  ".join(parts) if not parts.is_empty() else "no units yet"
	for unit_id in _unit_nodes.keys():
		if not seen.has(unit_id):
			_unit_nodes[unit_id].queue_free()
			_unit_nodes.erase(unit_id)
			_last_unit_ids.erase(unit_id)
			continue
		var node2: Node2D = _unit_nodes[unit_id]
		var target: Vector2 = node2.get_meta("target", node2.position)
		if not (_paused or not _focus or _bridge_down):
			node2.position = node2.position.move_toward(target, 80.0 * get_process_delta_time())


func _assembly_slot(def_id: String) -> Vector2:
	var base := Vector2(7.0 * TILE, 9.0 * TILE)
	match def_id:
		"unit.ancient.skirmisher":
			return base + Vector2(-48, 0)
		"unit.ancient.line":
			return base + Vector2(0, 0)
		"unit.ancient.heavy":
			return base + Vector2(48, 0)
		_:
			return base


func _short_unit_name(def_id: String) -> String:
	if def_id.ends_with("skirmisher"):
		return "Skirmisher"
	if def_id.ends_with("line"):
		return "Line"
	if def_id.ends_with("heavy"):
		return "Heavy"
	return def_id.get_file()


func _fraction_to_float(value) -> float:
	if typeof(value) == TYPE_DICTIONARY:
		var num := float(value.get("numerator", 0))
		var den := float(value.get("denominator", 1))
		if den == 0.0:
			return 0.0
		return num / den
	return float(value)


func _on_industry_action(action: String) -> void:
	var reply := _cmd("Interact", {"action": action})
	if str(reply.get("status", "")) == "ACCEPTED":
		var paid = reply.get("payload", {}).get("paid", {})
		if action == "industry_repair" and typeof(paid) == TYPE_DICTIONARY and not paid.is_empty():
			_prompt.text = "Paid repair accepted — cost %s" % str(paid)
		else:
			_prompt.text = "%s accepted. Watch workplaces, rates, and worker activity." % action
		if _economy:
			_economy.refresh(true)
	else:
		_prompt.text = "%s rejected: %s" % [action, reply.get("public_feedback", reply.get("code", "?"))]


func _on_save() -> void:
	_sync_pose()
	var reply := _cmd("Save", {"slot": G03_SAVE_SLOT})
	if str(reply.get("status", "")) == "ACCEPTED":
		_prompt.text = "Saved isolated slot %s" % G03_SAVE_SLOT


func _on_load() -> void:
	var reply := _cmd("Load", {"slot": G03_SAVE_SLOT})
	if str(reply.get("status", "")) == "ACCEPTED":
		_paused = false
		_bridge_down = false
		_refresh_counters(true)
		_apply_movement_gate()
		_prompt.text = "Loaded %s — worker ID/job and exact carry restored" % G03_SAVE_SLOT
		if _economy:
			_economy.refresh(true)


func _draw_connections(view: Dictionary) -> void:
	if _links_layer == null:
		return
	for child in _links_layer.get_children():
		child.queue_free()
	var connections: Array = view.get("industry_connections", [])
	for conn_variant in connections:
		var conn: Dictionary = conn_variant
		var from_id := str(conn.get("from_id", ""))
		var to_id := str(conn.get("to_id", ""))
		if not _site_nodes.has(from_id) or not _site_nodes.has(to_id):
			continue
		var highlight := _selected_building != "" and (
			_selected_building == from_id or _selected_building == to_id
		)
		if _selected_building != "" and not highlight:
			continue
		var a: Vector2 = _site_nodes[from_id].position
		var b: Vector2 = _site_nodes[to_id].position
		var line := Line2D.new()
		line.width = 3.0 if highlight else 1.5
		line.default_color = Color(0.95, 0.9, 0.35, 0.95) if highlight else Color(0.8, 0.8, 0.75, 0.45)
		line.points = PackedVector2Array([a, b])
		_links_layer.add_child(line)
		var mid := (a + b) * 0.5
		var tag := Label.new()
		tag.text = "%s %s" % [conn.get("marker", {}).get("symbol", "?"), conn.get("resource_label", "")]
		tag.position = mid + Vector2(-36, -14)
		tag.add_theme_font_size_override("font_size", 10)
		_links_layer.add_child(tag)


func _try_select_building(view: Dictionary) -> void:
	if _area == null or _area._wizard == null:
		return
	var probe: Vector2 = _area._wizard.global_position
	var best_id := ""
	var best_dist := 72.0
	for site_id in _site_nodes.keys():
		var node: Node2D = _site_nodes[site_id]
		var dist: float = node.global_position.distance_to(probe)
		if dist < best_dist:
			best_dist = dist
			best_id = str(site_id)
	if best_id == "":
		return
	_selected_building = best_id
	var plain := _plain_building_focus(view, best_id)
	if _focus_label:
		_focus_label.text = plain
	_prompt.text = plain


func _plain_building_focus(view: Dictionary, building_id: String) -> String:
	var buildings: Dictionary = view.get("buildings", {})
	var building: Dictionary = buildings.get(building_id, {})
	var label := str(building.get("label", building_id))
	var connections: Array = view.get("industry_connections", [])
	var bits: PackedStringArray = PackedStringArray()
	bits.append(label.replace("\n", " / ") + ":")
	var bottleneck := ""
	for conn_variant in connections:
		var conn: Dictionary = conn_variant
		if str(conn.get("from_id", "")) == building_id:
			bits.append(
				"sends %s to %s (%.3f/s)"
				% [conn.get("resource_label", "?"), conn.get("to_id", "?"), float(conn.get("throughput_per_sec", 0))]
			)
			if conn.get("bottleneck"):
				bottleneck = str(conn.get("bottleneck"))
		elif str(conn.get("to_id", "")) == building_id:
			bits.append(
				"receives %s from %s (%.3f/s)"
				% [conn.get("resource_label", "?"), conn.get("from_id", "?"), float(conn.get("throughput_per_sec", 0))]
			)
			if conn.get("bottleneck"):
				bottleneck = str(conn.get("bottleneck"))
	if bottleneck != "":
		bits.append("Bottleneck: %s." % bottleneck)
	elif bits.size() == 1:
		bits.append("no active connections.")
	return " ".join(bits)
