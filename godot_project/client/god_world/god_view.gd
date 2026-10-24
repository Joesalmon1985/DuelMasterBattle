extends Node2D
class_name GodView

## The one continuous world of God World, drawn from the authoritative snapshot (docs/GOD_WORLD_PRD.md sections 4, 7, 8, 11). Positions arrive
## in board units (hex circumradius 1) and are multiplied by HEX_PX; nothing here decides anything: the simulation owns every number, this
## node owns the picture. Levels of detail by camera zoom (7.3): close and village (buildings, workers, parties), region (markers, roads,
## journeys), whole board (hexes, tokens, dots). The same entity ids are used at every level, so a tap resolves to the same thing.

const HybridArt = preload("res://client/hybrid/hybrid_art.gd")
const AssetLoader = preload("res://client/scripts/asset_loader.gd")

const HEX_PX := 900.0
const ZOOM_DETAIL := 0.28  # buildings and people from here in
const ZOOM_REGION := 0.12  # markers, roads and journeys between here and detail; below: the whole board
const ROLE_COLOR := {
	"WOOD": Color(0.22, 0.46, 0.2), "BRICK": Color(0.62, 0.38, 0.22), "SHEEP": Color(0.55, 0.72, 0.32), "WHEAT": Color(0.82, 0.7, 0.3),
	"ORE": Color(0.48, 0.5, 0.56), "DESERT": Color(0.86, 0.78, 0.55),
}
const SCALE_BY_GAME := {"widelands": 2.0, "openra": 2.0, "mindustry": 2.5}
const MIND_PAD := Color(0.17, 0.17, 0.2)

var board: Dictionary = {}
var snapshot: Dictionary = {}
var art = HybridArt.new()
var zoom := 0.5
var show_overlay := false
var faction_colors: Dictionary = {}
var selected_id := ""
var _font: Font
var _scenery: Dictionary = {}  # hex id -> Array of {x, y, art}
var _part_cache: Dictionary = {}
var _hit: Array = []  # [{id, rect(world px), priority}] rebuilt each draw for picking
var clock := 0.0
var missing: Array[String] = []


func _ready() -> void:
	art.load_catalogue()
	_font = ThemeDB.fallback_font


func set_board(b: Dictionary) -> void:
	board = b
	_scenery.clear()
	var seed_ := int(b.get("cosmetic_seed", 1))
	var rng := RandomNumberGenerator.new()
	for h in b.get("hexes", []):
		rng.seed = seed_ * 1000003 + hash(str(h["id"]))
		var role := str(h["role"])
		var arts: Array = []
		match role:
			"WOOD": arts = ["widelands.beech.old", "widelands.alder.old", "widelands.aspen.old", "widelands.birch.old"]
			"SHEEP": arts = ["widelands.birch.old"]
			"WHEAT": arts = ["widelands.aspen.old"]
			_: arts = []
		var n := 14 if role == "WOOD" else (3 if arts.size() > 0 else 0)
		var pts: Array = []
		for i in n:
			var ang := rng.randf() * TAU
			var r := 0.12 + rng.randf() * 0.42
			pts.append({"x": float(h["x"]) + cos(ang) * r, "y": float(h["y"]) + sin(ang) * r * 0.9, "art": arts[rng.randi() % arts.size()], "phase": rng.randf() * TAU})
		_scenery[str(h["id"])] = pts
	queue_redraw()


func set_snapshot(s: Dictionary) -> void:
	snapshot = s
	for f in s.get("factions", []):
		faction_colors[str(f["id"])] = Color(str(f["colour"]))
	art.faction_colors = faction_colors
	queue_redraw()


func _process(delta: float) -> void:
	clock += delta
	if zoom >= ZOOM_REGION:
		queue_redraw()  # animated sheets and moving journeys; the whole-board view redraws on snapshots only


static func bu(x: float, y: float) -> Vector2:
	return Vector2(x, y) * HEX_PX


func board_bounds() -> Rect2:
	var b: Array = board.get("bounds", [0, 0, 1, 1])
	return Rect2(bu(float(b[0]), float(b[1])), bu(float(b[2]) - float(b[0]), float(b[3]) - float(b[1])))


# ------------------------------------------------------------------ picking

## The semantic id drawn under a world point, by visible draw order and an enlarged touch area; "" when nothing is there.
func pick(world_pos: Vector2, radius_px: float) -> String:
	var best := ""
	var best_key := -1.0
	for h in _hit:
		var r: Rect2 = h["rect"]
		var grown := r.grow(radius_px)
		if grown.has_point(world_pos):
			var centre := r.get_center()
			var key := float(h["priority"]) * 100000.0 - centre.distance_to(world_pos)
			if key > best_key:
				best_key = key
				best = str(h["id"])
	if best != "":
		return best
	# empty ground inside a hex selects the hex
	for h in board.get("hexes", []):
		if bu(float(h["x"]), float(h["y"])).distance_to(world_pos) < HEX_PX * 0.86:
			return str(h["id"])
	return ""


func anchor_of(id: String) -> Vector2:
	"""Where a labelled thing is right now (world px); journeys move, so this is asked every frame."""
	for h in _hit:
		if str(h["id"]) == id:
			var r: Rect2 = h["rect"]
			return Vector2(r.get_center().x, r.position.y)
	var kind := id.get_slice(":", 0)
	var rest := id.substr(kind.length() + 1)
	if kind == "hex":
		for h in board.get("hexes", []):
			if str(h["id"]) == id:
				return bu(float(h["x"]), float(h["y"]))
	if kind == "village" or kind == "remains":
		for v in snapshot.get("villages", []):
			if str(v["id"]) == rest:
				return bu(float(v["x"]), float(v["y"])) - Vector2(0, 60)
	if kind == "journey":
		for j in snapshot.get("journeys", []):
			if str(j["id"]) == rest:
				return bu(float(j["x"]), float(j["y"])) - Vector2(0, 40)
	if kind == "road":
		for r in snapshot.get("roads", []):
			if str(r["id"]) == rest:
				return (bu(float(r["a"][0]), float(r["a"][1])) + bu(float(r["b"][0]), float(r["b"][1]))) * 0.5
	return Vector2.INF


# ------------------------------------------------------------------ drawing

func _draw() -> void:
	_hit.clear()
	if board.is_empty():
		return
	var vp_rect := _visible_world_rect()
	_draw_hexes(vp_rect)
	_draw_roads(vp_rect)
	if zoom < ZOOM_REGION:
		_draw_board_level(vp_rect)
		return
	if zoom < ZOOM_DETAIL:
		_draw_region_level(vp_rect)
		return
	_draw_detail_level(vp_rect)


func _visible_world_rect() -> Rect2:
	var xf := get_viewport().get_canvas_transform().affine_inverse()
	var vis := get_viewport().get_visible_rect().size
	var a := xf * Vector2.ZERO
	var b := xf * vis
	return Rect2(a, b - a).abs().grow(HEX_PX * 0.6)


func _draw_hexes(vp: Rect2) -> void:
	for h in board.get("hexes", []):
		var c := bu(float(h["x"]), float(h["y"]))
		if not vp.has_point(c) and vp.grow(HEX_PX).has_point(c) == false:
			continue
		var pts := PackedVector2Array()
		for k in h["corners"]:
			pts.append(bu(float(k[0]), float(k[1])))
		var col: Color = ROLE_COLOR.get(str(h["role"]), Color.GRAY)
		var shade := 0.94 + 0.06 * sin(float(int(h["q"]) * 3 + int(h["r"]) * 7))
		draw_colored_polygon(pts, col * Color(shade, shade, shade, 1.0))
		var border := pts.duplicate()
		border.append(pts[0])
		draw_polyline(border, Color(0.08, 0.1, 0.08, 0.55), 6.0 if zoom < ZOOM_REGION else 3.0)
		var token := int(h.get("token", 0))
		if token > 0 and (show_overlay or zoom < ZOOM_DETAIL * 1.6):
			var rad := 70.0 if zoom < ZOOM_REGION else (56.0 if zoom < ZOOM_DETAIL else 44.0)
			var hot := token == 6 or token == 8
			draw_circle(c, rad, Color(0.96, 0.93, 0.82, 0.92))
			draw_arc(c, rad, 0, TAU, 32, Color(0.2, 0.15, 0.1, 0.8), 3.0)
			var fs := int(rad * 1.1)
			var s := str(token)
			var w := _font.get_string_size(s, HORIZONTAL_ALIGNMENT_CENTER, -1, fs).x
			draw_string(_font, c + Vector2(-w * 0.5, fs * 0.36), s, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color(0.75, 0.1, 0.1) if hot else Color(0.12, 0.1, 0.08))
			var pips := int(h.get("pips", 0))
			for i in pips:
				draw_circle(c + Vector2((i - (pips - 1) * 0.5) * rad * 0.26, rad * 0.68), rad * 0.07, Color(0.75, 0.1, 0.1) if hot else Color(0.12, 0.1, 0.08))
		if show_overlay and zoom >= ZOOM_REGION:
			var nm: String = str(snapshot.get("role_names", {}).get(str(h["role"]), str(h["role"]))).capitalize()
			if str(h["role"]) == "DESERT":
				nm = "Desert"
			var fs2 := 40
			var w2 := _font.get_string_size(nm, HORIZONTAL_ALIGNMENT_CENTER, -1, fs2).x
			draw_string(_font, c + Vector2(-w2 * 0.5, 120), nm, HORIZONTAL_ALIGNMENT_LEFT, -1, fs2, Color(0.1, 0.08, 0.05, 0.85))


func _draw_roads(vp: Rect2) -> void:
	for r in snapshot.get("roads", []):
		var a := bu(float(r["a"][0]), float(r["a"][1]))
		var b := bu(float(r["b"][0]), float(r["b"][1]))
		if not vp.grow(HEX_PX).has_point(a) and not vp.grow(HEX_PX).has_point(b):
			continue
		var col: Color = faction_colors.get(str(r["faction"]), Color.WHITE)
		var status := str(r["status"])
		var width := 26.0 if zoom >= ZOOM_REGION else 46.0
		if status == "historical":
			draw_line(a, b, Color(0.35, 0.32, 0.28, 0.55), width * 0.5)
		elif status == "building":
			var t := float(r.get("progress", 0.0))
			var from := a if str(r.get("from_node", "")) == "" or _node_pos(str(r.get("from_node", ""))) == a else b
			var to := b if from == a else a
			draw_line(a, b, Color(0.3, 0.28, 0.24, 0.5), width * 0.6)
			draw_line(from, from.lerp(to, t), Color(0.25, 0.2, 0.15), width + 8.0)
			draw_line(from, from.lerp(to, t), col, width)
			if zoom >= ZOOM_DETAIL:
				_draw_worker(from.lerp(to, t), "widelands.barbarians_carrier_worker", (to - from).angle(), true)
				_hit.append({"id": "road:" + str(r["id"]), "rect": Rect2(from.lerp(to, t) - Vector2(40, 80), Vector2(80, 90)), "priority": 3})
		else:
			draw_line(a, b, Color(0.22, 0.18, 0.14), width + 8.0)
			draw_line(a, b, col.lerp(Color(0.6, 0.5, 0.4), 0.45), width)
		if status != "historical":
			var mid := (a + b) * 0.5
			var d := (b - a).normalized() * HEX_PX * 0.22
			var n := Vector2(-d.y, d.x).normalized() * width
			_hit.append({"id": "road:" + str(r["id"]), "rect": Rect2(mid - d - n, (d + n) * 2.0).abs(), "priority": 1})


func _node_pos(nid: String) -> Vector2:
	var p: Array = board.get("nodes", {}).get(nid, [0, 0])
	return bu(float(p[0]), float(p[1]))


func _draw_board_level(vp: Rect2) -> void:
	for v in snapshot.get("villages", []):
		var c := bu(float(v["x"]), float(v["y"]))
		var status := str(v["status"])
		if status == "pending":
			continue
		var col: Color = faction_colors.get(str(v["faction"]), Color.WHITE)
		var r := 90.0 if int(v.get("level", 1)) >= 2 else 60.0
		if status == "historical":
			draw_circle(c, 40.0, Color(0.3, 0.28, 0.25, 0.7))
			continue
		draw_circle(c, r + 14.0, Color(0.05, 0.05, 0.05, 0.8))
		draw_circle(c, r, col)
		_hit.append({"id": "village:" + str(v["id"]), "rect": Rect2(c - Vector2(r, r), Vector2(r, r) * 2.0), "priority": 5})
	for j in snapshot.get("journeys", []):
		var c := bu(float(j["x"]), float(j["y"]))
		draw_circle(c, 34.0, Color(0.05, 0.05, 0.05, 0.8))
		draw_circle(c, 26.0, faction_colors.get(str(j["faction"]), Color.WHITE))


func _draw_region_level(vp: Rect2) -> void:
	for v in snapshot.get("villages", []):
		var c := bu(float(v["x"]), float(v["y"]))
		if not vp.has_point(c):
			continue
		var status := str(v["status"])
		if status == "pending":
			continue
		var col: Color = faction_colors.get(str(v["faction"]), Color.WHITE)
		if status == "historical":
			_draw_remains(v, c)
			continue
		var level := int(v.get("level", 1))
		var size := 150.0 if level >= 2 else 100.0
		var rect := Rect2(c - Vector2(size * 0.5, size * 0.9), Vector2(size, size))
		draw_rect(rect, Color(0.08, 0.08, 0.1, 0.85), true)
		draw_rect(rect.grow(-10.0), col, true)
		var roof := PackedVector2Array([rect.position + Vector2(-10, 0), Vector2(c.x, rect.position.y - size * 0.45), rect.position + Vector2(size + 10, 0)])
		draw_colored_polygon(roof, Color(0.35, 0.2, 0.15))
		if level >= 2:
			draw_rect(Rect2(c + Vector2(-size * 0.15, -size * 1.5), Vector2(size * 0.3, size * 0.6)), col.darkened(0.3), true)
		_hit.append({"id": "village:" + str(v["id"]), "rect": rect.grow(20.0), "priority": 5})
		var units: Array = v.get("units", [])
		if units.size() > 0:
			var g := c + Vector2(size * 0.8, -20)
			draw_circle(g, 34.0, Color(0.1, 0.1, 0.1, 0.8))
			var s := str(units.size())
			draw_string(_font, g + Vector2(-12, 12), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 34, Color(1, 1, 1))
	_draw_journeys(vp, false)


func _draw_remains(v: Dictionary, c: Vector2) -> void:
	var item: Dictionary = art.items.get("widelands.warehouse", {})
	var tex: Texture2D = art._tex("widelands.warehouse")
	if tex != null and zoom >= ZOOM_REGION:
		var sc := 1.6
		var hs: Array = item.get("hotspot", [0, 0])
		var size := Vector2(tex.get_width(), tex.get_height()) * sc
		draw_texture_rect(tex, Rect2(c - Vector2(float(hs[0]), float(hs[1])) * sc, size), false, Color(0.55, 0.52, 0.5, 0.6))
		_hit.append({"id": "remains:" + str(v["id"]), "rect": Rect2(c - Vector2(float(hs[0]), float(hs[1])) * sc, size), "priority": 2})
	else:
		draw_circle(c, 40.0, Color(0.3, 0.28, 0.25, 0.6))


func _draw_detail_level(vp: Rect2) -> void:
	var items: Array = []  # {y, kind, data...} painter's order
	for hid in _scenery:
		var pts: Array = _scenery[hid]
		for p in pts:
			var c := bu(float(p["x"]), float(p["y"]))
			if vp.has_point(c) and not _near_station(p):
				items.append({"y": c.y, "kind": "tree", "pos": c, "art": str(p["art"]), "phase": float(p["phase"])})
	for v in snapshot.get("villages", []):
		var c := bu(float(v["x"]), float(v["y"]))
		if not vp.grow(HEX_PX).has_point(c):
			continue
		var status := str(v["status"])
		if status == "pending":
			continue
		if status == "historical":
			items.append({"y": c.y, "kind": "remains", "v": v, "pos": c})
			continue
		var col: Color = faction_colors.get(str(v["faction"]), Color.WHITE)
		var building: bool = status == "building" or status == "rebuilding" or v.has("construction")
		items.append({"y": c.y + 1.0, "kind": "warehouse", "v": v, "pos": c, "col": col, "scaffold": building, "progress": float(v.get("construction", {}).get("progress", 1.0)) if v.has("construction") else 1.0})
		var ready := bool(v.get("ready", true))
		for d in v.get("districts", []):
			for s in d.get("stations", []):
				for b in s.get("buildings", []):
					var bp := bu(float(b["x"]), float(b["y"]))
					items.append({"y": bp.y, "kind": "building", "art": str(b["art"]), "pos": bp, "id": "station:" + str(s["id"]), "col": col, "scaffold": not ready or status != "operational",
						"working": ready and status == "operational", "role": str(d["role"]), "v": v})
			# a worker per district walking its first row (presentation)
			if d.get("count", 0) > 0 and ready and status == "operational" and str(d.get("worker", "")) != "":
				var s0: Dictionary = d["stations"][0]
				var sp := bu(float(s0["x"]), float(s0["y"]))
				var t := fmod(clock * 0.12 + float(hash(str(v["id"]) + str(d["hex"])) % 100) * 0.01, 1.0)
				var wp := sp.lerp(c, 0.15 + 0.7 * (abs(t * 2.0 - 1.0)))
				items.append({"y": wp.y, "kind": "worker", "art": str(d["worker"]), "pos": wp, "angle": (c - sp).angle() if t < 0.5 else (sp - c).angle(), "load": t < 0.5})
		var mil: Variant = v.get("military")
		if mil != null and typeof(mil) == TYPE_DICTIONARY:
			var mp := bu(float(mil["x"]), float(mil["y"]))
			items.append({"y": mp.y, "kind": "building", "art": str(mil["art"]), "pos": mp, "id": "facility:" + str(v["id"]), "col": col, "scaffold": not ready, "working": false, "role": "MIL", "v": v})
			var slots: Array = mil.get("slots", [])
			for u in v.get("units", []):
				var slot := int(u["slot"])
				if slot < slots.size():
					var up := bu(float(slots[slot][0]), float(slots[slot][1]))
					items.append({"y": up.y, "kind": "unit", "art": str(u["art"]), "pos": up, "id": "unit:" + str(u["id"]), "col": col})
	items.sort_custom(func(a, b): return a["y"] < b["y"])
	for it in items:
		match str(it["kind"]):
			"tree": _draw_tree(it)
			"warehouse": _draw_warehouse(it)
			"building": _draw_building(it)
			"worker": _draw_worker(it["pos"], it["art"], it["angle"], it["load"])
			"unit": _draw_unit(it)
			"remains": _draw_remains(it["v"], it["pos"])
	_draw_journeys(vp, true)


func _near_station(p: Dictionary) -> bool:
	for v in snapshot.get("villages", []):
		if str(v["status"]) in ["pending", "historical"]:
			continue
		if abs(float(v["x"]) - float(p["x"])) > 1.3 or abs(float(v["y"]) - float(p["y"])) > 1.3:
			continue
		for d in v.get("districts", []):
			for s in d.get("stations", []):
				if abs(float(s["x"]) - float(p["x"])) < 0.2 and abs(float(s["y"]) - float(p["y"])) < 0.2:
					return true
		var mil: Variant = v.get("military")
		if mil != null and typeof(mil) == TYPE_DICTIONARY and abs(float(mil["x"]) - float(p["x"])) < 0.25 and abs(float(mil["y"]) - float(p["y"])) < 0.25:
			return true
	return false


func _item_scale(item: Dictionary) -> float:
	return float(SCALE_BY_GAME.get(str(item.get("game", "widelands")), 2.0))


func _draw_sheet(item: Dictionary, pos: Vector2, tint: Color, sc_mul: float = 1.0, fake_entity: Dictionary = {}) -> Rect2:
	var tex: Texture2D = art._frame_texture(item, fake_entity) if str(item.get("mode", "")) == "sequence" else art._tex(str(item.get("id", "")))
	if tex == null:
		var k := str(item.get("id", "?"))
		if k not in missing:
			missing.append(k)
		draw_rect(Rect2(pos - Vector2(40, 60), Vector2(80, 60)), Color(1, 0, 1, 0.5), true)
		return Rect2(pos - Vector2(40, 60), Vector2(80, 60))
	var sc := _item_scale(item) * sc_mul
	var hs: Array = item.get("hotspot", [0, 0])
	var fsize: Vector2 = art._frame_size(item, tex)
	var src: Rect2 = art._source_rect(item, tex, fake_entity)
	var top_left := pos - Vector2(float(hs[0]), float(hs[1])) * sc
	if hs[0] == 0 and hs[1] == 0 and str(item.get("game", "")) == "openra":
		top_left = pos - Vector2(fsize.x * 0.5, fsize.y * 0.85) * sc
	var rect := Rect2(top_left, fsize * sc)
	draw_texture_rect_region(tex, rect, src, tint)
	return rect


func _draw_mindustry(item: Dictionary, pos: Vector2, tint: Color, working: bool) -> Rect2:
	var sc := _item_scale(item)
	var w := float(item.get("width", 64)) * sc
	var rect := Rect2(pos - Vector2(w * 0.5, w * 0.8), Vector2(w, w))
	draw_rect(rect.grow(10.0), MIND_PAD * tint, true)  # the industrial pad: a top-view machine reads as a roof on it
	draw_rect(rect.grow(10.0), Color(0.05, 0.05, 0.06), false, 3.0)
	var parts: Array = item.get("parts", [])
	if parts.is_empty():
		var tex: Texture2D = art._tex(str(item.get("id", "")))
		if tex != null:
			draw_texture_rect(tex, rect, false, tint)
		return rect
	for p in parts:
		var tex2: Texture2D = _part_tex(str(p.get("file", "")))
		if tex2 == null:
			continue
		var anim := str(p.get("anim", "none"))
		if anim == "spin_when_working" and working:
			draw_set_transform(rect.get_center(), clock * 2.5, Vector2.ONE)
			draw_texture_rect(tex2, Rect2(-rect.size * 0.5, rect.size), false, tint)
			draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
		else:
			draw_texture_rect(tex2, rect, false, tint)
	return rect


func _part_tex(path: String) -> Texture2D:
	if _part_cache.has(path):
		return _part_cache[path]
	var t: Texture2D = AssetLoader.load_texture(path)
	_part_cache[path] = t
	return t


func _draw_building(it: Dictionary) -> void:
	var item: Dictionary = art.items.get(str(it["art"]), {})
	var pos: Vector2 = it["pos"]
	var tint := Color(1, 1, 1, 1)
	if bool(it.get("scaffold", false)):
		tint = Color(0.8, 0.8, 0.85, 0.55)
	var rect: Rect2
	if item.is_empty():
		rect = Rect2(pos - Vector2(50, 70), Vector2(100, 70))
		draw_rect(rect, Color(0.5, 0.3, 0.6, 0.7), true)
	elif str(item.get("game", "")) == "mindustry":
		rect = _draw_mindustry(item, pos, tint, bool(it.get("working", false)))
	else:
		rect = _draw_sheet(item, pos, tint, 1.0, {"facing": "s", "class": "building"})
	if bool(it.get("scaffold", false)):
		draw_rect(rect, Color(0.9, 0.75, 0.3, 0.9), false, 4.0)
	# a faction accent at the door
	draw_circle(pos + Vector2(0, 6), 9.0, Color(0.05, 0.05, 0.05, 0.8))
	draw_circle(pos + Vector2(0, 6), 6.0, it["col"])
	if bool(it.get("working", false)) and str(it.get("role", "")) != "MIL":
		var puff := fmod(clock * 0.4 + float(hash(str(it["id"])) % 50) * 0.02, 1.0)
		draw_circle(Vector2(rect.get_center().x + 10.0, rect.position.y - puff * 60.0), 8.0 + puff * 10.0, Color(0.85, 0.85, 0.85, 0.35 * (1.0 - puff)))
	_hit.append({"id": str(it["id"]), "rect": rect, "priority": 3})


func _draw_warehouse(it: Dictionary) -> void:
	var v: Dictionary = it["v"]
	var pos: Vector2 = it["pos"]
	var col: Color = it["col"]
	var item: Dictionary = art.items.get("widelands.warehouse", {})
	var level := int(v.get("level", 1))
	var tint := Color(1, 1, 1, 1) if not bool(it.get("scaffold", false)) else Color(0.85, 0.85, 0.9, 0.6)
	# the dispatch yard: a city's is larger; one warehouse, always
	var yard := 170.0 if level >= 2 else 130.0
	draw_circle(pos + Vector2(0, 10), yard, Color(0.42, 0.36, 0.28, 0.75))
	draw_arc(pos + Vector2(0, 10), yard, 0, TAU, 40, col.darkened(0.2), 5.0)
	var rect := _draw_sheet(item, pos, tint, 1.25 if level >= 2 else 1.0, {"facing": "s", "class": "building"})
	if bool(it.get("scaffold", false)):
		draw_rect(rect, Color(0.9, 0.75, 0.3, 0.9), false, 5.0)
		var t := float(it.get("progress", 0.0))
		draw_arc(pos + Vector2(0, -rect.size.y - 20), 26.0, -PI * 0.5, -PI * 0.5 + TAU * t, 24, Color(1, 0.9, 0.4), 6.0)
	# flag in the faction colour
	var top := Vector2(rect.position.x + rect.size.x * 0.5, rect.position.y - 10.0)
	draw_line(top, top + Vector2(0, -70), Color(0.2, 0.15, 0.1), 5.0)
	var wave := sin(clock * 3.0 + pos.x * 0.01) * 6.0
	draw_colored_polygon(PackedVector2Array([top + Vector2(0, -70), top + Vector2(46, -58 + wave), top + Vector2(0, -44)]), col)
	if v.has("upgrade"):
		var t2 := float(v["upgrade"].get("progress", 0.0))
		draw_arc(pos + Vector2(0, -rect.size.y - 20), 26.0, -PI * 0.5, -PI * 0.5 + TAU * t2, 24, Color(0.4, 0.9, 1.0), 6.0)
	_hit.append({"id": "village:" + str(v["id"]), "rect": rect, "priority": 4})


func _draw_tree(it: Dictionary) -> void:
	var item: Dictionary = art.items.get(str(it["art"]), {})
	if item.is_empty():
		return
	var pos: Vector2 = it["pos"]
	var sh := 0.02 * sin(clock * 0.8 + float(it["phase"]))
	draw_set_transform_matrix(Transform2D(Vector2(1, 0), Vector2(sh, 1), Vector2(-sh * pos.y, 0)))
	_draw_sheet(item, pos, Color.WHITE, 1.0, {"_static": true})
	draw_set_transform_matrix(Transform2D.IDENTITY)


func _draw_worker(pos: Vector2, family: String, angle: float, loaded: bool) -> void:
	var facing := _facing_of(angle)
	var entity := {"kind": "worker", "definition": family, "anim": "walkload" if loaded else "walk", "facing": facing}
	var item: Dictionary = art._item_for(entity)
	if item.is_empty():
		draw_circle(pos, 10.0, Color(0.9, 0.8, 0.6))
		return
	_draw_sheet(item, pos, Color.WHITE, 1.0, entity)


func _facing_of(angle: float) -> String:
	var deg := fmod(rad_to_deg(angle) + 360.0, 360.0)
	var names := ["e", "se", "s", "sw", "w", "nw", "n", "ne"]
	return names[int(round(deg / 45.0)) % 8]


func _draw_unit(it: Dictionary) -> void:
	var item: Dictionary = art.items.get(str(it["art"]), {})
	var pos: Vector2 = it["pos"]
	var rect: Rect2
	if item.is_empty():
		draw_circle(pos, 12.0, it["col"])
		rect = Rect2(pos - Vector2(12, 12), Vector2(24, 24))
	elif str(item.get("game", "")) == "mindustry":
		var sc := 1.4
		var w := float(item.get("width", 48)) * sc
		rect = Rect2(pos - Vector2(w * 0.5, w * 0.7), Vector2(w, w))
		for p in item.get("parts", []):
			if str(p.get("role", "")) in ["main", "base"]:
				var tex: Texture2D = _part_tex(str(p.get("file", "")))
				if tex != null:
					draw_texture_rect(tex, rect, false)
	else:
		rect = _draw_sheet(item, pos, Color.WHITE, 1.0, {"facing": "s", "status": "idle"})
	draw_circle(pos + Vector2(0, 4), 7.0, Color(0, 0, 0, 0.6))
	draw_circle(pos + Vector2(0, 4), 4.5, it["col"])
	_hit.append({"id": str(it["id"]), "rect": rect, "priority": 2})


func _draw_journeys(vp: Rect2, detail: bool) -> void:
	for j in snapshot.get("journeys", []):
		var c := bu(float(j["x"]), float(j["y"]))
		if not vp.has_point(c):
			continue
		var col: Color = faction_colors.get(str(j["faction"]), Color.WHITE)
		var kind := str(j["type"])
		var heading := float(j.get("heading", 0.0))
		if str(j.get("phase", "")) == "return":
			pass  # legs are already reversed by the simulation; heading follows the leg
		if not detail:
			draw_circle(c, 30.0, Color(0.05, 0.05, 0.05, 0.85))
			draw_circle(c, 22.0, col)
			if kind == "expedition":
				draw_rect(Rect2(c - Vector2(8, 8), Vector2(16, 16)), Color(1, 1, 1), true)
			elif kind == "bank":
				draw_circle(c, 8.0, Color(1.0, 0.85, 0.3))
			_hit.append({"id": "journey:" + str(j["id"]), "rect": Rect2(c - Vector2(40, 40), Vector2(80, 80)), "priority": 6})
			continue
		var dir := Vector2(cos(heading), sin(heading))
		var side := Vector2(-dir.y, dir.x)
		if kind == "expedition":
			var party: Array = j.get("party", [])
			var k := 0
			for m in party:
				var off := -dir * 34.0 * k + side * (18.0 if k % 2 == 1 else -18.0) * (1 if k > 0 else 0)
				_draw_worker(c + off, str(m.get("art", "widelands.carrier")), heading, k == party.size() - 1)
				k += 1
			draw_circle(c + Vector2(0, 8), 12.0, Color(0, 0, 0, 0.5))
			draw_circle(c + Vector2(0, 8), 8.0, col)
			_hit.append({"id": "journey:" + str(j["id"]), "rect": Rect2(c - Vector2(70, 90), Vector2(140, 110)), "priority": 6})
		else:
			_draw_worker(c, "widelands.carrier", heading, true)
			# the cargo crate behind the carrier, with the goods' count
			var crate := c - dir * 30.0
			draw_rect(Rect2(crate - Vector2(16, 30), Vector2(32, 24)), Color(0.55, 0.38, 0.2), true)
			draw_rect(Rect2(crate - Vector2(16, 30), Vector2(32, 24)), Color(0.15, 0.1, 0.05), false, 2.0)
			draw_circle(c + Vector2(0, 8), 12.0, Color(0, 0, 0, 0.5))
			draw_circle(c + Vector2(0, 8), 8.0, Color(1.0, 0.85, 0.3) if kind == "bank" else col)
			_hit.append({"id": "journey:" + str(j["id"]), "rect": Rect2(c - Vector2(50, 90), Vector2(100, 110)), "priority": 6})
	# the selected thing gets a ring at every level
	if selected_id != "":
		var a := anchor_of(selected_id)
		if a != Vector2.INF:
			draw_arc(a + Vector2(0, 20), 40.0 / maxf(zoom, 0.1) * 0.5, 0, TAU, 32, Color(1, 1, 1, 0.9), 4.0 / maxf(zoom, 0.1) * 0.5)
