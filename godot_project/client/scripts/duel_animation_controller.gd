extends RefCounted
class_name DuelAnimationController

const _VT = preload("res://client/scripts/visual_theme.gd")
const _DuelEvent = preload("res://sim/duel_event.gd")
const _SpellVfx = preload("res://client/components/spell_vfx.gd")
const _SaveData = preload("res://client/scripts/save_data.gd")
const _WardBarrier = preload("res://client/components/ward_barrier.gd")
const _FeedbackChip = preload("res://client/components/feedback_chip.gd")

var _board
var _animation_area: Control
var _travel_layer: Control
var _result_cluster: HBoxContainer
var _ward
var _reduce_motion: bool = false
var _active_tweens: Array = []


func setup(
	board,
	animation_area: Control,
	travel_layer: Control,
	result_cluster: HBoxContainer,
	ward
) -> void:
	_board = board
	_animation_area = animation_area
	_travel_layer = travel_layer
	_result_cluster = result_cluster
	_ward = ward
	_reduce_motion = bool(_SaveData.get_setting("reduce_motion", false))


func consume_events(events: Array) -> void:
	for ev in events:
		match ev.type:
			_DuelEvent.ATTACK_LAUNCHED:
				_on_attack_launched(ev.data)
			_DuelEvent.FEEDBACK_REVEALED:
				_on_feedback_revealed(ev.data)
			_DuelEvent.WARD_BROKEN, _DuelEvent.LAST_STAND_STARTED:
				_on_ward_state(ev.type)


func _on_attack_launched(data: Dictionary) -> void:
	if _reduce_motion:
		return
	var pattern: Array = data.get("pattern_by_locus", [])
	var target_pos: Vector2 = _ward.global_position + _ward.size * 0.5 if _ward else Vector2(360, 200)
	for i in range(pattern.size()):
		var essence := int(pattern[i])
		var bolt := _SpellVfx.new()
		_travel_layer.add_child(bolt)
		bolt.position = Vector2(80 + i * 40, _travel_layer.size.y * 0.5)
		bolt.setup(essence)
		var tw := bolt.launch_toward(target_pos, _VT.DUR_PROJECTILE)
		tw.finished.connect(bolt.queue_free)
	if _ward:
		_ward.set_state(_WardBarrier.State.IMPACTED)
		_SpellVfx.spawn_impact(_travel_layer, target_pos)


func _on_feedback_revealed(_data: Dictionary) -> void:
	if _reduce_motion or _result_cluster == null:
		return
	for chip in _result_cluster.get_children():
		if chip.has_method("pop_in") and chip.visible:
			chip.pop_in()


func _on_ward_state(ev_type: String) -> void:
	if _ward == null or _reduce_motion:
		return
	if ev_type == _DuelEvent.WARD_BROKEN:
		_ward.set_state(_WardBarrier.State.FRACTURED)
	elif ev_type == _DuelEvent.LAST_STAND_STARTED:
		_ward.set_state(_WardBarrier.State.UNSTABLE)
