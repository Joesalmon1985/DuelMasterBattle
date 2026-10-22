extends Control

## The table's small celebrations (docs/POLISH_WATCHING_FEEL.md): a ring where a card, die or tile was tapped, a gold flare and a shower of
## sparks for a win, a grey settle for a loss, and the result's banner. A full-screen layer over the panel that never takes input. Drawn, never loaded.

const _VT = preload("res://client/scripts/visual_theme.gd")

var _parts: Array = []  # {pos, vel, t, life, size, col, kind}
var _banner: Label
var _banner_tween: Tween
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	name = "TableFx"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_rng.seed = 11
	_banner = Label.new()
	_banner.name = "Banner"
	_banner.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_banner.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_banner.visible = false
	add_child(_banner)


func _process(delta: float) -> void:
	if _parts.is_empty():
		if _banner.visible:
			queue_redraw()  # the band behind the banner follows its fade
		return
	var keep: Array = []
	for p in _parts:
		p["t"] += delta
		if p["t"] < p["life"]:
			p["vel"] += Vector2(0, 520.0) * delta if str(p["kind"]) == "spark" else Vector2.ZERO
			p["pos"] += p["vel"] * delta
			keep.append(p)
	_parts = keep
	queue_redraw()


## A ring spreading from where a widget was tapped (screen position).
func tap_ring(at: Vector2, col: Color = Color(0.95, 0.85, 0.45)) -> void:
	_parts.append({"pos": at, "vel": Vector2.ZERO, "t": 0.0, "life": 0.3, "size": 26.0, "col": col, "kind": "ring"})
	queue_redraw()


## The result: "win" showers gold sparks from the panel's top, "lose" settles grey, "draw" a soft ring. `rect` is the panel on screen.
func result(kind: String, text: String, rect: Rect2, font_px: int) -> void:
	var col := _VT.COLOR_GOLD
	match kind:
		"win":
			for i in 42:
				var x := rect.position.x + _rng.randf_range(0.1, 0.9) * rect.size.x
				_parts.append({"pos": Vector2(x, rect.position.y + rect.size.y * 0.5), "vel": Vector2(_rng.randf_range(-60, 60), _rng.randf_range(-40, 80)), "t": 0.0,
					"life": _rng.randf_range(0.9, 1.6), "size": _rng.randf_range(4.0, 9.0), "col": [Color(1.0, 0.85, 0.35), Color(0.95, 0.6, 0.3), Color(1.0, 0.95, 0.7)][i % 3], "kind": "spark"})
		"lose":
			col = _VT.COLOR_PARCHMENT
			_parts.append({"pos": rect.get_center(), "vel": Vector2.ZERO, "t": 0.0, "life": 0.7, "size": rect.size.x * 0.2, "col": Color(0.5, 0.48, 0.55, 0.25), "kind": "ring"})
		_:
			col = _VT.COLOR_PARCHMENT
			_parts.append({"pos": rect.get_center(), "vel": Vector2.ZERO, "t": 0.0, "life": 0.7, "size": rect.size.x * 0.25, "col": Color(0.9, 0.85, 0.7, 0.6), "kind": "ring"})
	_banner.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_banner.text = text
	_banner.add_theme_font_size_override("font_size", font_px)
	_banner.add_theme_color_override("font_color", col)
	_banner.add_theme_color_override("font_outline_color", Color(0.05, 0.03, 0.08, 0.9))
	_banner.add_theme_constant_override("outline_size", maxi(4, int(font_px * 0.18)))
	var w := rect.size.x
	_banner.size = Vector2(w, maxf(rect.size.y, font_px * 1.4))
	_banner.position = rect.position
	_banner.pivot_offset = _banner.size * 0.5
	_banner.visible = true
	_banner.modulate = Color(1, 1, 1, 0)
	_banner.scale = Vector2(0.6, 0.6)
	if _banner_tween != null and _banner_tween.is_valid():
		_banner_tween.kill()
	_banner_tween = create_tween()
	_banner_tween.set_parallel(true)
	_banner_tween.tween_property(_banner, "modulate:a", 1.0, 0.18)
	_banner_tween.tween_property(_banner, "scale", Vector2.ONE, 0.32).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	_banner_tween.chain().tween_interval(1.5)
	_banner_tween.chain().tween_property(_banner, "modulate:a", 0.0, 0.5)
	_banner_tween.chain().tween_callback(func() -> void: _banner.visible = false)
	queue_redraw()


func clear() -> void:
	_parts = []
	if _banner_tween != null and _banner_tween.is_valid():
		_banner_tween.kill()
	_banner.visible = false
	queue_redraw()


func banner_visible() -> bool:
	return _banner.visible


func _draw() -> void:
	if _banner.visible:  # a dark band behind the words, so they read over a full slate
		var r := Rect2(_banner.position, _banner.size)
		var band := StyleBoxFlat.new()
		band.bg_color = Color(0.05, 0.03, 0.09, 0.82 * _banner.modulate.a)
		band.border_color = Color(_VT.COLOR_GOLD.r, _VT.COLOR_GOLD.g, _VT.COLOR_GOLD.b, 0.6 * _banner.modulate.a)
		band.set_border_width_all(2)
		band.set_corner_radius_all(int(r.size.y * 0.3))
		draw_style_box(band, r)
	for p in _parts:
		var k: float = float(p["t"]) / float(p["life"])
		var col: Color = p["col"]
		var pos: Vector2 = p["pos"]
		match str(p["kind"]):
			"ring":
				draw_arc(pos, float(p["size"]) * (0.4 + 0.6 * k), 0.0, TAU, 40, Color(col.r, col.g, col.b, col.a * (1.0 - k)), 3.0)
			"spark":
				var s: float = float(p["size"]) * (1.0 - k * 0.5)
				draw_rect(Rect2(pos - Vector2(s, s) * 0.5, Vector2(s, s)), Color(col.r, col.g, col.b, 1.0 - k * k), true)
