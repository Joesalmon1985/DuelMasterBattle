extends Node2D
class_name GodView

## The one continuous world of God World, drawn from the authoritative snapshot (docs/GOD_WORLD_PRD.md sections 4, 7, 8, 11). Positions arrive
## in board units (hex circumradius 1) and are multiplied by HEX_PX; nothing here decides anything: the simulation owns every number, this
## node owns the picture. Levels of detail by camera zoom (7.3): close and village (buildings, workers, parties), region (markers, roads,
## journeys), whole board (hexes, tokens, dots). The same entity ids are used at every level, so a tap resolves to the same thing.

const HybridArt = preload("res://client/hybrid/hybrid_art.gd")
const AssetLoader = preload("res://client/scripts/asset_loader.gd")
const TerrainView = preload("res://client/hybrid/terrain_view.gd")

const TILE_PX := 64.0  # one Widelands map tile; positions arrive in tiles (the terrain embedding, docs/PLAN_GOD_WORLD_LIVING.md)
const HEX_PX := TILE_PX  # kept as the unit multiplier name used throughout: a board unit is one tile now
const ZOOM_DETAIL := 0.28  # buildings and people from here in
const ZOOM_REGION := 0.12  # markers, roads and journeys between here and detail; below: the whole board
const ROLE_COLOR := {
	"WOOD": Color(0.22, 0.46, 0.2), "BRICK": Color(0.62, 0.38, 0.22), "SHEEP": Color(0.55, 0.72, 0.32), "WHEAT": Color(0.82, 0.7, 0.3),
	"ORE": Color(0.48, 0.5, 0.56), "DESERT": Color(0.86, 0.78, 0.55),
}
const SCALE_BY_GAME := {"widelands": 2.0, "openra": 2.0, "mindustry": 1.6}  # a Mindustry cell (32 px) is 0.8 tile: a 3x3 block spans 2.4 tiles, the planner's spacing
const MIND_PAD := Color(0.17, 0.17, 0.2)

var board: Dictionary = {}
var snapshot: Dictionary = {}
var art = HybridArt.new()
var terrain = null  # TerrainView once the board arrives with its map
var unit := 13.0  # tiles per board unit (edge length)
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
	unit = float(b.get("unit", 13.0))
	_scenery.clear()
	if b.has("terrain"):
		terrain = TerrainView.new()
		if not terrain.load_from({"terrain": b["terrain"]}):
			terrain = null
	# the trees are the embedding's: planted in the woodland regions on arable ground, clear of plots and corridors (the simulation knows them too)
	var rng := RandomNumberGenerator.new()
	rng.seed = int(b.get("cosmetic_seed", 1))
	var idx := 0
	for t in b.get("trees", []):
		var hid := str(t["hex"])
		if not _scenery.has(hid):
			_scenery[hid] = []
		_scenery[hid].append({"x": float(t["x"]), "y": float(t["y"]), "art": "widelands.%s.old" % str(t.get("species", "beech")), "phase": rng.randf() * TAU, "key": str(idx)})
		idx += 1
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


## Is a world point inside a region's catchment polygon (the embedded corners)?
func _in_region(h: Dictionary, p: Vector2) -> bool:
	var pts := PackedVector2Array()
	for k in h["corners"]:
		pts.append(bu(float(k[0]), float(k[1])))
	return Geometry2D.is_point_in_polygon(p, pts)


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
	# empty ground inside a region's catchment selects the region
	for h in board.get("hexes", []):
		if _in_region(h, world_pos):
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
	if terrain != null:
		terrain.draw(self, int(TILE_PX))
		_draw_overlay(vp_rect)
	else:
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
	return Rect2(a, b - a).abs().grow(TILE_PX * 8.0)


## The logical board as an inspection overlay over the natural terrain: catchment outlines, the token and odds at each region's work site, the
## plot rings. Off by default; the terrain itself is the picture.
func _draw_overlay(vp: Rect2) -> void:
	var far := zoom < ZOOM_REGION
	for h in board.get("hexes", []):
		var c := bu(float(h["x"]), float(h["y"]))
		if not vp.grow(TILE_PX * unit).has_point(c):
			continue
		var token := int(h.get("token", 0))
		var role := str(h["role"])
		if show_overlay:
			var pts := PackedVector2Array()
			for k in h["corners"]:
				pts.append(bu(float(k[0]), float(k[1])))
			var col: Color = ROLE_COLOR.get(role, Color.GRAY)
			draw_colored_polygon(pts, Color(col.r, col.g, col.b, 0.22))
			var border := pts.duplicate()
			border.append(pts[0])
			draw_polyline(border, Color(col.r, col.g, col.b, 0.9), 5.0 if far else 3.0)
		if token > 0 and (show_overlay or far or zoom < ZOOM_DETAIL * 1.3):
			# the number token sits at the region's work site: where the woodcutters, quarrymen or miners go
			var ws := bu(float(h.get("work_site", [h["x"], h["y"]])[0]), float(h.get("work_site", [h["x"], h["y"]])[1]))
			var rad := 70.0 if far else (44.0 if zoom < ZOOM_DETAIL else 30.0)
			var hot := token == 6 or token == 8
			draw_circle(ws, rad, Color(0.96, 0.93, 0.82, 0.92))
			draw_arc(ws, rad, 0, TAU, 32, Color(0.2, 0.15, 0.1, 0.8), 3.0)
			var fs := int(rad * 1.1)
			var s := str(token)
			var w := _font.get_string_size(s, HORIZONTAL_ALIGNMENT_CENTER, -1, fs).x
			draw_string(_font, ws + Vector2(-w * 0.5, fs * 0.36), s, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color(0.75, 0.1, 0.1) if hot else Color(0.12, 0.1, 0.08))
			var pips := int(h.get("pips", 0))
			for i in pips:
				draw_circle(ws + Vector2((i - (pips - 1) * 0.5) * rad * 0.26, rad * 0.68), rad * 0.07, Color(0.75, 0.1, 0.1) if hot else Color(0.12, 0.1, 0.08))
		if show_overlay and not far:
			var nm: String = str(snapshot.get("role_names", {}).get(role, role)).capitalize()
			if role == "DESERT":
				nm = "Desert"
			var fs2 := 34
			var w2 := _font.get_string_size(nm, HORIZONTAL_ALIGNMENT_CENTER, -1, fs2).x
			draw_string(_font, c + Vector2(-w2 * 0.5, 0), nm, HORIZONTAL_ALIGNMENT_LEFT, -1, fs2, Color(0.1, 0.08, 0.05, 0.85))
	if show_overlay:
		for nid in board.get("nodes", {}):
			var p: Array = board["nodes"][nid]
			draw_arc(bu(float(p[0]), float(p[1])), TILE_PX * 6.0, 0, TAU, 40, Color(1, 1, 1, 0.35), 2.0)
		for e in board.get("edges", {}):
			var ab: Array = board["edges"][e]
			var pa: Array = board["nodes"][ab[0]]
			var pb: Array = board["nodes"][ab[1]]
			draw_line(bu(float(pa[0]), float(pa[1])), bu(float(pb[0]), float(pb[1])), Color(1, 1, 1, 0.25), 2.0)


## A road follows its corridor over the terrain: a winding polyline between the same two logical endpoints. A road under construction grows
## from the end that joins the faction's network, with its crew at the front.
func _corridor_points(eid: String, from_node: String) -> PackedVector2Array:
	var pts := PackedVector2Array()
	var poly: Array = board.get("corridors", {}).get(eid, [])
	for p in poly:
		pts.append(bu(float(p[0]), float(p[1])))
	var ends: Array = board.get("edges", {}).get(eid, [])
	if ends.size() == 2 and from_node != "" and str(ends[1]) == from_node:
		pts.reverse()
	return pts


static func _poly_len(pts: PackedVector2Array) -> float:
	var L := 0.0
	for i in range(pts.size() - 1):
		L += pts[i].distance_to(pts[i + 1])
	return L


## The point and heading a fraction `t` along a polyline.
static func _poly_at(pts: PackedVector2Array, t: float) -> Array:
	var total := _poly_len(pts)
	var want := clampf(t, 0.0, 1.0) * total
	var run := 0.0
	for i in range(pts.size() - 1):
		var seg := pts[i].distance_to(pts[i + 1])
		if run + seg >= want or i == pts.size() - 2:
			var f := 0.0 if seg <= 0.0 else clampf((want - run) / seg, 0.0, 1.0)
			return [pts[i].lerp(pts[i + 1], f), (pts[i + 1] - pts[i]).angle()]
		run += seg
	return [pts[0] if pts.size() > 0 else Vector2.ZERO, 0.0]


static func _poly_prefix(pts: PackedVector2Array, t: float) -> PackedVector2Array:
	var out := PackedVector2Array()
	if pts.size() == 0:
		return out
	var total := _poly_len(pts)
	var want := clampf(t, 0.0, 1.0) * total
	var run := 0.0
	out.append(pts[0])
	for i in range(pts.size() - 1):
		var seg := pts[i].distance_to(pts[i + 1])
		if run + seg >= want:
			var f := 0.0 if seg <= 0.0 else (want - run) / seg
			out.append(pts[i].lerp(pts[i + 1], f))
			return out
		out.append(pts[i + 1])
		run += seg
	return out


func _draw_roads(vp: Rect2) -> void:
	for r in snapshot.get("roads", []):
		var a := bu(float(r["a"][0]), float(r["a"][1]))
		var b := bu(float(r["b"][0]), float(r["b"][1]))
		var big := vp.grow(TILE_PX * unit)
		if not big.has_point(a) and not big.has_point(b):
			continue
		var col: Color = faction_colors.get(str(r["faction"]), Color.WHITE)
		var status := str(r["status"])
		var width := 22.0 if zoom >= ZOOM_REGION else 40.0
		var pts := _corridor_points(str(r["id"]), str(r.get("from_node", "")))
		if pts.size() < 2:
			pts = PackedVector2Array([a, b])
		if status == "historical":
			draw_polyline(pts, Color(0.35, 0.32, 0.28, 0.55), width * 0.5)
		elif status == "building":
			var t := float(r.get("progress", 0.0))
			draw_polyline(pts, Color(0.3, 0.28, 0.24, 0.5), width * 0.6)
			var done := _poly_prefix(pts, t)
			if done.size() >= 2:
				draw_polyline(done, Color(0.25, 0.2, 0.15), width + 8.0)
				draw_polyline(done, col, width)
			var front: Array = _poly_at(pts, t)
			if zoom >= ZOOM_DETAIL:
				_draw_worker(front[0], "widelands.barbarians_carrier_worker", float(front[1]), true)
				_hit.append({"id": "road:" + str(r["id"]), "rect": Rect2((front[0] as Vector2) - Vector2(40, 80), Vector2(80, 90)), "priority": 3})
		else:
			draw_polyline(pts, Color(0.22, 0.18, 0.14), width + 8.0)
			draw_polyline(pts, col.lerp(Color(0.6, 0.5, 0.4), 0.45), width)
		if status != "historical":
			var mid: Array = _poly_at(pts, 0.5)
			var d := Vector2(cos(float(mid[1])), sin(float(mid[1]))) * TILE_PX * 2.5
			var n := Vector2(-d.y, d.x).normalized() * width
			_hit.append({"id": "road:" + str(r["id"]), "rect": Rect2((mid[0] as Vector2) - d - n, (d + n) * 2.0).abs(), "priority": 1})


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


func _draw_hexes(vp: Rect2) -> void:
	# the bare regular layout (no map attached): role-coloured polygons, kept only for a world without an embedding
	for h in board.get("hexes", []):
		var pts := PackedVector2Array()
		for k in h["corners"]:
			pts.append(bu(float(k[0]), float(k[1])))
		draw_colored_polygon(pts, ROLE_COLOR.get(str(h["role"]), Color.GRAY))
	_draw_overlay(vp)


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
	var claimed: Dictionary = {}  # board trees a village works are drawn from its own picture (felled, regrowing)
	for v in snapshot.get("villages", []):
		var ops: Variant = v.get("ops")
		if ops == null or typeof(ops) != TYPE_DICTIONARY:
			continue
		for t in ops.get("trees", []):
			claimed[str(t["key"])] = true
	var k := 0
	for hid in _scenery:
		var pts: Array = _scenery[hid]
		for p in pts:
			var key := str(p.get("key", ""))
			if not claimed.has(key):
				var c := bu(float(p["x"]), float(p["y"]))
				if vp.has_point(c):
					items.append({"y": c.y, "kind": "tree", "pos": c, "art": str(p["art"]), "phase": float(p["phase"])})
			k += 1
	for v in snapshot.get("villages", []):
		var c := bu(float(v["x"]), float(v["y"]))
		if not vp.grow(TILE_PX * unit).has_point(c):
			continue
		var status := str(v["status"])
		if status == "pending":
			continue
		if status == "historical":
			items.append({"y": c.y, "kind": "remains", "v": v, "pos": c})
			continue
		var col: Color = faction_colors.get(str(v["faction"]), Color.WHITE)
		var ops: Variant = v.get("ops")
		if ops == null or typeof(ops) != TYPE_DICTIONARY or bool(ops.get("lean", false)):
			# no living picture (a village still being founded, or out of the window): the hub alone
			items.append({"y": c.y + 1.0, "kind": "warehouse", "v": v, "pos": c, "col": col, "scaffold": status != "operational", "progress": float(v.get("construction", {}).get("progress", 1.0)) if v.has("construction") else 1.0})
			continue
		# streets: the village's own paths from each workshop to its one hub (none in the age of belts)
		if str(ops.get("transport", "carrier")) != "belt":
			for st in ops.get("streets", []):
				items.append({"y": -1e9, "kind": "street", "a": bu(float(st[0]), float(st[1])), "b": bu(float(st[2]), float(st[3]))})
		for seg in ops.get("segments", []):
			items.append({"y": -1e8, "kind": "segment", "seg": seg, "col": col})
		for t in ops.get("trees", []):
			var tp := bu(float(t["x"]), float(t["y"]))
			if vp.has_point(tp):
				var stage := str(t.get("stage", "old"))
				var art_id := "widelands.%s.%s" % [str(t.get("species", "beech")), "old" if stage == "old" else ("sapling" if stage == "sapling" else "old")]
				if stage == "stump":
					art_id = "widelands.fallentree"
				items.append({"y": tp.y, "kind": "tree", "pos": tp, "art": art_id, "phase": float(hash(str(t["key"])) % 628) / 100.0, "still": stage != "old"})
		for s_ in ops.get("sites", []):
			var sp := bu(float(s_["x"]), float(s_["y"]))
			var kind := str(s_["kind"])
			if kind == "hub":
				items.append({"y": sp.y + 1.0, "kind": "hub", "v": v, "site": s_, "pos": sp, "col": col, "scaffold": str(s_["state"]) == "building"})
			elif kind == "military":
				items.append({"y": sp.y, "kind": "building", "art": str(s_["art"]), "pos": sp, "id": "facility:" + str(v["id"]), "col": col, "scaffold": str(s_["state"]) == "building", "working": false, "role": "MIL", "v": v})
			else:
				items.append({"y": sp.y, "kind": "building", "art": str(s_["art"]), "pos": sp, "id": "site:" + str(s_["id"]), "col": col, "scaffold": str(s_["state"]) == "building",
					"working": str(s_["state"]) == "working", "state": str(s_["state"]), "role": str(s_["role"]), "v": v, "out": s_.get("out", {}), "progress": float(s_.get("progress", 0.0)),
					"site_kind": kind, "water": int(s_.get("water", 0)), "fuel": int(s_.get("fuel", 0)), "unpowered": not bool(ops.get("power", true)) and kind in ["processor", "factory"]})
		for a in ops.get("agents", []):
			if str(a.get("anim", "")) == "inside":
				continue
			var ap := bu(float(a["x"]), float(a["y"]))
			items.append({"y": ap.y, "kind": "agent", "a": a, "pos": ap, "col": col})
		var mil: Variant = v.get("military")
		if mil != null and typeof(mil) == TYPE_DICTIONARY:
			var slots: Array = mil.get("slots", [])
			for u in v.get("units", []):
				var slot := int(u["slot"])
				if slot < slots.size():
					var up := bu(float(slots[slot][0]), float(slots[slot][1]))
					items.append({"y": up.y, "kind": "unit", "art": str(u["art"]), "pos": up, "id": "unit:" + str(u["id"]), "col": col})
	items.sort_custom(func(a, b): return a["y"] < b["y"])
	for it in items:
		match str(it["kind"]):
			"street": draw_line(it["a"], it["b"], Color(0.42, 0.36, 0.26, 0.55), 9.0)
			"segment": _draw_segment(it)
			"tree": _draw_tree(it)
			"warehouse": _draw_warehouse(it)
			"hub": _draw_hub(it)
			"building": _draw_building(it)
			"agent": _draw_agent(it)
			"unit": _draw_unit(it)
			"remains": _draw_remains(it["v"], it["pos"])
	_draw_journeys(vp, true)


## A conveyor or a conduit: the sprite laid tile by tile along its line, turned to each leg's direction; packets ride the belt as small crates
## coloured by their good, a pipe tints with its fill. A broken segment is drawn dark and carries nothing (the simulation moves nothing on it).
const GOOD_COLOR := {"coal": Color(0.12, 0.12, 0.14), "sand": Color(0.93, 0.85, 0.6), "lead": Color(0.55, 0.5, 0.7), "copper": Color(0.85, 0.5, 0.3), "titanium": Color(0.6, 0.7, 0.95),
	"silicon": Color(0.55, 0.85, 0.9), "pyratite": Color(0.95, 0.6, 0.2), "thorium": Color(0.75, 0.35, 0.75), "spore_pod": Color(0.5, 0.3, 0.6), "phase_fabric": Color(0.95, 0.85, 1.0),
	"blast_compound": Color(0.95, 0.3, 0.3), "surge_alloy": Color(0.95, 0.9, 0.45), "water": Color(0.35, 0.6, 1.0)}


func _draw_segment(it: Dictionary) -> void:
	var seg: Dictionary = it["seg"]
	var pts := PackedVector2Array()
	for p in seg.get("pts", []):
		pts.append(bu(float(p[0]), float(p[1])))
	if pts.size() < 2:
		return
	var pipe := str(seg.get("kind", "belt")) == "pipe"
	var broken := bool(seg.get("broken", false))
	var tex: Texture2D = _part_tex("res://client/hybrid/art/mindustry/%s" % ("conduit__top.png" if pipe else "conveyor__main.png"))
	var tile := TILE_PX * 0.9
	var tint := Color(0.4, 0.4, 0.4) if broken else (Color(0.55, 0.75, 1.0).lerp(Color(0.2, 0.45, 1.0), float(seg.get("fill", 0.0))) if pipe else Color.WHITE)
	for i in range(pts.size() - 1):
		var a := pts[i]
		var b := pts[i + 1]
		var d := b - a
		var n := maxi(1, int(ceil(d.length() / tile)))
		var ang := d.angle()
		for k in n:
			var c := a + d * ((k + 0.5) / float(n))
			if tex != null:
				draw_set_transform(c, ang, Vector2.ONE)
				draw_texture_rect(tex, Rect2(Vector2(-tile * 0.5, -tile * 0.5), Vector2(tile, tile)), false, tint)
				draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
			else:
				draw_line(a, b, Color(0.3, 0.3, 0.32) if not pipe else Color(0.3, 0.5, 0.8), 14.0)
	if pipe:
		return
	var total := _poly_len(pts)
	for item in seg.get("items", []):
		var at: Array = _poly_at(pts, float(item.get("t", 0.0)))
		var c2: Vector2 = at[0]
		var col: Color = GOOD_COLOR.get(str(item.get("good", "")), Color(0.8, 0.8, 0.8))
		draw_rect(Rect2(c2 - Vector2(9, 9), Vector2(18, 18)), col, true)
		draw_rect(Rect2(c2 - Vector2(9, 9), Vector2(18, 18)), Color(0.05, 0.05, 0.05, 0.9), false, 1.5)
	if total > 0.0 and not broken:
		pass


## The village's one hub, in the age's dress: the primitive store (a timber hut with its stockpiles), the warehouse and its yard, the command
## centre on its pad, the core. Never two of them.
func _draw_hub(it: Dictionary) -> void:
	var v: Dictionary = it["v"]
	var site: Dictionary = it["site"]
	var pos: Vector2 = it["pos"]
	var col: Color = it["col"]
	var item: Dictionary = art.items.get(str(site["art"]), {})
	var level := int(v.get("level", 1))
	var props := str(site.get("props", ""))
	var tint := Color(1, 1, 1, 1) if not bool(it.get("scaffold", false)) else Color(0.85, 0.85, 0.9, 0.6)
	if props == "yard":
		var yard := 170.0 if level >= 2 else 130.0
		draw_circle(pos + Vector2(0, 10), yard, Color(0.42, 0.36, 0.28, 0.75))
		draw_arc(pos + Vector2(0, 10), yard, 0, TAU, 40, col.darkened(0.2), 5.0)
	elif props == "primitive":
		draw_circle(pos + Vector2(0, 14), 110.0, Color(0.45, 0.38, 0.26, 0.6))
		# stockpiles: logs and baskets beside the store
		for i in 3:
			var lp := pos + Vector2(-96 + i * 14, 44 + i * 6)
			draw_rect(Rect2(lp, Vector2(56, 10)), Color(0.45, 0.3, 0.16), true)
			draw_rect(Rect2(lp, Vector2(56, 10)), Color(0.2, 0.12, 0.06), false, 1.5)
		for i in 3:
			var bp := pos + Vector2(70 + i * 22, 36 + (i % 2) * 14)
			draw_circle(bp, 10.0, Color(0.72, 0.58, 0.32))
			draw_arc(bp, 10.0, 0, TAU, 12, Color(0.35, 0.25, 0.1), 2.0)
	elif props == "industrial":
		var pad := Rect2(pos - Vector2(170, 150), Vector2(340, 240))
		draw_rect(pad, Color(0.32, 0.31, 0.3, 0.85), true)
		draw_rect(pad, Color(0.12, 0.12, 0.12), false, 3.0)
	elif props == "core":
		var pad2 := Rect2(pos - Vector2(150, 130), Vector2(300, 220))
		draw_rect(pad2, Color(0.2, 0.21, 0.24, 0.9), true)
		draw_rect(pad2, Color(0.5, 0.55, 0.6), false, 3.0)
	var rect: Rect2
	if item.is_empty():
		rect = Rect2(pos - Vector2(60, 90), Vector2(120, 90))
		draw_rect(rect, Color(0.5, 0.3, 0.6, 0.7), true)
	elif str(item.get("game", "")) == "mindustry":
		rect = _draw_mindustry(item, pos, tint, false)
	elif str(item.get("game", "")) == "openra" and item.has("states"):
		var st_files: Array = item["states"].get("idle", {}).get("files", [])
		var tex: Texture2D = _part_tex(str(st_files[0])) if st_files.size() > 0 else null
		var sc := 2.6667
		if tex != null:
			var size := Vector2(tex.get_width(), tex.get_height()) * sc
			rect = Rect2(pos - Vector2(size.x * 0.5, size.y * 0.8), size)
			draw_texture_rect(tex, rect, false, tint)
		else:
			rect = Rect2(pos - Vector2(90, 90), Vector2(180, 120))
			draw_rect(rect, Color(0.4, 0.4, 0.45), true)
	else:
		rect = _draw_sheet(item, pos, tint, 1.25 if level >= 2 else 1.0, {"facing": "s", "class": "building"})
	if bool(it.get("scaffold", false)):
		draw_rect(rect, Color(0.9, 0.75, 0.3, 0.9), false, 5.0)
	var top := Vector2(rect.position.x + rect.size.x * 0.5, rect.position.y - 10.0)
	draw_line(top, top + Vector2(0, -70), Color(0.2, 0.15, 0.1), 5.0)
	var wave := sin(clock * 3.0 + pos.x * 0.01) * 6.0
	draw_colored_polygon(PackedVector2Array([top + Vector2(0, -70), top + Vector2(46, -58 + wave), top + Vector2(0, -44)]), col)
	if v.has("upgrade"):
		var t2 := float(v["upgrade"].get("progress", 0.0))
		draw_arc(pos + Vector2(0, -rect.size.y - 20), 26.0, -PI * 0.5, -PI * 0.5 + TAU * t2, 24, Color(0.4, 0.9, 1.0), 6.0)
	_hit.append({"id": "village:" + str(v["id"]), "rect": rect, "priority": 4})


## A worker, carrier or truck of the living village: facing comes from its actual motion (the simulation's heading), the sheet from its job
## (walk, walkload, the work animation of its program), cargo drawn as the ware's icon over the shoulder.
func _draw_agent(it: Dictionary) -> void:
	var a: Dictionary = it["a"]
	var pos: Vector2 = it["pos"]
	var family := str(a.get("art", ""))
	var anim := str(a.get("anim", "idle"))
	var heading := float(a.get("heading", 0.0))
	var facing := _facing_of(heading)
	var kind := str(a.get("kind", "worker"))
	var rect: Rect2
	if kind == "truck":
		var item: Dictionary = art.items.get(family, {})
		if item.is_empty():
			draw_circle(pos, 14.0, it["col"])
			rect = Rect2(pos - Vector2(14, 14), Vector2(28, 28))
		else:
			rect = _draw_sheet(item, pos, Color.WHITE, 1.0, {"facing": facing, "status": "moving" if anim != "idle" else "idle"})
	else:
		var entity := {"kind": "worker", "definition": family, "anim": anim, "facing": facing}
		if anim != "walk" and anim != "walkload" and anim != "idle":
			var wkey := "%s.%s" % [family, anim]
			if not art.items.has(wkey):
				entity["anim"] = "idle"
		var item2: Dictionary = art._item_for(entity)
		if item2.is_empty():
			draw_circle(pos, 10.0, Color(0.9, 0.8, 0.6))
			rect = Rect2(pos - Vector2(10, 10), Vector2(20, 20))
		else:
			rect = _draw_sheet(item2, pos, Color.WHITE, 1.0, entity)
	var cargo := str(a.get("cargo", ""))
	if cargo != "":
		var icon := "widelands.ware.%s" % cargo
		var ic: Dictionary = art.items.get(icon, {})
		var tex: Texture2D = art._tex(icon) if not ic.is_empty() else null
		var at := Vector2(rect.position.x + rect.size.x * 0.5 + 10, rect.position.y - 4)
		if tex != null:
			draw_texture_rect(tex, Rect2(at - Vector2(14, 14), Vector2(28, 28)), false)
		else:
			draw_rect(Rect2(at - Vector2(10, 8), Vector2(20, 16)), Color(0.55, 0.38, 0.2), true)
			draw_rect(Rect2(at - Vector2(10, 8), Vector2(20, 16)), Color(0.15, 0.1, 0.05), false, 1.5)
	draw_circle(pos + Vector2(0, 4), 5.0, Color(0, 0, 0, 0.45))
	draw_circle(pos + Vector2(0, 4), 3.0, it["col"])
	_hit.append({"id": "agent:" + str(a["id"]), "rect": rect.grow(8.0), "priority": 2})


func _near_station(p: Dictionary) -> bool:
	for v in snapshot.get("villages", []):
		if str(v["status"]) in ["pending", "historical"]:
			continue
		if abs(float(v["x"]) - float(p["x"])) > unit * 1.3 or abs(float(v["y"]) - float(p["y"])) > unit * 1.3:
			continue
		for d in v.get("districts", []):
			for s in d.get("stations", []):
				if abs(float(s["x"]) - float(p["x"])) < unit * 0.2 and abs(float(s["y"]) - float(p["y"])) < unit * 0.2:
					return true
		var mil: Variant = v.get("military")
		if mil != null and typeof(mil) == TYPE_DICTIONARY and abs(float(mil["x"]) - float(p["x"])) < unit * 0.25 and abs(float(mil["y"]) - float(p["y"])) < unit * 0.25:
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
	draw_rect(rect.grow(4.0), MIND_PAD * tint, true)  # a thin footing under the top-view machine, no yard of its own
	draw_rect(rect.grow(4.0), Color(0.05, 0.05, 0.06), false, 2.0)
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
	var state := str(it.get("state", ""))
	if bool(it.get("unpowered", false)):
		state = "unpowered"
	if state == "short" or state == "unpowered":
		draw_circle(Vector2(rect.position.x + rect.size.x - 10.0, rect.position.y + 10.0), 6.0, Color(0.95, 0.2, 0.2))
	var skind := str(it.get("site_kind", ""))
	if skind == "tank" or (skind == "producer" and int(it.get("water", -1)) >= 0 and str(it.get("art", "")).contains("cultivator")):
		var lvl := clampf(float(it.get("water", 0)) / 12.0, 0.0, 1.0)
		draw_rect(Rect2(rect.position.x + 6.0, rect.position.y + rect.size.y - 10.0, (rect.size.x - 12.0) * lvl, 5.0), Color(0.35, 0.6, 1.0), true)
	if skind == "generator" and int(it.get("fuel", 0)) > 0:
		draw_circle(Vector2(rect.position.x + 10.0, rect.position.y + 10.0), 5.0, Color(1.0, 0.6, 0.15))
	elif state == "no_work":
		draw_circle(Vector2(rect.position.x + rect.size.x - 10.0, rect.position.y + 10.0), 6.0, Color(0.95, 0.75, 0.2))
	var outs: Dictionary = it.get("out", {})
	var n_out := 0
	for g in outs:
		n_out += int(outs[g])
	for i in mini(n_out, 4):
		var cp := pos + Vector2(28 + i * 14, 2)
		draw_rect(Rect2(cp - Vector2(6, 6), Vector2(12, 10)), Color(0.55, 0.38, 0.2), true)
		draw_rect(Rect2(cp - Vector2(6, 6), Vector2(12, 10)), Color(0.15, 0.1, 0.05), false, 1.0)
	var prog := float(it.get("progress", 0.0))
	if prog > 0.0 and prog < 1.0 and state == "working":
		draw_arc(Vector2(rect.position.x + 12.0, rect.position.y + 12.0), 8.0, -PI * 0.5, -PI * 0.5 + TAU * prog, 16, Color(1, 0.95, 0.6), 3.0)
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
	var sh := 0.0 if bool(it.get("still", false)) else 0.02 * sin(clock * 0.8 + float(it["phase"]))
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
			_draw_worker(c, "widelands.barbarians_carrier_worker", heading, true)
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
