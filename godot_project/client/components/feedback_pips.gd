extends HBoxContainer
class_name FeedbackPips

## Four pips summarising a cast: green filled = Fracture (right spell, right locus),
## amber ring = Echo (right spell, wrong locus), grey dot = Fade (no match).
## Pips are always drawn in the order fracture → echo → fade so they never hint
## at positions.

const _VT = preload("res://client/scripts/visual_theme.gd")

var pip_size: float = 18.0
var _pips: Array = []


func _ready() -> void:
	add_theme_constant_override("separation", int(pip_size * 0.35))
	alignment = BoxContainer.ALIGNMENT_CENTER


func show_counts(slot_count: int, fracture: int, echo: int, fade: int) -> void:
	for p in _pips:
		p.queue_free()
	_pips.clear()
	var kinds: Array = []
	for _i in range(fracture):
		kinds.append("fracture")
	for _i in range(echo):
		kinds.append("echo")
	for _i in range(fade):
		kinds.append("fade")
	while kinds.size() < slot_count:
		kinds.append("fade")
	for k in kinds:
		var pip := _Pip.new()
		pip.kind = k
		pip.custom_minimum_size = Vector2(pip_size, pip_size)
		add_child(pip)
		_pips.append(pip)


func pop_in(stagger: float = 0.06) -> void:
	for i in range(_pips.size()):
		var pip: Control = _pips[i]
		pip.scale = Vector2(0.2, 0.2)
		pip.pivot_offset = pip.custom_minimum_size * 0.5
		var tw := pip.create_tween()
		tw.tween_interval(stagger * i)
		tw.tween_property(pip, "scale", Vector2.ONE, 0.18).set_trans(Tween.TRANS_BACK)


class _Pip:
	extends Control
	var kind: String = "fade"

	func _draw() -> void:
		var r := minf(size.x, size.y) * 0.5
		var c := size * 0.5
		match kind:
			"fracture":
				draw_circle(c, r, _VT.COLOR_FRACTURE)
				draw_circle(c, r * 0.45, Color(1, 1, 1, 0.9))
			"echo":
				draw_arc(c, r * 0.78, 0, TAU, 32, _VT.COLOR_ECHO, r * 0.42, true)
			_:
				draw_circle(c, r * 0.45, _VT.COLOR_FADE)
