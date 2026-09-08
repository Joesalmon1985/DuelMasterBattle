extends Control
class_name PixelPortrait

## Pixel-art opponent portrait for the battle screen. Same animation surface
## as CompositeWizard (play_idle / play_cast_windup / play_hit) so the board
## does not care which it is showing.

var _tex: TextureRect
var _idle_tween: Tween
var _base_pos: Vector2 = Vector2.ZERO


func _ready() -> void:
	_tex = TextureRect.new()
	_tex.set_anchors_preset(Control.PRESET_FULL_RECT)
	_tex.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_tex.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_tex.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_tex.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_tex)
	_tex.pivot_offset = size * 0.5
	resized.connect(func(): _tex.pivot_offset = size * 0.5)


static func portrait_path(archetype: String) -> String:
	var creature := "res://assets/pixel/creatures/%s_portrait_0.png" % archetype
	if ResourceLoader.exists(creature):
		return creature
	var wiz := "res://assets/pixel/portraits/%s.png" % archetype
	if ResourceLoader.exists(wiz):
		return wiz
	return ""


static func has_portrait(archetype: String) -> bool:
	return portrait_path(archetype) != ""


func load_archetype(archetype: String) -> void:
	var p := portrait_path(archetype)
	if p == "":
		p = "res://assets/pixel/portraits/wizard.png"
	_tex.texture = load(p)
	play_idle()


func play_idle() -> void:
	_stop_idle()
	_tex.scale = Vector2.ONE
	_idle_tween = create_tween().set_loops()
	_idle_tween.tween_property(_tex, "position:y", -4.0, 1.1).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	_idle_tween.tween_property(_tex, "position:y", 0.0, 1.1).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)


func play_cast_windup() -> void:
	_stop_idle()
	var tw := create_tween()
	tw.tween_property(_tex, "scale", Vector2(1.08, 0.94), 0.12)
	tw.tween_property(_tex, "scale", Vector2(0.96, 1.06), 0.1)
	tw.tween_property(_tex, "scale", Vector2.ONE, 0.12)
	tw.tween_callback(play_idle)


func play_hit() -> void:
	_stop_idle()
	var tw := create_tween()
	tw.tween_property(_tex, "modulate", Color(1.6, 0.8, 0.8), 0.06)
	tw.tween_property(_tex, "position:x", 8.0, 0.05)
	tw.tween_property(_tex, "position:x", -8.0, 0.05)
	tw.tween_property(_tex, "position:x", 0.0, 0.05)
	tw.tween_property(_tex, "modulate", Color.WHITE, 0.15)
	tw.tween_callback(play_idle)


func play_last_stand() -> void:
	play_hit()


func _stop_idle() -> void:
	if _idle_tween and _idle_tween.is_valid():
		_idle_tween.kill()
	_tex.position = Vector2.ZERO
