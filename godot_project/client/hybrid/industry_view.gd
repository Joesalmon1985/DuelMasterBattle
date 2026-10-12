extends RefCounted
class_name HybridIndustryView

## Presentation of the Mindustry-style industry layer (belts, machines, power links, Mindustry units). Everything here is drawn from
## the simulation snapshot: no rules live in Godot. Machines, belts and units use the imported Mindustry v146 sprites
## (scripts/import_mindustry_art.py, GPL-3.0); a block without imported art falls back to a shape labelled "placeholder art".

const ROLE_COLOR := {
	"drill": Color(0.78, 0.55, 0.22), "crafter": Color(0.72, 0.3, 0.28), "generator": Color(0.95, 0.85, 0.25), "battery": Color(0.3, 0.7, 0.75),
	"node": Color(0.4, 0.8, 1.0), "unit_factory": Color(0.45, 0.4, 0.75), "belt": Color(0.5, 0.5, 0.55),
}
const WARE_COLOR := {
	"coal": Color(0.1, 0.1, 0.12), "mdy.sand": Color(0.95, 0.82, 0.55), "mdy.lead": Color(0.55, 0.45, 0.75), "mdy.copper": Color(0.85, 0.5, 0.3),
	"mdy.silicon": Color(0.55, 0.85, 0.9), "mdy.titanium": Color(0.6, 0.7, 0.95), "mdy.graphite": Color(0.65, 0.7, 0.75), "mdy.metaglass": Color(0.9, 0.95, 1.0),
}
const SHORT := {
	"mdy:mechanical_drill": "DRILL", "mdy:pneumatic_drill": "DRILL 2", "mdy:silicon_smelter": "SMELTER", "mdy:graphite_press": "PRESS",
	"mdy:solar_panel": "SOLAR", "mdy:solar_panel_large": "SOLAR", "mdy:combustion_generator": "BURNER", "mdy:battery": "BATT",
	"mdy:power_node": "NODE", "mdy:ground_factory": "FACTORY", "mdy:conveyor": "BELT",
}
const DIRS := [Vector2(1, 0), Vector2(0, 1), Vector2(-1, 0), Vector2(0, -1)]

var clock := 0.0  ## seconds of real time, for the moving chevrons and pulses (presentation only)
var _cache: Dictionary = {}


func _sprite(art, key: String) -> Texture2D:
	if _cache.has(key):
		return _cache[key]
	var item: Dictionary = art.items.get(key, {}) if art != null else {}
	var tex: Texture2D = null
	if not item.is_empty() and ResourceLoader.exists(str(item.get("godot", ""))):
		tex = load(str(item["godot"]))
	_cache[key] = tex
	return tex


func begin_frame(delta: float) -> void:
	clock += delta


func ware_color(ware: String) -> Color:
	return WARE_COLOR.get(ware, Color(1, 0, 1))


var art_ref = null  ## set by hybrid_art so belts can find the imported conveyor sprite


func draw_belts(canvas: CanvasItem, industry: Dictionary, tpx: int, vx0: int, vy0: int, vx1: int, vy1: int) -> void:
	var belt_tex: Texture2D = _sprite(art_ref, "mindustry.block.conveyor")
	for belt in industry.get("belts", []):
		var x := int(belt[0])
		var y := int(belt[1])
		if x < vx0 or x > vx1 or y < vy0 or y > vy1:
			continue
		var d: Vector2 = DIRS[int(belt[2])]
		var origin := Vector2(x, y) * tpx
		var centre := origin + Vector2(tpx, tpx) * 0.5
		var blocked := int(belt[4]) == 1
		if belt_tex != null:  # the Mindustry conveyor, turned to the run's direction (the sprite runs east)
			canvas.draw_set_transform(centre, d.angle(), Vector2.ONE)
			canvas.draw_texture_rect(belt_tex, Rect2(Vector2(-tpx, -tpx) * 0.5, Vector2(tpx, tpx)), false, Color(1, 0.55, 0.55) if blocked else Color.WHITE)
			canvas.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
		else:
			canvas.draw_rect(Rect2(origin + Vector2(6, 6), Vector2(tpx - 12, tpx - 12)), Color(0.18, 0.18, 0.2) if not blocked else Color(0.35, 0.12, 0.12), true)
		var side := Vector2(-d.y, d.x)
		# chevrons slide along the run (moving only while the tile is not blocked)
		var phase := fmod(clock * 1.8, 1.0) if not blocked else 0.0
		for k in 2:
			var c := centre + d * (float(k) * 0.5 + phase * 0.5 - 0.5) * tpx * 0.9
			var pts := PackedVector2Array([c + d * 8.0, c - d * 6.0 + side * 8.0, c - d * 6.0 - side * 8.0])
			canvas.draw_polyline(PackedVector2Array([pts[1], pts[0], pts[2]]), Color(0.75, 0.75, 0.8, 0.55), 2.0)
		for it in belt[3]:
			var pos := float(it[1]) / 1000.0
			var p := origin + Vector2(tpx, tpx) * 0.5 + d * (pos - 0.5) * tpx
			canvas.draw_rect(Rect2(p - Vector2(8, 8), Vector2(16, 16)), ware_color(str(it[0])), true)
			canvas.draw_rect(Rect2(p - Vector2(8, 8), Vector2(16, 16)), Color(0, 0, 0, 0.8), false, 1.5)


func draw_links(canvas: CanvasItem, snapshot: Dictionary, tpx: int) -> void:
	var industry: Dictionary = snapshot.get("industry", {})
	var links: Dictionary = industry.get("links", {})
	if links.is_empty():
		return
	var centres := {}
	for e in snapshot.get("entities", []):
		if str(e.get("definition", "")).begins_with("mindustry.") and e.has("ground_footprint"):
			centres[str(e["id"])] = _footprint_centre(e, tpx)
	for node in links:
		for target in links[node]:
			if centres.has(node) and centres.has(target):
				canvas.draw_line(centres[node], centres[target], Color(0.5, 0.9, 1.0, 0.85), 3.0)


func _footprint_centre(e: Dictionary, tpx: int) -> Vector2:
	var fp: Array = e.get("ground_footprint", [])
	if fp.is_empty():
		return (Vector2(int(e["tx"]), int(e["ty"])) + Vector2(0.5, 0.5)) * tpx
	var lo := Vector2(1 << 30, 1 << 30)
	var hi := Vector2(-(1 << 30), -(1 << 30))
	for p in fp:
		lo.x = min(lo.x, float(p[0]))
		lo.y = min(lo.y, float(p[1]))
		hi.x = max(hi.x, float(p[0]))
		hi.y = max(hi.y, float(p[1]))
	return (lo + hi + Vector2(1, 1)) * 0.5 * tpx


func draw_entity(canvas: CanvasItem, art, e: Dictionary, tpx: int, faction_color: Color) -> void:
	var definition := str(e.get("definition", ""))
	if str(e.get("class", "")) == "unit":
		_draw_unit(canvas, art, e, tpx, faction_color)
		return
	if str(e.get("kind", "")) == "mdy:conveyor":
		_draw_belt_site(canvas, e, tpx, faction_color)
		return
	var fp: Array = e.get("ground_footprint", [])
	var lo := Vector2(float(e["tx"]), float(e["ty"]))
	var hi := lo
	for p in fp:
		lo.x = min(lo.x, float(p[0]))
		lo.y = min(lo.y, float(p[1]))
		hi.x = max(hi.x, float(p[0]))
		hi.y = max(hi.y, float(p[1]))
	var rect := Rect2(lo * tpx + Vector2(4, 4), (hi - lo + Vector2(1, 1)) * tpx - Vector2(8, 8))
	var m: Dictionary = e.get("mdy", {})
	var role := str(m.get("role", _role_from_kind(str(e.get("kind", "")))))
	var base: Color = ROLE_COLOR.get(role, Color(0.6, 0.6, 0.6))
	var building := e.has("constructing")
	var working := str(m.get("state", "")) in ["drilling", "working", "building", "producing", "burning"]
	var blocked := str(m.get("state", "")) in ["output blocked", "no power", "no deposit", "deposit used up", "exit blocked"]
	var col := base
	if building:
		col = Color(base.r, base.g, base.b, 0.4)
	elif blocked:
		col = base.darkened(0.45)
	elif working:
		col = base.lightened(0.18 + 0.12 * sin(clock * 6.0))
	var centre := rect.get_center()
	var tex: Texture2D = _sprite(art, "mindustry.block." + str(e.get("kind", "")).trim_prefix("mdy:"))
	if tex != null:
		var tint := Color(1, 1, 1, 0.45) if building else (Color(0.55, 0.5, 0.5) if blocked else Color.WHITE)
		canvas.draw_texture_rect(tex, rect.grow(4.0), false, tint)
		canvas.draw_rect(rect.grow(4.0), faction_color, false, 3.0)
		if working and role == "drill":
			_spoke(canvas, centre, min(rect.size.x, rect.size.y) * 0.18, clock * 4.0)
		if not building and m.has("pct") and role in ["crafter", "unit_factory"]:
			canvas.draw_rect(Rect2(rect.position + Vector2(6, rect.size.y - 14), Vector2((rect.size.x - 12) * float(m["pct"]) / 100.0, 8)), Color(0.5, 1, 0.5), true)
		if (blocked or str(m.get("state", "")).begins_with("closed")) and not building:
			canvas.draw_string(ThemeDB.fallback_font, rect.position + Vector2(6, rect.size.y - 18), str(m.get("state", "")).to_upper(), HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(1, 0.6, 0.55))
		art._draw_health(canvas, e, centre)
		return
	canvas.draw_rect(rect, col, true)
	canvas.draw_rect(rect, faction_color, false, 4.0)
	match role:
		"drill":
			canvas.draw_circle(centre, min(rect.size.x, rect.size.y) * 0.28, Color(0.15, 0.1, 0.05))
			_spoke(canvas, centre, min(rect.size.x, rect.size.y) * 0.26, clock * (4.0 if working else 0.0))
		"crafter":
			canvas.draw_rect(Rect2(centre - rect.size * 0.22, rect.size * 0.44), Color(1, 0.55, 0.2) if working else Color(0.25, 0.1, 0.1), true)
		"generator":
			canvas.draw_colored_polygon(PackedVector2Array([centre + Vector2(0, -rect.size.y * 0.3), centre + Vector2(rect.size.x * 0.3, 0), centre + Vector2(0, rect.size.y * 0.3), centre + Vector2(-rect.size.x * 0.3, 0)]), Color(1, 1, 0.5) if working else Color(0.5, 0.45, 0.2))
		"node":
			canvas.draw_circle(centre, rect.size.x * 0.3, Color(0.7, 0.95, 1.0))
		"battery":
			canvas.draw_rect(Rect2(centre - Vector2(rect.size.x * 0.25, rect.size.y * 0.3), Vector2(rect.size.x * 0.5, rect.size.y * 0.6)), Color(0.1, 0.25, 0.28), true)
			canvas.draw_rect(Rect2(centre + Vector2(-rect.size.x * 0.22, rect.size.y * 0.27 - rect.size.y * 0.5 * float(m.get("pct", 0)) / 100.0), Vector2(rect.size.x * 0.44, rect.size.y * 0.5 * float(m.get("pct", 0)) / 100.0)), Color(0.4, 1, 0.9), true)
		"unit_factory":
			canvas.draw_rect(Rect2(centre - rect.size * 0.3, rect.size * 0.6), Color(0.2, 0.18, 0.35), true)
			canvas.draw_colored_polygon(PackedVector2Array([centre + Vector2(0, -rect.size.y * 0.22), centre + Vector2(rect.size.x * 0.2, rect.size.y * 0.16), centre + Vector2(-rect.size.x * 0.2, rect.size.y * 0.16)]), Color(1, 1, 1, 0.9 if working else 0.35))
	if not building and m.has("pct") and role in ["crafter", "unit_factory"]:
		canvas.draw_rect(Rect2(rect.position + Vector2(6, rect.size.y - 14), Vector2((rect.size.x - 12) * float(m["pct"]) / 100.0, 8)), Color(0.5, 1, 0.5), true)
	var font := ThemeDB.fallback_font
	canvas.draw_string(font, rect.position + Vector2(6, 22), str(SHORT.get(str(e.get("kind", "")), "MACHINE")), HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color(1, 1, 1))
	canvas.draw_string(font, rect.position + Vector2(6, 38), "placeholder art", HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(1, 1, 0.7))
	if blocked and not building:
		canvas.draw_string(font, rect.position + Vector2(6, rect.size.y - 18), str(m.get("state", "")).to_upper(), HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(1, 0.6, 0.55))
	art._draw_health(canvas, e, centre)


func _spoke(canvas: CanvasItem, c: Vector2, r: float, a: float) -> void:
	for k in 4:
		var ang := a + float(k) * TAU / 4.0
		canvas.draw_line(c, c + Vector2(cos(ang), sin(ang)) * r, Color(0.95, 0.8, 0.5), 3.0)


func _role_from_kind(kind: String) -> String:
	if kind.contains("drill"):
		return "drill"
	if kind.contains("smelter") or kind.contains("press"):
		return "crafter"
	if kind.contains("solar") or kind.contains("combustion"):
		return "generator"
	if kind.contains("battery"):
		return "battery"
	if kind.contains("node"):
		return "node"
	if kind.contains("factory"):
		return "unit_factory"
	return "belt"


func _draw_belt_site(canvas: CanvasItem, e: Dictionary, tpx: int, faction_color: Color) -> void:
	if bool(e.get("line_live", false)):
		return  # the live belt is drawn tile by tile from the industry layer
	var p := (Vector2(int(e["tx"]), int(e["ty"])) + Vector2(0.5, 0.5)) * tpx
	canvas.draw_rect(Rect2(p - Vector2(18, 18), Vector2(36, 36)), Color(0.55, 0.45, 0.25, 0.7), true)
	canvas.draw_rect(Rect2(p - Vector2(18, 18), Vector2(36, 36)), faction_color, false, 3.0)
	canvas.draw_string(ThemeDB.fallback_font, p + Vector2(-16, 6), "BELT x%d" % int(e.get("line_tiles", 0)), HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(1, 1, 1))


func _draw_unit(canvas: CanvasItem, art, e: Dictionary, tpx: int, faction_color: Color) -> void:
	var drawn: Dictionary = art._motion(e)
	var c := Vector2(drawn["_vx"] * tpx + tpx * 0.5, drawn["_vy"] * tpx + tpx * 0.5)
	var ang := deg_to_rad(float(art.FACING_DEG.get(str(e.get("facing", "e")), 0.0)))
	var utex: Texture2D = _sprite(art, "mindustry.unit." + str(e.get("definition", "")).trim_prefix("mindustry."))
	if utex != null:  # Mindustry unit sprites face up: turn them to the unit's heading
		var size := Vector2(utex.get_width(), utex.get_height()) * (tpx / 40.0)
		canvas.draw_set_transform(c, ang + PI * 0.5, Vector2.ONE)
		canvas.draw_texture_rect(utex, Rect2(-size * 0.5, size), false)
		canvas.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
		canvas.draw_arc(c, size.x * 0.55, 0.0, TAU, 20, faction_color, 3.0)
		art._draw_marker(canvas, e, c)
		art._draw_health(canvas, e, c)
		return
	var xf := Transform2D(ang, c)
	var pts := PackedVector2Array([xf * Vector2(22, 0), xf * Vector2(-16, 16), xf * Vector2(-16, -16)])
	canvas.draw_colored_polygon(pts, Color(0.88, 0.9, 0.95))
	canvas.draw_polyline(PackedVector2Array([pts[0], pts[1], pts[2], pts[0]]), faction_color, 4.0)
	canvas.draw_circle(c, 6.0, faction_color)
	canvas.draw_string(ThemeDB.fallback_font, c + Vector2(-20, 34), "DAGGER*", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(1, 1, 0.7))
	art._draw_marker(canvas, e, c)
	art._draw_health(canvas, e, c)
