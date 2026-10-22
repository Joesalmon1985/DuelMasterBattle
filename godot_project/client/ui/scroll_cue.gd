extends Control

## A cue that there is more below (red team, docs/POLISH_RED_BLUE.md): a soft dark band and a bobbing chevron along the bottom edge of a
## ScrollContainer while content is hidden under it; it fades as the reader reaches the end. Drawn; takes no input. The owner adds it as a
## full-rect child above the panel and sets `target`.

var target: ScrollContainer
var _shown := 0.0
var _t := 0.0


func _ready() -> void:
	name = "ScrollCue"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)


func _process(delta: float) -> void:
	_t += delta
	var want := 0.0
	if target != null and is_instance_valid(target) and target.is_visible_in_tree():
		var bar := target.get_v_scroll_bar()
		if bar != null and bar.max_value - bar.page - bar.value > 6.0:
			want = 1.0
	var before := _shown
	_shown = move_toward(_shown, want, delta * 5.0)
	if _shown != before or _shown > 0.0:
		queue_redraw()


func more_below() -> bool:
	return _shown > 0.5


func _draw() -> void:
	if _shown <= 0.0 or target == null or not is_instance_valid(target):
		return
	var r := target.get_global_rect()
	r.position -= global_position
	var band_h := minf(34.0, r.size.y * 0.25)
	var steps := 7
	for i in steps:
		var y := r.end.y - band_h * (1.0 - float(i) / float(steps))
		var a := 0.55 * _shown * float(i + 1) / float(steps)
		draw_rect(Rect2(r.position.x, y, r.size.x, band_h / float(steps) + 1.0), Color(0.05, 0.03, 0.09, a), true)
	var bob := sin(_t * 3.0) * 2.0
	var c := Vector2(r.get_center().x, r.end.y - 9.0 + bob)
	var col := Color(0.89, 0.73, 0.37, _shown)
	draw_line(c + Vector2(-9, -5), c, col, 3.0)
	draw_line(c, c + Vector2(9, -5), col, 3.0)
