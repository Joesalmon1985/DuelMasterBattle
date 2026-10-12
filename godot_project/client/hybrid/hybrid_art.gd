extends RefCounted

const HexCoords = preload("res://client/hybrid/hex_coords.gd")

## Draws imported Widelands and OpenRA sprites. Missing catalogue entries are
## recorded and not replaced with rectangles.

var items: Dictionary = {}
const MOBILE := ["worker", "carrier", "animal", "unit"]
var _vis: Dictionary = {}
var _dt := 0.0
var _ts := 1.0
var _last_ms := 0
var _frames := 0
var textures: Dictionary = {}
var missing: Array[String] = []
var show_markers := false
var faction_colors: Dictionary = {}
var selected: Dictionary = {}


const IndustryView = preload("res://client/hybrid/industry_view.gd")
var industry = IndustryView.new()


func load_catalogue() -> void:
	var file := FileAccess.open("res://client/hybrid/art/catalogue.json", FileAccess.READ)
	if file == null:
		missing.append("catalogue.json")
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		missing.append("catalogue.json")
		return
	for raw in parsed.get("items", []):
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var item: Dictionary = raw
		var item_id := str(item.get("id", ""))
		items[item_id] = item
		if str(item.get("mode", "")) == "sheet":
			_remember(item_id, str(item.get("godot", "")))
		elif str(item.get("mode", "")) == "sequence":
			for path in item.get("frames_godot", []):
				_remember(str(path), str(path))


func draw_terrain(canvas: CanvasItem, origin: Vector2i, radius: int, tpx: int) -> void:
	var xf: Transform2D = canvas.get_viewport().get_canvas_transform()
	var zoom: float = xf.get_scale().x
	var inv := xf.affine_inverse()
	var vp: Vector2 = canvas.get_viewport_rect().size
	var tl: Vector2 = inv * Vector2.ZERO
	var br: Vector2 = inv * vp
	var x0 := int(floor(tl.x / tpx)) - 1
	var y0 := int(floor(tl.y / tpx)) - 1
	var x1 := int(ceil(br.x / tpx)) + 1
	var y1 := int(ceil(br.y / tpx)) + 1
	if zoom < 0.3:
		# far view: flat grass per block of tiles, so a whole continent costs a few thousand rects
		var step := 8
		for by in range(int(floor(float(y0) / step)) * step, y1, step):
			for bx in range(int(floor(float(x0) / step)) * step, x1, step):
				if HexCoords.tile_in_map(bx + step / 2, by + step / 2):
					canvas.draw_rect(Rect2(bx * tpx, by * tpx, step * tpx, step * tpx), Color(0.17, 0.34, 0.19), true)
		return
	var names: Array[String] = ["widelands.meadow1", "widelands.meadow2", "widelands.meadow3"]
	for ty in range(maxi(y0, origin.y - radius), mini(y1, origin.y + radius + 1)):
		for tx in range(maxi(x0, origin.x - radius), mini(x1, origin.x + radius + 1)):
			if not HexCoords.tile_in_map(tx, ty):
				continue
			var pick: int = absi(tx * 3 + ty * 5) % names.size()
			var tex := _tex(names[pick])
			var rect := Rect2(tx * tpx, ty * tpx, tpx, tpx)
			if tex == null:
				canvas.draw_rect(rect, Color(0.16, 0.32, 0.18), true)
			else:
				canvas.draw_texture_rect(tex, rect, false)


func draw_road(canvas: CanvasItem, tile: Array, tpx: int) -> void:
	if tile.size() < 2:
		return
	var tex := _tex("widelands.road")
	var tx := int(tile[0])
	var ty := int(tile[1])
	if tex == null:
		return
	var dest := Rect2(tx * tpx + 4, ty * tpx + 18, 56, 28)
	canvas.draw_texture_rect(tex, dest, false)


## Naval PLACEHOLDER art: OpenRA ship and naval yard sprites are not extracted on this machine (they need the Red Alert
## content packages on the Windows machine). These shapes are drawn from the entity's real state (position, facing,
## footprint, faction, hull points) and are labelled "placeholder" in docs/ASSET_INVENTORY.md.
const NAVAL_UNITS := {"openra.pt": [0.9, 0.34], "openra.ss": [1.0, 0.26], "openra.dd": [1.3, 0.4], "openra.ca": [1.6, 0.5], "openra.lst": [1.4, 0.55], "openra.msub": [1.2, 0.3]}
const NAVAL_YARDS := ["openra.syrd", "openra.spen"]
const FACING_DEG := {"e": 0.0, "se": 45.0, "s": 90.0, "sw": 135.0, "w": 180.0, "nw": 225.0, "n": 270.0, "ne": 315.0}


func _draw_naval_placeholder(canvas: CanvasItem, entity: Dictionary, tpx: int) -> bool:
	var definition := str(entity.get("definition", ""))
	var col: Color = faction_colors.get(str(entity.get("faction_name", "")), Color(0.7, 0.7, 0.7))
	if definition in NAVAL_YARDS:
		var fp: Array = entity.get("footprint", [])
		if fp.is_empty():
			return false
		var ax := int(entity.get("anchor", [0, 0])[0])
		var ay := int(entity.get("anchor", [0, 0])[1])
		var rect := Rect2((ax - 1) * tpx, (ay - 1) * tpx, tpx * 3, tpx * 3)
		var building := not entity.has("constructing")
		canvas.draw_rect(rect, Color(0.36, 0.26, 0.16, 0.95 if building else 0.45), true)
		canvas.draw_rect(rect.grow(-10), Color(0.16, 0.34, 0.6, 0.9), true)  # the open slip the ships leave from
		canvas.draw_rect(Rect2(rect.position, Vector2(rect.size.x, 14)), Color(0.5, 0.38, 0.24), true)
		canvas.draw_rect(Rect2(rect.position + Vector2(0, rect.size.y - 14), Vector2(rect.size.x, 14)), Color(0.5, 0.38, 0.24), true)
		canvas.draw_rect(rect, col, false, 5.0)
		var door := Vector2(float(entity.get("tx", ax)) + 0.5, float(entity.get("ty", ay)) + 0.5) * tpx
		canvas.draw_line(rect.get_center(), door, Color(0.5, 0.38, 0.24), 8.0)  # the jetty to the shore door
		var font := ThemeDB.fallback_font
		canvas.draw_string(font, rect.position + Vector2(10, 38), "NAVAL YARD" if definition == "openra.syrd" else "SUB PEN", HORIZONTAL_ALIGNMENT_LEFT, -1, 22, Color(1, 1, 1))
		canvas.draw_string(font, rect.position + Vector2(10, rect.size.y - 22), "placeholder art", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color(1, 1, 0.7))
		_draw_health(canvas, entity, rect.get_center())
		return true
	if NAVAL_UNITS.has(definition):
		var dims: Array = NAVAL_UNITS[definition]
		var centre := Vector2(int(entity.get("tx", 0)) * tpx + tpx * 0.5, int(entity.get("ty", 0)) * tpx + tpx * 0.5)
		if entity.has("next_tx"):
			var nxt := Vector2(int(entity["next_tx"]) * tpx + tpx * 0.5, int(entity["next_ty"]) * tpx + tpx * 0.5)
			centre = centre.lerp(nxt, float(entity.get("move_progress", 0.0)))
		var length: float = float(dims[0]) * tpx * 0.5
		var beam: float = float(dims[1]) * tpx * 0.5
		var ang := deg_to_rad(float(FACING_DEG.get(str(entity.get("facing", "e")), 0.0)))
		var xf := Transform2D(ang, centre)
		var hull := PackedVector2Array([Vector2(length, 0), Vector2(length * 0.4, beam), Vector2(-length, beam), Vector2(-length, -beam), Vector2(length * 0.4, -beam)])
		var pts := PackedVector2Array()
		for p in hull:
			pts.append(xf * p)
		var sub := definition == "openra.ss" or definition == "openra.msub"
		var hull_col := Color(0.2, 0.22, 0.26) if sub else Color(0.55, 0.58, 0.62)
		if bool(entity.get("cloaked", false)):
			hull_col.a = 0.45  # a submerged boat is drawn faint: it is hidden from the enemy
		canvas.draw_colored_polygon(pts, hull_col)
		canvas.draw_polyline(PackedVector2Array([pts[0], pts[1], pts[2], pts[3], pts[4], pts[0]]), col, 4.0)
		canvas.draw_circle(xf * Vector2(-length * 0.2, 0), beam * 0.45, col)
		_draw_marker(canvas, entity, centre)
		_draw_health(canvas, entity, centre)
		return true
	return false


func draw_entity(canvas: CanvasItem, entity: Dictionary, tpx: int) -> void:
	var definition := str(entity.get("definition", ""))
	if bool(entity.get("inside", false)):
		return
	if definition.begins_with("story."):  # the wizard's story people and places: labelled placeholders
		_draw_story(canvas, entity, tpx)
		return
	if definition.begins_with("mindustry."):  # labelled placeholders: the Mindustry art is not imported (docs/MINDUSTRY_PROVENANCE.md)
		industry.draw_entity(canvas, self, entity, tpx, faction_colors.get(str(entity.get("faction_name", "")), Color(0.7, 0.7, 0.7)))
		return
	if bool(entity.get("destroyed", false)) and _draw_ruin(canvas, entity, tpx):
		return
	if (definition in NAVAL_YARDS or NAVAL_UNITS.has(definition)) and _draw_naval_placeholder(canvas, entity, tpx):
		return
	if definition == "":
		if str(entity.get("kind", "")) == "hazard":
			var hx := int(entity.get("tx", 0))
			var hy := int(entity.get("ty", 0))
			canvas.draw_circle(Vector2(hx * tpx + tpx * 0.5, hy * tpx + tpx * 0.5), 14, Color(0.62, 0.18, 0.78))
		return
	var item: Dictionary = _item_for(entity)
	if item.is_empty():
		if definition not in missing:
			missing.append(definition)
		return
	var tex: Texture2D = _frame_texture(item, entity)
	if tex == null:
		if definition not in missing:
			missing.append(definition)
		return
	var scale := float(item.get("scale", 1))
	var hotspot: Array = item.get("hotspot", [0, 0])
	var frame_size := _frame_size(item, tex)
	var anchor := Vector2(int(entity.get("tx", 0)) * tpx + tpx * 0.5, int(entity.get("ty", 0)) * tpx + tpx * 0.5)
	var drawn := entity
	if MOBILE.has(str(entity.get("class", ""))):
		drawn = _motion(entity)
		anchor = Vector2(drawn["_vx"] * tpx + tpx * 0.5, drawn["_vy"] * tpx + tpx * 0.5)
	elif entity.has("next_tx"):
		var t := float(entity.get("move_progress", 0.0))
		var nxt := Vector2(int(entity["next_tx"]) * tpx + tpx * 0.5, int(entity["next_ty"]) * tpx + tpx * 0.5)
		anchor = anchor.lerp(nxt, t)
	if entity.has("ground_footprint") and item.has("footprint_cells"):
		_draw_footprint_building(canvas, entity, item, tex, tpx)
		return
	var top_left := anchor - Vector2(float(hotspot[0]), float(hotspot[1])) * scale
	var src := _source_rect(item, tex, drawn)
	_draw_marker(canvas, entity, anchor)
	canvas.draw_texture_rect_region(tex, Rect2(top_left, frame_size * scale), src)
	_draw_cargo(canvas, entity, anchor, float(hotspot[1]) * scale)
	_draw_health(canvas, entity, anchor)


## An OpenRA building sits on its real footprint: one source cell (24 px) per tile, top-left at the footprint's corner, so the
## picture covers exactly the tiles the simulation blocks. The war factory is its base frame plus the roll-up door overlay
## (OpenRA WithProductionDoorOverlay `build-top`): closed while idle, opening and closing while a vehicle is being built.
func _draw_footprint_building(canvas: CanvasItem, entity: Dictionary, item: Dictionary, tex: Texture2D, tpx: int) -> void:
	var min_x := 1 << 30
	var min_y := 1 << 30
	var max_x := -(1 << 30)
	var max_y := -(1 << 30)
	for p in entity["ground_footprint"]:
		min_x = mini(min_x, int(p[0]))
		min_y = mini(min_y, int(p[1]))
		max_x = maxi(max_x, int(p[0]))
		max_y = maxi(max_y, int(p[1]))
	var cells: Array = item["footprint_cells"]
	var box := Rect2(Vector2(min_x, min_y) * tpx, Vector2(int(cells[0]), int(cells[1])) * tpx)
	var scale := float(item.get("scale", 1))
	var hurt := entity.has("hp") and entity.has("max_hp") and int(entity["hp"]) * 2 < int(entity["max_hp"])
	var index := 0
	if item.has("overlay_prefix"):
		index = 1 if hurt else 0
	elif item.has("damaged_frame"):
		index = int(item["damaged_frame"]) if hurt else 0
	else:
		index = _sequence_index(item, entity)
	var base_path := "res://client/hybrid/art/openra/%s-%04d.png" % [str(item.get("prefix", "")), index]
	var base_tex: Texture2D = _tex(base_path)
	if base_tex == null:
		base_tex = tex
	var size := Vector2(base_tex.get_width(), base_tex.get_height()) * scale
	var building_pos := box.position + Vector2(0, box.size.y - size.y)
	canvas.draw_texture_rect(base_tex, Rect2(building_pos, size), false)
	if item.has("overlay_prefix"):
		var length := int(item.get("overlay_length", 1))
		var frame := 0
		var q: Array = entity.get("queue", [])
		var producing := not q.is_empty() and str(q[0].get("state", "")) == "building"
		if producing:
			var t := int(Time.get_ticks_msec() / (1000.0 / float(item.get("overlay_fps", 8)))) % (length * 3)
			frame = t if t < length else (length - 1 if t < length * 2 else length * 3 - 1 - t)
		var door := _tex("res://client/hybrid/art/openra/%s-%04d.png" % [str(item["overlay_prefix"]), clampi(frame, 0, length - 1)])
		if door != null:
			canvas.draw_texture_rect(door, Rect2(building_pos, Vector2(door.get_width(), door.get_height()) * scale), false)
	var centre := box.get_center()
	var ring := entity.duplicate()
	ring["_box"] = box
	_draw_marker(canvas, ring, centre)
	_draw_health(canvas, ring, centre)


## A building at 0 HP burns for a few seconds before the simulation removes it. Widelands buildings are replaced by the
## Widelands `destroyed_building` fire sheet; an OpenRA structure keeps its (darkened) picture with the same fire over it.
func _draw_ruin(canvas: CanvasItem, entity: Dictionary, tpx: int) -> bool:
	var fire: Dictionary = items.get("widelands.destroyed_building", {})
	var tex: Texture2D = _tex("widelands.destroyed_building")
	if fire.is_empty() or tex == null:
		return false
	var anchor := Vector2(int(entity.get("tx", 0)) * tpx + tpx * 0.5, int(entity.get("ty", 0)) * tpx + tpx * 0.5)
	var scale := float(fire.get("scale", 2))
	if str(entity.get("definition", "")).begins_with("openra."):
		var base: Dictionary = _item_for(entity)
		var btex: Texture2D = _frame_texture(base, entity) if not base.is_empty() else null
		if btex != null:
			var bhot: Array = base.get("hotspot", [0, 0])
			var bscale := float(base.get("scale", 1))
			var bsize := _frame_size(base, btex)
			canvas.draw_texture_rect_region(btex, Rect2(anchor - Vector2(float(bhot[0]), float(bhot[1])) * bscale, bsize * bscale), _source_rect(base, btex, {"_static": true}), Color(0.25, 0.22, 0.2))
			scale *= 1.5
	var phase := int(Time.get_ticks_msec() / (1000.0 / float(fire.get("fps", 10)))) % int(fire.get("frames", 10))
	var fw := tex.get_width() / int(fire.get("columns", 10))
	var hot: Array = fire.get("hotspot", [43, 60])
	var src := Rect2(phase * fw, 0, fw, tex.get_height())
	canvas.draw_texture_rect_region(tex, Rect2(anchor - Vector2(float(hot[0]), float(hot[1])) * scale, Vector2(fw, tex.get_height()) * scale), src)
	return true


## Called once per rendered frame before the entities: the time step and the game speed the motion layer needs.
func begin_frame(time_scale: float) -> void:
	var now := Time.get_ticks_msec()
	_dt = clampf(float(now - _last_ms) / 1000.0, 0.0, 0.1)
	_last_ms = now
	_ts = maxf(time_scale, 1.0)
	_frames += 1
	if _frames % 300 == 0:
		for id in _vis.keys():
			if int(_vis[id]["seen"]) < _frames - 300:
				_vis.erase(id)


## Presentation only. The simulation owns the tile; this layer glides the picture towards it at the entity's own speed
## so a snapshot arriving every few frames cannot make a worker hop. It never feeds a position back.
func _motion(entity: Dictionary) -> Dictionary:
	var id := str(entity.get("id", ""))
	var goal := Vector2(float(entity.get("tx", 0)), float(entity.get("ty", 0)))
	var heading := Vector2.ZERO
	if entity.has("next_tx"):
		var nxt := Vector2(float(entity["next_tx"]), float(entity["next_ty"]))
		heading = nxt - goal
		goal = goal.lerp(nxt, float(entity.get("move_progress", 0.0)))
	var v: Dictionary = _vis.get(id, {})
	if v.is_empty():
		v = {"pos": goal, "face": str(entity.get("facing", "e"))}
	var pos: Vector2 = v["pos"]
	var dist := pos.distance_to(goal)
	if dist > 4.0:
		pos = goal  # a teleport (spawn, deploy, a long stall): do not slide across the map
		dist = 0.0
	var speed := _ts * 1000.0 / maxf(float(entity.get("move_ms", 600)), 1.0)
	pos = pos.move_toward(goal, minf((speed * 1.2 + dist * 2.0) * _dt, 0.5))  # never more than half a tile in one frame
	var moving := pos.distance_to(goal) > 0.02 or heading != Vector2.ZERO
	var face: String = v["face"]
	var dir := heading if heading != Vector2.ZERO else goal - pos
	if moving and dir.length() > 0.02:
		face = ("e" if dir.x > 0.0 else "w") if absf(dir.x) >= absf(dir.y) else ("s" if dir.y > 0.0 else "n")
	elif not moving and str(entity.get("class", "")) == "worker":
		face = str(entity.get("facing", face))
	v["pos"] = pos
	v["face"] = face
	v["seen"] = _frames
	_vis[id] = v
	var out := entity.duplicate()
	out["_vx"] = pos.x
	out["_vy"] = pos.y
	out["_moving"] = moving
	var cls := str(entity.get("class", ""))
	if cls != "unit":
		out["facing"] = face
	var anim := str(entity.get("anim", ""))
	# a figure that is not walking stands still: no walking frames on the spot (idle carriers, workers waiting at a door)
	out["_static"] = not moving and (cls != "worker" or anim in ["", "idle", "walk", "walkload"])
	return out


func _draw_cargo(canvas: CanvasItem, entity: Dictionary, anchor: Vector2, head: float) -> void:
	var good := str(entity.get("cargo", entity.get("carrying", "")))
	if good == "":
		return
	var icon: Dictionary = items.get("widelands.ware.%s" % good, {})
	var tex: Texture2D = _tex(str(icon.get("id", ""))) if not icon.is_empty() else null
	if tex == null:
		return
	var sc := float(icon.get("scale", 2)) * 1.4
	var size := Vector2(tex.get_width(), tex.get_height()) * sc
	var centre := Vector2(anchor.x, anchor.y - head * 0.9 - size.y * 0.4)
	canvas.draw_circle(centre, maxf(size.x, size.y) * 0.62, Color(0.05, 0.05, 0.05, 0.55))
	canvas.draw_texture_rect(tex, Rect2(centre - size * 0.5, size), false)


func draw_effects(canvas: CanvasItem, effects: Array, tpx: int) -> void:
	for e in effects:
		if typeof(e) != TYPE_DICTIONARY:
			continue
		var a := Vector2(float(e.get("x1", 0)) + 0.5, float(e.get("y1", 0)) + 0.5) * tpx + Vector2(0, -14)
		var b := Vector2(float(e.get("x2", 0)) + 0.5, float(e.get("y2", 0)) + 0.5) * tpx + Vector2(0, -14)
		var ttl := float(e.get("ttl_ms", 0))
		if str(e.get("t", "")) == "explosion":
			var f := clampf(1.0 - ttl / 2500.0, 0.0, 1.0) if ttl > 800.0 else clampf(1.0 - ttl / 800.0, 0.0, 1.0)
			canvas.draw_circle(b, 14.0 + 30.0 * f, Color(1.0, 0.55, 0.1, 0.65 * (1.0 - f)))
			canvas.draw_circle(b, 8.0 + 14.0 * f, Color(1.0, 0.9, 0.4, 0.8 * (1.0 - f)))
		else:
			var t := clampf(1.0 - ttl / 400.0, 0.0, 1.0)
			var head := a.lerp(b, minf(t * 3.0, 1.0))
			var tail := a.lerp(b, maxf(t * 3.0 - 0.35, 0.0))
			var heavy := str(e.get("p", "")) in ["Bullet", "Missile"]
			canvas.draw_line(tail, head, Color(1.0, 0.85, 0.3, 0.95), 5.0 if heavy else 3.0)
			if t >= 1.0:
				canvas.draw_circle(b, 6.0, Color(1.0, 0.7, 0.2, 0.6))


func _draw_marker(canvas: CanvasItem, entity: Dictionary, anchor: Vector2) -> void:
	var kind := str(entity.get("class", ""))
	var radius := 0.0
	if kind == "unit":
		radius = 22.0
	elif kind == "worker" or kind == "carrier":
		radius = 14.0
	elif entity.has("hp"):
		radius = 46.0
		if entity.has("_box"):
			radius = maxf((entity["_box"] as Rect2).size.x, (entity["_box"] as Rect2).size.y) * 0.5
	if radius == 0.0:
		return
	var col: Color = faction_colors.get(str(entity.get("faction_name", "")), Color(0.7, 0.7, 0.7))
	var zoom: float = canvas.get_viewport().get_canvas_transform().get_scale().x
	if zoom < 0.2 and (kind == "worker" or kind == "carrier"):
		return
	if zoom < 0.2:
		# strategic icon: a solid dot in the faction colour, about 6 screen px
		var dot := 6.0 / maxf(zoom, 0.02)
		canvas.draw_circle(anchor, dot * (1.4 if entity.has("hp") and kind != "unit" else 1.0), col)
		return
	var width := 3.0 if show_markers else 2.0
	canvas.draw_arc(anchor + Vector2(0, 8), radius, 0.0, TAU, 28, Color(col.r, col.g, col.b, 0.9), width)
	if selected.has(str(entity.get("id", ""))):
		canvas.draw_arc(anchor + Vector2(0, 8), radius + 6.0, 0.0, TAU, 28, Color(1, 1, 1), 4.0)


func _draw_health(canvas: CanvasItem, entity: Dictionary, anchor: Vector2) -> void:
	if not entity.has("hp") or not entity.has("max_hp"):
		return
	var hp := int(entity.get("hp", 0))
	var max_hp := int(entity.get("max_hp", 0))
	if max_hp <= 0 or hp >= max_hp:
		return
	var width := 36.0
	var bar := Rect2(anchor.x - width * 0.5, anchor.y - 28.0, width, 4.0)
	if entity.has("_box"):
		var box: Rect2 = entity["_box"]
		width = box.size.x * 0.6
		bar = Rect2(box.get_center().x - width * 0.5, box.position.y - 10.0, width, 5.0)
	canvas.draw_rect(bar, Color(0.1, 0.1, 0.1, 0.8), true)
	var fill := width * float(hp) / float(max_hp)
	canvas.draw_rect(Rect2(bar.position, Vector2(fill, 4.0)), Color(0.75, 0.15, 0.12), true)


func _item_for(entity: Dictionary) -> Dictionary:
	var definition := str(entity.get("definition", ""))
	var kind := str(entity.get("kind", ""))
	if kind == "tree":
		# the stage sprite always wins: the bare definition is only the mature picture and would show every stage as a full tree
		var stage := str(entity.get("stage", "old"))
		var tkey := "widelands.fallentree" if stage == "felled" else "%s.%s" % [definition, stage]
		if items.has(tkey):
			return items[tkey]
		return items.get(definition, {})
	if str(entity.get("class", "")) == "animal":
		var akey := "%s.idle" % definition
		if str(entity.get("status", "")) == "moving":
			akey = "%s.walk.%s" % [definition, _sheet_facing(str(entity.get("facing", "e")))]
		return items.get(akey, items.get("%s.idle" % definition, {}))
	if kind == "worker":
		var anim := str(entity.get("anim", "idle"))
		var key := "%s.%s" % [definition, anim]
		if anim == "walk" or anim == "walkload":
			key += ".%s" % _sheet_facing(str(entity.get("facing", "e")))
		var found: Dictionary = items.get(key, items.get("%s.idle" % definition, {}))
		if found.is_empty():
			# some imported roles have no still idle sheet: stand on the first walking frame facing the same way instead
			found = items.get("%s.walk.%s" % [definition, _sheet_facing(str(entity.get("facing", "e")))], items.get("%s.walk.e" % definition, {}))
		return found
	if definition == "widelands.carrier":
		var facing := _sheet_facing(str(entity.get("facing", "e")))
		var key := "widelands.carrier" if facing == "e" else "widelands.carrier.%s" % facing
		if items.has(key):
			return items[key]
	if items.has(definition):
		return items[definition]
	return {}


func _frame_texture(item: Dictionary, entity: Dictionary) -> Texture2D:
	if str(item.get("mode", "")) == "sequence":
		var index := _sequence_index(item, entity)
		var path := "res://client/hybrid/art/openra/%s-%04d.png" % [str(item.get("prefix", "")), index]
		return _tex(path)
	return _tex(str(item.get("id", "")))


func _sequence_index(item: Dictionary, entity: Dictionary) -> int:
	var facing := _eight(str(entity.get("facing", "s")))
	var moving := str(entity.get("status", "")) == "moving"
	if item.has("run_start") and moving:
		var length := int(item.get("run_length", 1))
		var tick := 0
		if int(item.get("fps", 0)) > 0 and length > 1:
			tick = int(Time.get_ticks_msec() / (1000.0 / float(item.get("fps", 1)))) % length
		return int(item.get("run_start", 0)) + facing * length + tick
	if int(item.get("facing_count", 0)) == 32:
		return facing * 4
	if int(item.get("facings", 1)) <= 1:
		var length := maxi(int(item.get("length", 1)), 1)
		var tick := 0
		if int(item.get("fps", 0)) > 0 and length > 1:
			tick = int(Time.get_ticks_msec() / (1000.0 / float(item.get("fps", 1)))) % length
		return tick
	return facing


func _source_rect(item: Dictionary, tex: Texture2D, entity: Dictionary) -> Rect2:
	if str(item.get("mode", "")) == "sequence":
		return Rect2(0, 0, tex.get_width(), tex.get_height())
	var columns := maxi(int(item.get("columns", 1)), 1)
	var rows := maxi(int(item.get("rows", 1)), 1)
	var frame_w := tex.get_width() / columns
	var frame_h := tex.get_height() / rows
	var frames := maxi(int(item.get("frames", 1)), 1)
	var frame := 0
	if int(item.get("fps", 0)) > 0 and frames > 1 and not bool(entity.get("_static", false)):
		frame = int(Time.get_ticks_msec() / (1000.0 / float(item.get("fps", 1)))) % frames
	var col := frame % columns
	var row := frame / columns
	if row >= rows:
		row = 0
	return Rect2(col * frame_w, row * frame_h, frame_w, frame_h)


func _frame_size(item: Dictionary, tex: Texture2D) -> Vector2:
	if str(item.get("mode", "")) == "sequence":
		return Vector2(tex.get_width(), tex.get_height())
	var columns := maxi(int(item.get("columns", 1)), 1)
	var rows := maxi(int(item.get("rows", 1)), 1)
	return Vector2(tex.get_width() / float(columns), tex.get_height() / float(rows))


func _remember(key: String, path: String) -> void:
	if path == "":
		return
	var image := Image.new()
	var err := image.load(path)
	if err != OK:
		if key not in missing:
			missing.append(key)
		return
	textures[key] = ImageTexture.create_from_image(image)


func _tex(key: String) -> Texture2D:
	return textures.get(key) as Texture2D


func _sheet_facing(facing: String) -> String:
	if facing == "n":
		return "ne"
	if facing == "s":
		return "se"
	return facing


func _eight(facing: String) -> int:
	match facing:
		"n":
			return 0
		"ne":
			return 1
		"e":
			return 2
		"se":
			return 3
		"s":
			return 4
		"sw":
			return 5
		"w":
			return 6
		"nw":
			return 7
		_:
			return 4


## Outline of every hex region that holds an outbreak cube (the overlay is logical: it changes no movement or placement).
func draw_regions(canvas: CanvasItem, snapshot: Dictionary, tpx: int) -> void:
	var reg: Dictionary = snapshot.get("regions", {})
	var cubes: Dictionary = reg.get("cubes", {})
	if cubes.is_empty():
		return
	var size := float(reg.get("size", 56))
	var map: Dictionary = snapshot.get("map", {})
	var w := float(map.get("w", 544))
	var h := float(map.get("h", 288))
	for rid in cubes:
		var parts := str(rid).split(":")[1].split(",")
		var q := float(parts[0])
		var r := float(parts[1])
		var cx := w * 0.5 + 1.5 * size * q
		var cy := h * 0.5 + sqrt(3.0) * size * (r + q * 0.5)
		var pts := PackedVector2Array()
		for k in 7:
			var a := deg_to_rad(60.0 * float(k))
			pts.append(Vector2(cx + size * cos(a), cy + size * sin(a)) * tpx)
		var n := int(cubes[rid])
		canvas.draw_polyline(pts, Color(0.75, 0.2 + 0.1 * n, 0.9, 0.55), 6.0)


func _draw_story(canvas: CanvasItem, e: Dictionary, tpx: int) -> void:
	var c := Vector2(int(e["tx"]) * tpx + tpx * 0.5, int(e["ty"]) * tpx + tpx * 0.5)
	var font := ThemeDB.fallback_font
	if str(e.get("kind", "")) == "outbreak_clue":
		var t := Time.get_ticks_msec() / 1000.0
		var col := {"sickness": Color(0.55, 0.45, 0.25), "blight": Color(0.6, 0.6, 0.6), "toxic_spill": Color(0.4, 0.9, 0.3), "signal_fault": Color(0.4, 0.8, 1.0)}.get(str(e.get("hazard", "")), Color(0.7, 0.3, 0.8))
		for k in 4:
			var rise := fmod(t * 0.6 + float(k) * 0.25, 1.0)
			canvas.draw_circle(c + Vector2(sin(t * 2.0 + k) * 8.0, -rise * 70.0), 10.0 + rise * 14.0, Color(col.r, col.g, col.b, 0.5 * (1.0 - rise)))
		canvas.draw_rect(Rect2(c + Vector2(-16, -6), Vector2(32, 12)), Color(0.15, 0.1, 0.05, 0.8), true)
		canvas.draw_string(font, c + Vector2(-44, 24), str(e.get("label", "outbreak")) + " (placeholder)", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(1, 0.95, 0.7))
		return
	if str(e.get("kind", "")) == "npc":
		var col := Color(0.95, 0.65, 0.2)
		canvas.draw_circle(c + Vector2(0, -18), 11, Color(0.95, 0.8, 0.65))
		canvas.draw_rect(Rect2(c + Vector2(-13, -8), Vector2(26, 32)), col, true)
		canvas.draw_rect(Rect2(c + Vector2(-13, -8), Vector2(26, 32)), Color(0.25, 0.15, 0.05), false, 3.0)
		canvas.draw_string(font, c + Vector2(-34, 44), "MINER (placeholder)", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(1, 1, 0.8))
		if bool(e.get("has_quest", false)):
			canvas.draw_circle(c + Vector2(0, -44), 12, Color(1, 0.9, 0.2))
			canvas.draw_string(font, c + Vector2(-4, -38), "!", HORIZONTAL_ALIGNMENT_LEFT, -1, 20, Color(0.3, 0.1, 0.0))
	else:
		var open := bool(e.get("solved", false))
		canvas.draw_rect(Rect2(c + Vector2(-26, -26), Vector2(52, 52)), Color(0.12, 0.1, 0.1), true)
		canvas.draw_rect(Rect2(c + Vector2(-16, -10), Vector2(32, 36)), Color(0.02, 0.02, 0.03), true)
		canvas.draw_arc(c + Vector2(0, -10), 16, PI, TAU, 16, Color(0.7, 0.6, 0.4), 4.0)
		canvas.draw_string(font, c + Vector2(-40, 46), "GALLERY (placeholder)", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.9, 0.85, 0.7) if not open else Color(0.6, 1, 0.7))
