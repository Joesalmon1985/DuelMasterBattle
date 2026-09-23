extends Control
## Dungeon World Playtest shell.
## Boots a disposable isolated session on the real production board.
## Default experience: start in the home settlement and play. Strategic board
## and developer tools are optional (M / Esc → Dungeon Test Tools).

const OverworldScene = preload("res://client/scenes/overworld.tscn")
const DWRunner = preload("res://sim/world/dungeon_world_test_runner.gd")

var world: Node2D
var current_size: Vector2i = Vector2i(73, 55)
var show_hex_ids := true
var show_node_ids := false
var show_settlements := true
var show_candidates := true
var show_terrain := true
var show_connectivity := false
var strategic_mode := false
var board_draw: Control
var badge: Label
var map_hint: Label


func _ready() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-DUNGEON-WORLD")
	var world_seed: int = int(OS.get_environment("DMB_SEED")) if OS.get_environment("DMB_SEED") != "" else 507
	var sz := OS.get_environment("DMB_NODE_SIZE")
	if sz != "" and "x" in sz:
		var parts := sz.split("x")
		current_size = Vector2i(int(parts[0]), int(parts[1]))
	DWRunner.prepare(world_seed, current_size)
	_build_chrome()
	_boot_play()


func _boot_play() -> void:
	strategic_mode = false
	board_draw.visible = false
	world = OverworldScene.instantiate()
	world.name = "Overworld"
	add_child(world)
	# After overworld boots, point flow at fixture sim (boot already did this).
	await get_tree().process_frame
	if world != null and DWRunner.fixture != null:
		world._world_flow.sim = DWRunner.fixture.sim
	_refresh_badge()


func _build_chrome() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	board_draw = Control.new()
	board_draw.set_anchors_preset(Control.PRESET_FULL_RECT)
	board_draw.visible = false
	board_draw.draw.connect(_draw_strategic)
	board_draw.gui_input.connect(_on_board_input)
	add_child(board_draw)

	var layer := CanvasLayer.new()
	layer.layer = 45
	add_child(layer)

	badge = Label.new()
	badge.text = "DUNGEON WORLD PLAYTEST — disposable world"
	badge.add_theme_font_size_override("font_size", 11)
	badge.add_theme_color_override("font_color", Color(0.85, 0.9, 0.75, 0.9))
	badge.position = Vector2(8, 8)
	layer.add_child(badge)

	map_hint = Label.new()
	map_hint.text = "M: map · Esc: menu"
	map_hint.add_theme_font_size_override("font_size", 10)
	map_hint.add_theme_color_override("font_color", Color(0.7, 0.75, 0.7, 0.7))
	map_hint.position = Vector2(8, 24)
	layer.add_child(map_hint)


func _refresh_badge() -> void:
	if DWRunner.is_active():
		badge.text = "DUNGEON WORLD PLAYTEST — home wn_%d · dungeon wn_%d (%s)" % [
			DWRunner.home_node, DWRunner.playtest_node, DWRunner.playtest_type]
	else:
		badge.text = "DUNGEON WORLD PLAYTEST — disposable world"


func toggle_strategic_map() -> void:
	strategic_mode = not strategic_mode
	board_draw.visible = strategic_mode
	if world:
		world.visible = not strategic_mode
	if strategic_mode:
		board_draw.queue_redraw()
		map_hint.text = "M / click: close map · yellow = you · orange = dungeon candidates"
	else:
		map_hint.text = "M: map · Esc: menu"
	_refresh_badge()


func open_test_tools() -> void:
	if world == null or world._dialogue == null:
		return
	while true:
		var choice: String = await world._dialogue.choose_async("Dungeon Test Tools", [
			"Close",
			"Strategic Board",
			"Show Test Labels",
			"Show Dungeon Bounds",
			"Size 65×49",
			"Size 73×55",
			"Size 81×61",
			"Teleport to playtest dungeon",
			"Teleport home",
			"Reset Dungeon",
			"Reset World",
			"Playtest info",
		])
		match choice:
			"Strategic Board":
				if not strategic_mode:
					toggle_strategic_map()
				return
			"Show Test Labels":
				DWRunner.show_test_labels = not DWRunner.show_test_labels
				_reload_local()
			"Show Dungeon Bounds":
				DWRunner.show_dungeon_bounds = not DWRunner.show_dungeon_bounds
				_reload_local()
			"Size 65×49":
				_apply_node_size(Vector2i(65, 49))
			"Size 73×55":
				_apply_node_size(Vector2i(73, 55))
			"Size 81×61":
				_apply_node_size(Vector2i(81, 61))
			"Teleport to playtest dungeon":
				_teleport_node(DWRunner.playtest_node)
				return
			"Teleport home":
				_teleport_node(DWRunner.home_node)
				return
			"Reset Dungeon":
				DWRunner.reset_dungeon(get_node("/root/Adventure"))
				_reload_local()
			"Reset World":
				var adv: Node = get_node("/root/Adventure")
				if world:
					world.queue_free()
					world = null
				DWRunner.reset_world(adv)
				_boot_play()
				return
			"Playtest info":
				await world._dialogue.say_async("Playtest", DWRunner.playtest_info())
			_:
				return


func _apply_node_size(sz: Vector2i) -> void:
	current_size = sz
	DWRunner.node_size = sz
	DmbSettlementLayout.FORCE_DIMS = sz
	_reload_local()


func _reload_local() -> void:
	if world == null or strategic_mode:
		return
	world.load_area(world.area_id, world._john_pos, world._john_facing)


func _teleport_node(nid: int) -> void:
	if world == null or nid < 0:
		return
	strategic_mode = false
	board_draw.visible = false
	world.visible = true
	var aid := DmbNodeProjection.area_id(nid)
	var area: Dictionary = world._world_flow.area_for(aid)
	var start: Array = area.get("player_start", [current_size.x / 2, current_size.y - 4])
	if area.has("embedded_dungeon"):
		var emb: Dictionary = area["embedded_dungeon"]
		if emb.has("approach"):
			start = emb["approach"]
	world.load_area(aid, Vector2i(int(start[0]), int(start[1])), "up")
	get_node("/root/Adventure").state["world_node"] = nid
	_refresh_badge()


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


func _axial_to_pixel(q: int, r: int, origin: Vector2, hs: float) -> Vector2:
	var x := hs * (sqrt(3.0) * q + sqrt(3.0) / 2.0 * r)
	var y := hs * (1.5 * r)
	return origin + Vector2(x, y)


func _draw_strategic() -> void:
	if not strategic_mode or DWRunner.fixture == null:
		return
	var board: DmbHexBoard = DWRunner.fixture.sim.board
	var origin := Vector2(size.x * 0.5, size.y * 0.42)
	var hs := mini(size.x, size.y) * 0.055
	for h in board.hexes:
		var c := _axial_to_pixel(int(h["q"]), int(h["r"]), origin, hs)
		var col := _hex_color(str(h["terrain"])) if show_terrain else Color(0.25, 0.28, 0.32)
		_draw_hex(board_draw, c, hs * 0.95, col)
		if show_hex_ids:
			board_draw.draw_string(ThemeDB.fallback_font, c + Vector2(-10, 4), "H%d" % int(h["id"]), HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color.WHITE)
	if show_connectivity:
		for e in board.edges:
			var a: Dictionary = board.nodes[e["nodes"][0]]
			var b: Dictionary = board.nodes[e["nodes"][1]]
			board_draw.draw_line(_node_pixel(a, origin, hs), _node_pixel(b, origin, hs), Color(1, 1, 1, 0.15), 1.0)
	var cur: int = int(get_node("/root/Adventure").state.get("world_node", DWRunner.home_node))
	for n in board.nodes:
		var p := _node_pixel(n, origin, hs)
		var nid: int = int(n["id"])
		var col := Color(0.7, 0.75, 0.8, 0.7)
		if show_candidates and DWRunner.fixture.by_node.has(nid):
			col = Color(1.0, 0.55, 0.15, 0.95)
		if show_settlements:
			for s in DWRunner.fixture.settlements:
				if int(s["node"]) == nid:
					col = Color(0.2, 0.85, 1.0, 1.0)
		if nid == DWRunner.playtest_node:
			col = Color(0.95, 0.35, 0.85, 1.0)
		if nid == cur:
			board_draw.draw_circle(p, 8, Color(1, 1, 0.2, 1))
		board_draw.draw_circle(p, 4, col)
		if show_node_ids:
			board_draw.draw_string(ThemeDB.fallback_font, p + Vector2(5, -2), str(nid), HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.9, 0.95, 1.0))
	board_draw.draw_string(ThemeDB.fallback_font, Vector2(16, size.y - 48),
		"Cyan=settlement  Orange=candidate  Magenta=playtest dungeon  Yellow=you",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.85, 0.9, 0.95))
	board_draw.draw_string(ThemeDB.fallback_font, Vector2(16, size.y - 32),
		"Board: %d hexes · %d nodes · %d edges — production Catan" % [board.hexes.size(), board.nodes.size(), board.edges.size()],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.75, 0.8, 0.85))
	board_draw.draw_string(ThemeDB.fallback_font, Vector2(16, size.y - 16),
		DWRunner.playtest_info().split("\n")[0],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.8, 0.85, 0.7))


func _node_pixel(n: Dictionary, origin: Vector2, hs: float) -> Vector2:
	var acc := Vector2.ZERO
	var board: DmbHexBoard = DWRunner.fixture.sim.board
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
	# Close map on click — primary play stays local.
	toggle_strategic_map()


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED and board_draw:
		board_draw.queue_redraw()


func _exit_tree() -> void:
	var adv := get_node_or_null("/root/Adventure")
	if adv and DWRunner.is_active():
		DWRunner.end(adv)
	else:
		DWRunner.clear()
