extends RefCounted

const HexCoords = preload("res://client/hybrid/hex_coords.gd")

## Draws imported Widelands and OpenRA sprites. Missing catalogue entries are
## recorded and not replaced with rectangles.

var items: Dictionary = {}
var textures: Dictionary = {}
var missing: Array[String] = []


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
	var names: Array[String] = ["widelands.meadow1", "widelands.meadow2", "widelands.meadow3"]
	for ty in range(origin.y - radius, origin.y + radius + 1):
		for tx in range(origin.x - radius, origin.x + radius + 1):
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
	var top_left := anchor - Vector2(float(hotspot[0]), float(hotspot[1])) * scale
	var src := _source_rect(item, tex, entity)
	canvas.draw_texture_rect_region(tex, Rect2(top_left, frame_size * scale), src)
	_draw_health(canvas, entity, anchor)


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
