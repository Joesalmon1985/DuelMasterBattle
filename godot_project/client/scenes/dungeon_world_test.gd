extends Control
## Full-board dungeon spatial test shell.
## Boots a disposable Adventure + real DmbWorldSim board, with debug controls
## for node size profiles, candidate overlays, and one embedded PuzzleKit specimen.

const Spec = preload("res://sim/world/wizard_dungeon_spec.gd")
const Fixture = preload("res://sim/world/dungeon_world_fixture.gd")
const Emb = preload("res://sim/world/embedded_dungeon.gd")
const OverworldScene = preload("res://client/scenes/overworld.tscn")
const Runner = preload("res://client/scripts/puzzle_test_runner.gd")

var fixture
var world: Node2D
var current_node: int = -1
var current_size: Vector2i = Vector2i(73, 55)
var show_hex_ids := true
var show_node_ids := true
var show_settlements := true
var show_candidates := true
var show_terrain := true
var show_connectivity := false
var show_dungeon_bounds := true
var show_room_bounds := true
var show_entity_ids := true
var show_paths := false
var strategic_mode := true
var metrics_label: Label
var board_draw: Control
var panel: VBoxContainer
var status: Label


func _ready() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-DUNGEON-WORLD")
	var world_seed: int = int(OS.get_environment("DMB_SEED")) if OS.get_environment("DMB_SEED") != "" else 507
	fixture = Fixture.new()
	fixture.setup(world_seed)
	current_node = fixture.sim.player_home_node()
	_build_ui()
	_wire_augment()
	_boot_adventure()
	_show_strategic()
	_refresh_metrics()


func _boot_adventure() -> void:
	var adv: Node = get_node("/root/Adventure")
	adv.test_mode = true
	adv.delete_save()
	adv.new_game()
	adv.state["world_seed"] = fixture.seed
	adv.state["world"] = var_to_str(fixture.sim.to_dict())
	adv.state["area"] = DmbNodeProjection.area_id(fixture.sim.player_home_node())
	adv.state["pos"] = [current_size.x / 2, current_size.y - 4]
	WorldFlow.test_augment = _augment_area
	# Overworld is created lazily on first node enter so strategic mode is clean.
	world = null


func _ensure_world() -> void:
	if world != null:
		return
	var adv: Node = get_node("/root/Adventure")
	DmbSettlementLayout.FORCE_DIMS = current_size
	world = OverworldScene.instantiate()
	world.name = "Overworld"
	add_child(world)
	await get_tree().process_frame
	world._world_flow.setup(adv)
	world._world_flow.sim = fixture.sim
	world._play.setup(world, adv, world._world_flow)
	world.visible = false
	DmbSettlementLayout.FORCE_DIMS = Vector2i.ZERO


func _wire_augment() -> void:
	WorldFlow.test_augment = _augment_area


func _augment_area(area: Dictionary, nid: int) -> Dictionary:
	DmbSettlementLayout.FORCE_DIMS = current_size
	var sized: Dictionary = DmbNodeProjection.area_for(fixture.sim, nid, {})
	DmbSettlementLayout.FORCE_DIMS = Vector2i.ZERO
	var code: String = fixture.primary_type_for(nid)
	if code == "" and nid == fixture.bg_test_node:
		code = "BG"
	if nid == fixture.specimen_node and fixture.types_for(nid).has("GW"):
		code = "GW"
	if code == "":
		sized["dungeon_world_test"] = true
		sized["fixture_node"] = nid
		return _filter_debug(sized)
	# Always stamp an interactive PuzzleKit dungeon for playable fixture nodes.
	var emb: Dictionary = Emb.stamp(sized, code, true)
	sized["embedded_dungeon"] = emb
	sized["dungeon_world_test"] = true
	sized["fixture_node"] = nid
	sized["fixture_types"] = fixture.types_for(nid)
	return _filter_debug(sized)


func _filter_debug(area: Dictionary) -> Dictionary:
	if show_entity_ids and show_room_bounds:
		return area
	var ents: Array = []
	for e in area.get("entities", []):
		if str(e.get("kind", "")) == "debug_label":
			var t := str(e.get("text", ""))
			if not show_entity_ids and (t.begins_with("ITEM:") or t.begins_with("MECH:") or t.begins_with("GATE:") or t.begins_with("RECEPTOR:") or t.begins_with("SIGN:") or t.begins_with("STATE:") or t.begins_with("WIZARD:")):
				continue
			if not show_room_bounds and t.begins_with("ROOM:"):
				continue
			if not show_dungeon_bounds and t.begins_with("DUNGEON:"):
				continue
		ents.append(e)
	area["entities"] = ents
	return area


func _build_ui() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = Color(0.05, 0.07, 0.1, 1)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	board_draw = Control.new()
	board_draw.set_anchors_preset(Control.PRESET_FULL_RECT)
	board_draw.draw.connect(_draw_strategic)
	board_draw.gui_input.connect(_on_board_input)
	add_child(board_draw)

	var layer := CanvasLayer.new()
	layer.layer = 40
	add_child(layer)

	panel = VBoxContainer.new()
	panel.position = Vector2(8, 8)
	panel.custom_minimum_size = Vector2(210, 0)
	layer.add_child(panel)

	status = Label.new()
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	status.custom_minimum_size = Vector2(200, 48)
	status.add_theme_font_size_override("font_size", 11)
	panel.add_child(status)

	_btn("Strategic Board", func(): _show_strategic())
	_btn("Enter Current Node (puzzle)", func(): _enter_node(current_node))
	_btn("Prev Node", func(): _step_node(-1))
	_btn("Next Node", func(): _step_node(1))
	_btn("Size 65×49", func(): _set_profile_size(Vector2i(65, 49)))
	_btn("Size 73×55", func(): _set_profile_size(Vector2i(73, 55)))
	_btn("Size 81×61", func(): _set_profile_size(Vector2i(81, 61)))
	_btn("Toggle Hex IDs", func(): show_hex_ids = not show_hex_ids; board_draw.queue_redraw())
	_btn("Toggle Node IDs", func(): show_node_ids = not show_node_ids; board_draw.queue_redraw())
	_btn("Toggle Settlements", func(): show_settlements = not show_settlements; board_draw.queue_redraw())
	_btn("Toggle Candidates", func(): show_candidates = not show_candidates; board_draw.queue_redraw())
	_btn("Toggle Terrain", func(): show_terrain = not show_terrain; board_draw.queue_redraw())
	_btn("Toggle Connectivity", func(): show_connectivity = not show_connectivity; board_draw.queue_redraw())
	_btn("Toggle Dungeon Bounds", func(): show_dungeon_bounds = not show_dungeon_bounds; _reload_if_local())
	_btn("Toggle Room Bounds", func(): show_room_bounds = not show_room_bounds; _reload_if_local())
	_btn("Toggle Entity IDs", func(): show_entity_ids = not show_entity_ids; _reload_if_local())
	_btn("Test BG Rotgarden", func(): _enter_bg())
	_btn("Enter Specimen GW", func(): _enter_specimen())
	_btn("Reset Node", func(): _reload_if_local())
	_btn("Reset Fixture", func(): _reset_fixture())

	metrics_label = Label.new()
	metrics_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	metrics_label.custom_minimum_size = Vector2(200, 160)
	metrics_label.add_theme_font_size_override("font_size", 10)
	panel.add_child(metrics_label)


func _btn(text: String, cb: Callable) -> void:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(200, 22)
	b.add_theme_font_size_override("font_size", 11)
	b.pressed.connect(cb)
	panel.add_child(b)


func _show_strategic() -> void:
	strategic_mode = true
	board_draw.visible = true
	if world:
		world.visible = false
	board_draw.queue_redraw()
	status.text = "FX-DUNGEON-WORLD seed=%d · 19 hexes · %d nodes · %d candidates · node %d" % [
		fixture.seed, fixture.sim.board.nodes.size(), fixture.candidates.size(), current_node]


func _enter_node(nid: int, as_specimen: bool = false) -> void:
	strategic_mode = false
	board_draw.visible = false
	current_node = nid
	await _ensure_world()
	DmbSettlementLayout.FORCE_DIMS = current_size
	var adv: Node = get_node("/root/Adventure")
	if Runner.is_active():
		Runner.end(adv)
	var code: String = "GW" if as_specimen else fixture.primary_type_for(nid)
	if code == "" and nid == fixture.bg_test_node:
		code = "BG"
	if as_specimen:
		nid = fixture.specimen_node
		current_node = nid
		code = "GW"
	if code == "":
		# No dungeon type — plain local area projection.
		adv.state["area"] = DmbNodeProjection.area_id(nid)
		world.visible = true
		world.load_area(DmbNodeProjection.area_id(nid), Vector2i(current_size.x / 2, current_size.y - 3), "up")
		status.text = "Node %d @ %dx%d · no dungeon type" % [nid, current_size.x, current_size.y]
		DmbSettlementLayout.FORCE_DIMS = Vector2i.ZERO
		_refresh_metrics()
		return
	var area: Dictionary = fixture.project_node(nid, current_size, code, true)
	var emb: Dictionary = area.get("embedded_dungeon", {})
	if str(emb.get("fit", "")) != "OK":
		status.text = "DOES NOT FIT at %dx%d: %s" % [current_size.x, current_size.y, emb.get("reason", emb.get("fit", "?"))]
		DmbSettlementLayout.FORCE_DIMS = Vector2i.ZERO
		_show_strategic()
		return
	var kit: Dictionary = emb.get("kit_room", {})
	if kit.is_empty():
		status.text = "No PuzzleKit room for %s" % code
		_show_strategic()
		return
	# Ensure combat spells are present for guardian fights.
	for sid in [0, 1, 6]:
		adv.learn_spell(sid)
	Runner.begin_with_room(adv, kit)
	world.visible = true
	world._boot_kit_session(adv)
	status.text = "%s node %d @ %dx%d · interact: Space · fight guardians · D drop · T throw" % [
		code, nid, current_size.x, current_size.y]
	DmbSettlementLayout.FORCE_DIMS = Vector2i.ZERO
	_refresh_metrics()


func _enter_specimen() -> void:
	_enter_node(fixture.specimen_node, true)


func _enter_bg() -> void:
	_enter_node(fixture.bg_test_node, false)


func _step_node(delta: int) -> void:
	var ids: Array = fixture.candidate_nodes()
	if ids.is_empty():
		ids = []
		for n in fixture.sim.board.nodes:
			ids.append(int(n["id"]))
	var i := ids.find(current_node)
	if i < 0:
		i = 0
	i = (i + delta + ids.size()) % ids.size()
	current_node = int(ids[i])
	if strategic_mode:
		board_draw.queue_redraw()
		_refresh_metrics()
	else:
		_enter_node(current_node)


func _set_profile_size(sz: Vector2i) -> void:
	current_size = sz
	if strategic_mode:
		_refresh_metrics()
	else:
		_enter_node(current_node, Runner.is_active())


func _reload_if_local() -> void:
	if not strategic_mode:
		_enter_node(current_node, Runner.is_active())


func _reset_fixture() -> void:
	var adv: Node = get_node("/root/Adventure")
	if Runner.is_active():
		Runner.end(adv)
	DmbSettlementLayout.FORCE_DIMS = Vector2i.ZERO
	WorldFlow.test_augment = Callable()
	var keep_seed: int = fixture.seed
	fixture = Fixture.new()
	fixture.setup(keep_seed)
	_wire_augment()
	current_node = fixture.sim.player_home_node()
	if world != null:
		world._world_flow.sim = fixture.sim
	_show_strategic()
	_refresh_metrics()
	status.text = "Fixture reset · campaign save untouched (test_mode)"


func _refresh_metrics() -> void:
	var lines: PackedStringArray = []
	lines.append("Node %d · profile %dx%d" % [current_node, current_size.x, current_size.y])
	lines.append("Specimen=%d BG-test=%d" % [fixture.specimen_node, fixture.bg_test_node])
	var code: String = fixture.primary_type_for(current_node)
	if current_node == fixture.bg_test_node:
		code = "BG"
	if code != "":
		var area: Dictionary = fixture.project_node(current_node, current_size, code, false)
		var m: Dictionary = fixture.metrics_for(area)
		lines.append("fit=%s" % m["fit"])
		lines.append("dungeon %dx%d · %.1f%%" % [m["dungeon_w"], m["dungeon_h"], m["dungeon_pct"]])
		lines.append("free=%d exits=%d clear=%s" % [m["free_tiles"], m["exits"], m["exits_clear"]])
		lines.append("path_in=%s rooms=%s plaza=%s" % [m["path_in"], m["rooms_reachable"], m["settlement_reachable"]])
	else:
		lines.append("(no dungeon type on this node)")
	lines.append("BG production unassigned=%s" % fixture.production_bg_unassigned())
	metrics_label.text = "\n".join(lines)
	board_draw.queue_redraw()


func _hex_color(terrain: String) -> Color:
	match terrain:
		"forest":
			return Color(0.2, 0.45, 0.22)
		"hills":
			return Color(0.55, 0.35, 0.22)
		"mountains":
			return Color(0.45, 0.45, 0.5)
		"pasture":
			return Color(0.4, 0.6, 0.3)
		"fields":
			return Color(0.7, 0.65, 0.25)
		"desert":
			return Color(0.75, 0.7, 0.45)
		_:
			return Color(0.3, 0.3, 0.35)


func _axial_to_pixel(q: int, r: int, origin: Vector2, size: float) -> Vector2:
	var x := size * (sqrt(3.0) * q + sqrt(3.0) / 2.0 * r)
	var y := size * (1.5 * r)
	return origin + Vector2(x, y)


func _draw_strategic() -> void:
	if not strategic_mode or fixture == null:
		return
	var board: DmbHexBoard = fixture.sim.board
	var origin := Vector2(size.x * 0.55, size.y * 0.42)
	var hs := mini(size.x, size.y) * 0.055
	# Hexes
	for h in board.hexes:
		var c := _axial_to_pixel(int(h["q"]), int(h["r"]), origin, hs)
		var col := _hex_color(str(h["terrain"])) if show_terrain else Color(0.25, 0.28, 0.32)
		_draw_hex(board_draw, c, hs * 0.95, col)
		if show_hex_ids:
			board_draw.draw_string(ThemeDB.fallback_font, c + Vector2(-10, 4), "H%d" % int(h["id"]), HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color.WHITE)
	# Connectivity / edges
	if show_connectivity:
		for e in board.edges:
			var a: Dictionary = board.nodes[e["nodes"][0]]
			var b: Dictionary = board.nodes[e["nodes"][1]]
			var pa := _node_pixel(a, origin, hs)
			var pb := _node_pixel(b, origin, hs)
			board_draw.draw_line(pa, pb, Color(1, 1, 1, 0.15), 1.0)
	# Nodes
	for n in board.nodes:
		var p := _node_pixel(n, origin, hs)
		var nid: int = int(n["id"])
		var col := Color(0.7, 0.75, 0.8, 0.7)
		if show_candidates and fixture.by_node.has(nid):
			col = Color(1.0, 0.55, 0.15, 0.95)
		if show_settlements:
			for s in fixture.settlements:
				if int(s["node"]) == nid:
					col = Color(0.2, 0.85, 1.0, 1.0)
		if nid == current_node:
			board_draw.draw_circle(p, 7, Color(1, 1, 0.2, 1))
		board_draw.draw_circle(p, 4, col)
		if show_node_ids:
			board_draw.draw_string(ThemeDB.fallback_font, p + Vector2(5, -2), str(nid), HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.9, 0.95, 1.0))
		if show_candidates and fixture.by_node.has(nid):
			var types: Array = fixture.by_node[nid]["types"]
			board_draw.draw_string(ThemeDB.fallback_font, p + Vector2(5, 10), ",".join(PackedStringArray(types)), HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color(1.0, 0.8, 0.4))
	# Legend
	board_draw.draw_string(ThemeDB.fallback_font, Vector2(230, size.y - 48), "Cyan=settlement  Orange=dungeon candidate  Yellow=selected", HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.85, 0.9, 0.95))
	board_draw.draw_string(ThemeDB.fallback_font, Vector2(230, size.y - 32), "Board: %d hexes (production Catan), %d nodes — not a mock graph" % [board.hexes.size(), board.nodes.size()], HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.75, 0.8, 0.85))


func _node_pixel(n: Dictionary, origin: Vector2, hs: float) -> Vector2:
	# Average of touching hex centres.
	var acc := Vector2.ZERO
	var board: DmbHexBoard = fixture.sim.board
	for hid in n["hexes"]:
		var h: Dictionary = board.hexes[hid]
		acc += _axial_to_pixel(int(h["q"]), int(h["r"]), origin, hs)
	return acc / float(n["hexes"].size())


func _draw_hex(canvas: Control, centre: Vector2, radius: float, color: Color) -> void:
	var pts := PackedVector2Array()
	for i in range(6):
		var ang := deg_to_rad(60.0 * i - 30.0)
		pts.append(centre + Vector2(cos(ang), sin(ang)) * radius)
	canvas.draw_colored_polygon(pts, color)
	for i in range(6):
		canvas.draw_line(pts[i], pts[(i + 1) % 6], Color(0, 0, 0, 0.45), 1.0)


func _on_board_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT):
		return
	var origin := Vector2(size.x * 0.55, size.y * 0.42)
	var hs := mini(size.x, size.y) * 0.055
	var best := -1
	var best_d := 9999.0
	for n in fixture.sim.board.nodes:
		var p := _node_pixel(n, origin, hs)
		var d := p.distance_to(event.position)
		if d < best_d:
			best_d = d
			best = int(n["id"])
	if best >= 0 and best_d < 18.0:
		current_node = best
		board_draw.queue_redraw()
		_refresh_metrics()


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED and board_draw:
		board_draw.queue_redraw()


func _exit_tree() -> void:
	DmbSettlementLayout.FORCE_DIMS = Vector2i.ZERO
	WorldFlow.test_augment = Callable()
	var adv := get_node_or_null("/root/Adventure")
	if adv and Runner.is_active():
		Runner.end(adv)
