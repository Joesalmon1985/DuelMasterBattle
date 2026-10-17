extends RefCounted
class_name DmbCharRender

## Draws one character cell from its layer sheets.  Order: outline, skin, hair, cloth a / b / c, untinted detail, beard.
## All sheets of an outfit share one texture, so a crowd of one job is a handful of batched draws per figure.

const Lib = preload("res://client/characters/character_library.gd")

const POSES := ["neutral", "blink", "talk_a", "talk_b", "talk_c", "smile", "worried", "surprised", "angry"]
static var draws := 0   # cells drawn since the last reset (performance tests read this)


## `origin` is the top-left of the cell on `canvas`; `scale` the pixel size of one sprite pixel.
static func draw(canvas: CanvasItem, look, cell: Vector2i, flip: bool, origin: Vector2, scale: float, mod: Color = Color.WHITE, lod: int = 0, shadow: bool = true) -> void:
	var tex: Texture2D = look.outfit_texture()
	if tex == null:
		return
	var cs := Lib.cell()
	var w := float(cs.x) * scale
	var h := float(cs.y) * scale
	if shadow:
		canvas.draw_set_transform(origin + Vector2(w * 0.5, h * (45.0 / float(cs.y))), 0.0, Vector2(1.0, 0.38))
		canvas.draw_circle(Vector2.ZERO, 6.5 * scale, Color(0.0, 0.0, 0.0, 0.26 * mod.a))
	if flip:
		canvas.draw_set_transform(origin + Vector2(w, 0.0), 0.0, Vector2(-1.0, 1.0))
	else:
		canvas.draw_set_transform(origin, 0.0, Vector2.ONE)
	var dest := Rect2(0.0, 0.0, w, h)
	var x := cell.x * cs.x
	var row := cell.y
	canvas.draw_texture_rect_region(tex, dest, _src(x, 0, row, cs), mod)
	canvas.draw_texture_rect_region(tex, dest, _src(x, 1, row, cs), look.tint_skin * mod)
	if lod == 0:
		var ht: Texture2D = look.hair_texture()
		if ht != null:
			canvas.draw_texture_rect_region(ht, dest, Rect2(x, row * cs.y, cs.x, cs.y), look.tint_hair * mod)
	canvas.draw_texture_rect_region(tex, dest, _src(x, 2, row, cs), look.tint_a * mod)
	canvas.draw_texture_rect_region(tex, dest, _src(x, 3, row, cs), look.tint_b * mod)
	canvas.draw_texture_rect_region(tex, dest, _src(x, 4, row, cs), look.tint_c * mod)
	canvas.draw_texture_rect_region(tex, dest, _src(x, 5, row, cs), mod)
	if lod == 0:
		var bt: Texture2D = look.beard_texture()
		if bt != null:
			canvas.draw_texture_rect_region(bt, dest, Rect2(x, row * cs.y, cs.x, cs.y), look.tint_hair * mod)
	canvas.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	draws += 1


static func _src(x: int, band: int, row: int, cs: Vector2i) -> Rect2:
	return Rect2(x, (band * 3 + row) * cs.y, cs.x, cs.y)


static func draw_portrait(canvas: CanvasItem, look, pose: String, rect: Rect2, mod: Color = Color.WHITE) -> void:
	var tex: Texture2D = look.portrait_texture()
	if tex == null:
		return
	var size: int = int(Lib.data().get("portrait", {}).get("size", 64))
	var idx := maxi(0, POSES.find(pose))
	var x := idx * size
	var ps := func(band: int) -> Rect2: return Rect2(x, band * size, size, size)
	canvas.draw_texture_rect_region(tex, rect, ps.call(0), mod)
	canvas.draw_texture_rect_region(tex, rect, ps.call(1), look.tint_skin * mod)
	var ht: Texture2D = look.hair_texture(true)
	if ht != null:
		canvas.draw_texture_rect_region(ht, rect, Rect2(x, 0, size, size), look.tint_hair * mod)
	canvas.draw_texture_rect_region(tex, rect, ps.call(2), look.tint_a * mod)
	canvas.draw_texture_rect_region(tex, rect, ps.call(3), look.tint_b * mod)
	canvas.draw_texture_rect_region(tex, rect, ps.call(4), look.tint_c * mod)
	canvas.draw_texture_rect_region(tex, rect, ps.call(5), mod)
	var bt: Texture2D = look.beard_texture(true)
	if bt != null:
		canvas.draw_texture_rect_region(bt, rect, Rect2(x, 0, size, size), look.tint_hair * mod)
