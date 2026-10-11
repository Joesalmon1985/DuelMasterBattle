extends RefCounted

## The terrain exactly as the Python simulation sent it (op "terrain"). Nothing here is
## invented: tiles are drawn from the received layers with Widelands textures, far zoom
## uses a one-pixel-per-node overview, and deposits come from the live "resources" op.

const OVERVIEW := {
	"arable": Color(0.34, 0.63, 0.27), "mineable": Color(0.47, 0.43, 0.39), "walkable": Color(0.87, 0.80, 0.55),
	"water": Color(0.16, 0.35, 0.67), "unwalkable": Color(0.27, 0.35, 0.23), "unreachable": Color(0.94, 0.96, 0.98),
}
const RES_COLORS := [Color(0, 0, 0, 0), Color(0.08, 0.08, 0.08), Color(0.85, 0.38, 0.22), Color(0.98, 0.82, 0.16), Color(0.82, 0.82, 0.88), Color(0.55, 0.9, 1.0)]

var w := 0
var h := 0
var palette: Array = []
var palette_class: Array = []
var terrain := PackedByteArray()
var height := PackedByteArray()
var cls := PackedByteArray()
var build := PackedByteArray()
var static_hash := ""
var starts: Array = []
var textures: Array = []  # palette index -> Texture2D
var overview: ImageTexture
var show_resources := false
var show_build := false  # where the simulation allows which building size
var res_nodes: Array = []
var loaded := false
var water_frames: Array = []  # Widelands water animation, 14 frames per second
var _edge: Array = []  # four soft-edge gradients: east, west, south, north
var _avg: Array = []  # average colour of each palette terrain, used to blend neighbours into each other
var _res_stamp := -1.0


func load_from(reply: Dictionary) -> bool:
	var t: Variant = reply.get("terrain", null)
	if typeof(t) != TYPE_DICTIONARY:
		return false
	w = int(t["w"])
	h = int(t["h"])
	palette = t["palette"]
	palette_class = t["palette_class"]
	static_hash = str(t["static_hash"])
	starts = t.get("starts", [])
	terrain = _decode(str(t["terrain"]), w * h)
	height = _decode(str(t["height"]), w * h)
	cls = _decode(str(t["cls"]), w * h)
	build = _decode(str(t["build"]), w * h)
	textures.clear()
	for name in palette:
		var path := "res://client/hybrid/art/terrain/%s.png" % str(name)
		var tex: Texture2D = load(path) if ResourceLoader.exists(path) else null
		textures.append(tex)
	_build_overview()
	_load_water()
	_build_edges()
	loaded = true
	return true


func _load_water() -> void:
	water_frames.clear()
	for name in palette:
		if str(palette_class[palette.find(name)]) != "water":
			continue
		var i := 0
		while true:
			var path := "res://client/hybrid/art/terrain/water/%s_%02d.png" % [str(name), i]
			if not ResourceLoader.exists(path):
				break
			water_frames.append(load(path))
			i += 1
		break


func _build_edges() -> void:
	# soft alpha ramps for blending a tile's edge into the terrain next to it (Widelands dithers terrain borders)
	_edge.clear()
	var n := 24
	for dir in 4:
		var img := Image.create(n, n, false, Image.FORMAT_RGBA8)
		for y in n:
			for x in n:
				var t := 0.0
				match dir:
					0: t = float(x) / float(n - 1)
					1: t = 1.0 - float(x) / float(n - 1)
					2: t = float(y) / float(n - 1)
					3: t = 1.0 - float(y) / float(n - 1)
				var a := pow(t, 2.2) * 0.85
				img.set_pixel(x, y, Color(1, 1, 1, a))
		_edge.append(ImageTexture.create_from_image(img))
	_avg.clear()
	for i in palette.size():
		var tex: Texture2D = textures[i]
		var c := Color(0.5, 0.5, 0.5)
		if tex != null:
			var im := tex.get_image()
			if im != null:
				im.resize(1, 1, Image.INTERPOLATE_LANCZOS)
				c = im.get_pixel(0, 0)
				c.a = 1.0
		_avg.append(c)


func _decode(b64: String, size: int) -> PackedByteArray:
	var raw := Marshalls.base64_to_raw(b64)
	return raw.decompress(size, FileAccess.COMPRESSION_DEFLATE)


func _build_overview() -> void:
	var data := PackedByteArray()
	data.resize(w * h * 3)
	var table: Array = []
	for i in palette.size():
		table.append(OVERVIEW.get(str(palette_class[i]), Color.MAGENTA))
	for i in w * h:
		var c: Color = table[terrain[i]]
		var shade := 1.0
		if str(palette_class[terrain[i]]) != "water":
			shade = 0.85 + float(height[i]) / 255.0 * 0.5
		data[i * 3] = int(clampf(c.r * shade, 0.0, 1.0) * 255.0)
		data[i * 3 + 1] = int(clampf(c.g * shade, 0.0, 1.0) * 255.0)
		data[i * 3 + 2] = int(clampf(c.b * shade, 0.0, 1.0) * 255.0)
	overview = ImageTexture.create_from_image(Image.create_from_data(w, h, false, Image.FORMAT_RGB8, data))


func in_bounds(x: int, y: int) -> bool:
	return x >= 0 and y >= 0 and x < w and y < h


func class_name_at(x: int, y: int) -> String:
	if not in_bounds(x, y):
		return ""
	return str(palette_class[terrain[y * w + x]])


func ground(x: int, y: int) -> bool:
	var c := class_name_at(x, y)
	return c == "arable" or c == "mineable" or c == "walkable"


func terrain_name_at(x: int, y: int) -> String:
	if not in_bounds(x, y):
		return ""
	return str(palette[terrain[y * w + x]])


func draw(canvas: CanvasItem, tpx: int) -> void:
	var xf: Transform2D = canvas.get_viewport().get_canvas_transform()
	var zoom: float = xf.get_scale().x
	var inv := xf.affine_inverse()
	var vp: Vector2 = canvas.get_viewport_rect().size
	var tl: Vector2 = inv * Vector2.ZERO
	var br: Vector2 = inv * vp
	var x0 := maxi(int(floor(tl.x / tpx)) - 1, 0)
	var y0 := maxi(int(floor(tl.y / tpx)) - 1, 0)
	var x1 := mini(int(ceil(br.x / tpx)) + 1, w - 1)
	var y1 := mini(int(ceil(br.y / tpx)) + 1, h - 1)
	canvas.draw_rect(Rect2(tl, br - tl), Color(0.05, 0.12, 0.25), true)
	if zoom < 0.3:
		canvas.draw_texture_rect(overview, Rect2(0, 0, w * tpx, h * tpx), false)
		return
	var wf := int(Time.get_ticks_msec() * 0.014) % maxi(water_frames.size(), 1)
	for ty in range(y0, y1 + 1):
		var row := ty * w
		for tx in range(x0, x1 + 1):
			var idx: int = terrain[row + tx]
			var tex: Texture2D = textures[idx]
			if water_frames.size() > 0 and str(palette_class[idx]) == "water":
				tex = water_frames[wf]
			var rect := Rect2(tx * tpx, ty * tpx, tpx, tpx)
			if tex == null:
				canvas.draw_rect(rect, Color.MAGENTA, true)
			else:
				canvas.draw_texture_rect(tex, rect, false)
	if zoom >= 0.45:
		_draw_edges(canvas, x0, y0, x1, y1, tpx)
	if show_build:
		var sz := float(tpx) * 0.5
		for ty2 in range(y0, y1 + 1):
			for tx2 in range(x0, x1 + 1):
				var cap: int = build[ty2 * w + tx2]
				var base := cap & 7
				if base == 0:
					continue
				var col := Color(0.2, 0.9, 0.3, 0.5)  # big
				if base == 2:
					col = Color(0.6, 0.95, 0.35, 0.5)  # medium
				elif base == 1:
					col = Color(1.0, 0.9, 0.2, 0.5)  # small
				elif base == 4:
					col = Color(1.0, 0.55, 0.1, 0.55)  # mine
				var rc := Rect2(tx2 * tpx + sz * 0.5, ty2 * tpx + sz * 0.5, sz, sz)
				canvas.draw_rect(rc, col, true)
				if (cap & 8) != 0:
					canvas.draw_rect(rc.grow(4), Color(0.2, 0.5, 1.0, 0.9), false, 3.0)
	if show_resources:
		for n in res_nodes:
			var kind := int(n[2])
			var c: Color = RES_COLORS[kind]
			var centre := Vector2(int(n[0]) * tpx + tpx * 0.5, int(n[1]) * tpx + tpx * 0.5)
			var r := 4.0 + minf(float(n[3]), 30.0) * 0.25
			if kind == 5:
				r *= 0.6
			canvas.draw_circle(centre, r, c)
			canvas.draw_arc(centre, r, 0.0, TAU, 12, Color(1, 1, 1, 0.55), 1.5)


func _draw_edges(canvas: CanvasItem, x0: int, y0: int, x1: int, y1: int, tpx: int) -> void:
	var band := float(tpx) * 0.375
	for ty in range(y0, y1 + 1):
		var row := ty * w
		for tx in range(x0, x1 + 1):
			var idx: int = terrain[row + tx]
			# east, west, south, north neighbours: where the terrain differs, the neighbour's colour fades in along the shared edge
			if tx + 1 < w and terrain[row + tx + 1] != idx:
				var c: Color = _avg[terrain[row + tx + 1]]
				canvas.draw_texture_rect(_edge[0], Rect2((tx + 1) * tpx - band, ty * tpx, band, tpx), false, c)
			if tx > 0 and terrain[row + tx - 1] != idx:
				var c2: Color = _avg[terrain[row + tx - 1]]
				canvas.draw_texture_rect(_edge[1], Rect2(tx * tpx, ty * tpx, band, tpx), false, c2)
			if ty + 1 < h and terrain[row + w + tx] != idx:
				var c3: Color = _avg[terrain[row + w + tx]]
				canvas.draw_texture_rect(_edge[2], Rect2(tx * tpx, (ty + 1) * tpx - band, tpx, band), false, c3)
			if ty > 0 and terrain[row - w + tx] != idx:
				var c4: Color = _avg[terrain[row - w + tx]]
				canvas.draw_texture_rect(_edge[3], Rect2(tx * tpx, ty * tpx, tpx, band), false, c4)


func refresh_resources(sim, tpx: int, canvas: CanvasItem) -> void:
	var now := Time.get_ticks_msec() / 1000.0
	if not show_resources or now - _res_stamp < 3.0:
		return
	_res_stamp = now
	var xf: Transform2D = canvas.get_viewport().get_canvas_transform()
	var inv := xf.affine_inverse()
	var tl: Vector2 = inv * Vector2.ZERO
	var br: Vector2 = inv * canvas.get_viewport_rect().size
	var reply: Dictionary = sim.op({"op": "resources", "x0": int(tl.x / tpx) - 1, "y0": int(tl.y / tpx) - 1, "x1": int(br.x / tpx) + 1, "y1": int(br.y / tpx) + 1})
	res_nodes = reply.get("nodes", [])


func describe(x: int, y: int) -> String:
	if not in_bounds(x, y):
		return "Outside the map"
	var i := y * w + x
	var caps := ["none", "small", "medium", "big", "mine"]
	var cap: int = build[i]
	var cap_text: String = caps[cap & 7] + ("+port" if (cap & 8) != 0 else "")
	var text := "[b]%s[/b] (%s)\nHeight %d  Build: %s\n" % [terrain_name_at(x, y).replace("summer_", "").replace("_", " "), class_name_at(x, y), height[i], cap_text]
	for n in res_nodes:
		if int(n[0]) == x and int(n[1]) == y:
			text += "Deposit: %s %d\n" % [["", "coal", "iron", "gold", "stones", "fish"][int(n[2])], int(n[3])]
	return text
