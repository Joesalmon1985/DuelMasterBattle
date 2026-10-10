extends RefCounted

const HexCoords = preload("res://client/hybrid/hex_coords.gd")

## Draws imported Widelands and OpenRA sprites. Missing catalogue entries are
## recorded and not replaced with rectangles.

var items: Dictionary = {}
var textures: Dictionary = {}
var missing: Array[String] = []
var show_markers := false
var faction_colors: Dictionary = {}
var selected: Dictionary = {}


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


func draw_entity(canvas: CanvasItem, entity: Dictionary, tpx: int) -> void:
	var definition := str(entity.get("definition", ""))
	if bool(entity.get("inside", false)):
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
	var tx := int(entity.get("tx", 0))
	var ty := int(entity.get("ty", 0))
	var anchor := Vector2(tx * tpx + tpx * 0.5, ty * tpx + tpx * 0.5)
	if entity.has("next_tx"):
		var t := float(entity.get("move_progress", 0.0))
		var nxt := Vector2(int(entity["next_tx"]) * tpx + tpx * 0.5, int(entity["next_ty"]) * tpx + tpx * 0.5)
		anchor = anchor.lerp(nxt, t)
	var top_left := anchor - Vector2(float(hotspot[0]), float(hotspot[1])) * scale
	var src := _source_rect(item, tex, entity)
	_draw_marker(canvas, entity, anchor)
	canvas.draw_texture_rect_region(tex, Rect2(top_left, frame_size * scale), src)
	_draw_health(canvas, entity, anchor)


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
	canvas.draw_rect(bar, Color(0.1, 0.1, 0.1, 0.8), true)
	var fill := width * float(hp) / float(max_hp)
	canvas.draw_rect(Rect2(bar.position, Vector2(fill, 4.0)), Color(0.75, 0.15, 0.12), true)


func _item_for(entity: Dictionary) -> Dictionary:
	var definition := str(entity.get("definition", ""))
	var kind := str(entity.get("kind", ""))
	if kind == "tree":
		var stage := str(entity.get("stage", "old"))
		var tkey := "widelands.fallentree" if stage == "felled" else "%s.%s" % [definition, stage]
		return items.get(tkey, {})
	if kind == "worker":
		var anim := str(entity.get("anim", "idle"))
		var key := "%s.%s" % [definition, anim]
		if anim == "walk" or anim == "walkload":
			key += ".%s" % _sheet_facing(str(entity.get("facing", "e")))
		return items.get(key, items.get("%s.idle" % definition, {}))
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
	if int(item.get("fps", 0)) > 0 and frames > 1:
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
