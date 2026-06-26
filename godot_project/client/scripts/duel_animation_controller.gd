extends RefCounted
class_name DuelAnimationController

const _FeedbackDisplay = preload("res://client/components/feedback_display.gd")
const _DuelEvent = preload("res://sim/duel_event.gd")
const _SaveData = preload("res://client/scripts/save_data.gd")

var _board: GameBoard
var _animation_area: Control
var _reduce_motion: bool = false
var _active_tween: Tween


func setup(board: GameBoard, animation_area: Control) -> void:
	_board = board
	_animation_area = animation_area
	_reduce_motion = bool(_SaveData.get_setting("reduce_motion", false))


func consume_events(events: Array) -> void:
	for ev in events:
		if ev.type == _DuelEvent.FEEDBACK_REVEALED:
			_show_feedback(ev.data)
		elif ev.type == _DuelEvent.WARD_BROKEN or ev.type == _DuelEvent.LAST_STAND_STARTED:
			_pulse_barrier()


func _show_feedback(data: Dictionary) -> void:
	if _animation_area == null:
		return
	for c in _animation_area.get_children():
		c.queue_free()
	var row := _FeedbackDisplay.new()
	_animation_area.add_child(row)
	var pattern: Array = data.get("pattern_by_locus", [])
	row.show_attack(
		pattern,
		int(data.get("fracture_count", 0)),
		int(data.get("echo_count", 0)),
		int(data.get("fade_count", 0))
	)
	if _reduce_motion:
		return
	if _active_tween != null and _active_tween.is_valid():
		_active_tween.kill()
	_active_tween = _board.create_tween()
	row.modulate.a = 0.0
	_active_tween.tween_property(row, "modulate:a", 1.0, 0.35)


func _pulse_barrier() -> void:
	if _reduce_motion or _board == null:
		return
	var enemy := _board.get_node_or_null("VBox/DuelPanel/EnemyColumn/EnemyWizard")
	if enemy == null:
		return
	if _active_tween != null and _active_tween.is_valid():
		_active_tween.kill()
	_active_tween = _board.create_tween()
	_active_tween.tween_property(enemy, "modulate", Color(1.4, 0.8, 0.8), 0.15)
	_active_tween.tween_property(enemy, "modulate", Color.WHITE, 0.25)
