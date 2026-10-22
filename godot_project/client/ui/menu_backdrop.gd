extends Control

## The main menu's living backdrop (docs/POLISH_WATCHING_FEEL.md): slow motes of gold and violet rising behind the title, each on its own
## drift, and a soft breathing glow low on the screen. Drawn, never loaded; nothing to click. It stops when hidden.

const COUNT := 42
var _motes: Array = []  # {pos (0..1 of the screen), vel, size, col, phase}
var _t := 0.0
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	name = "MenuBackdrop"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_rng.seed = 5
	for i in COUNT:
		_motes.append(_spawn(true))


func _spawn(anywhere: bool) -> Dictionary:
	var gold := _rng.randf() < 0.55
	return {"pos": Vector2(_rng.randf(), _rng.randf() if anywhere else 1.05), "vel": Vector2(_rng.randf_range(-0.01, 0.01), -_rng.randf_range(0.018, 0.045)),
		"size": _rng.randf_range(1.5, 4.0), "col": (Color(1.0, 0.85, 0.45) if gold else Color(0.65, 0.55, 0.95)), "phase": _rng.randf_range(0.0, TAU),
		"alpha": _rng.randf_range(0.18, 0.5)}


func _process(delta: float) -> void:
	if not is_visible_in_tree():
		return
	_t += delta
	for i in _motes.size():
		var m: Dictionary = _motes[i]
		m["pos"] += m["vel"] * delta
		if m["pos"].y < -0.05:
			_motes[i] = _spawn(false)
	queue_redraw()


func _draw() -> void:
	var sz := size
	# a soft glow breathing behind the lower half, where the buttons sit
	var breathe := 0.5 + 0.5 * sin(_t * 0.6)
	for i in 4:
		var r := sz.x * (0.55 + 0.12 * i) * (0.96 + 0.04 * breathe)
		draw_circle(Vector2(sz.x * 0.5, sz.y * 0.82), r, Color(0.45, 0.3, 0.8, 0.035 * (1.0 - float(i) * 0.2)))
	for m in _motes:
		var p: Vector2 = m["pos"]
		var wob := sin(_t * 0.9 + float(m["phase"])) * 0.012
		var at := Vector2((p.x + wob) * sz.x, p.y * sz.y)
		var col: Color = m["col"]
		var a: float = float(m["alpha"]) * (0.6 + 0.4 * sin(_t * 1.3 + float(m["phase"])))
		draw_circle(at, float(m["size"]) * 2.2, Color(col.r, col.g, col.b, a * 0.25))
		draw_circle(at, float(m["size"]), Color(col.r, col.g, col.b, a))
