extends Control
class_name WardBarrier
const _VT = preload("res://client/scripts/visual_theme.gd")

enum State { STABLE, IMPACTED, FRACTURED, UNSTABLE, BROKEN }

const _Art = preload("res://client/scripts/art.gd")

var state: State = State.STABLE

var _layers: Dictionary = {}
var _impact_tween: Tween


func _ready() -> void:
	custom_minimum_size = Vector2(200, 120)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	for part in ["outer_ring", "inner_ring", "runes", "surface", "cracks", "instability"]:
		var tr := TextureRect.new()
		tr.set_anchors_preset(Control.PRESET_FULL_RECT)
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var tex := _Art.load_texture(_Art.ward_part_path(part))
		if tex != null:
			tr.texture = tex
		add_child(tr)
		_layers[part] = tr
	_set_layer_visible("cracks", false)
	_set_layer_visible("instability", false)


func _set_layer_visible(part: String, on: bool) -> void:
	if _layers.has(part):
		_layers[part].visible = on


func set_state(new_state: State) -> void:
	state = new_state
	match state:
		State.STABLE:
			modulate = Color.WHITE
			_set_layer_visible("cracks", false)
			_set_layer_visible("instability", false)
		State.IMPACTED:
			_play_impact()
		State.FRACTURED:
			_set_layer_visible("cracks", true)
		State.UNSTABLE:
			_set_layer_visible("cracks", true)
			_set_layer_visible("instability", true)
			_pulse_instability()
		State.BROKEN:
			modulate = Color(0.5, 0.5, 0.6, 0.8)


func _play_impact() -> void:
	if _impact_tween != null and _impact_tween.is_valid():
		_impact_tween.kill()
	_impact_tween = create_tween()
	_impact_tween.tween_property(self, "scale", Vector2(1.08, 1.08), _VT.DUR_IMPACT * 0.4)
	_impact_tween.tween_property(self, "scale", Vector2.ONE, _VT.DUR_IMPACT * 0.6)
	if _layers.has("runes"):
		_impact_tween.parallel().tween_property(_layers["runes"], "rotation", 0.3, _VT.DUR_IMPACT)
		_impact_tween.chain().tween_property(_layers["runes"], "rotation", 0.0, 0.2)


func _pulse_instability() -> void:
	if _impact_tween != null and _impact_tween.is_valid():
		_impact_tween.kill()
	_impact_tween = create_tween().set_loops()
	_impact_tween.tween_property(self, "modulate", Color(1.3, 0.8, 0.9), 0.45)
	_impact_tween.tween_property(self, "modulate", Color.WHITE, 0.45)
