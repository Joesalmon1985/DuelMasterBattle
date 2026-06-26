extends Control
class_name CompositeWizard
const _VT = preload("res://client/scripts/visual_theme.gd")

const _Art = preload("res://client/scripts/art.gd")

var archetype: String = "player"
var _parts: Dictionary = {}
var _idle_tween: Tween
var _manifest: Dictionary = {}


func _ready() -> void:
	custom_minimum_size = Vector2(96, 128)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func load_archetype(arch: String) -> void:
	archetype = arch
	for c in get_children():
		c.queue_free()
	_parts.clear()
	_manifest = _Art.load_wizard_manifest(archetype)
	var parts: Array = _manifest.get("parts", [])
	parts.sort_custom(func(a, b): return int(a.get("z_index", 0)) < int(b.get("z_index", 0)))
	for spec in parts:
		var name: String = spec.get("name", "")
		var tex := _Art.load_texture(_Art.wizard_part_path(archetype, name))
		if tex == null:
			continue
		var node := TextureRect.new()
		node.texture = tex
		node.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		node.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		node.name = name
		var offset: Array = spec.get("offset", [0, 0])
		node.position = Vector2(offset[0], offset[1])
		node.custom_minimum_size = Vector2(96, 96)
		if spec.has("tint"):
			var t: Array = spec.tint
			node.modulate = Color(t[0], t[1], t[2], t[3] if t.size() > 3 else 1.0)
		add_child(node)
		_parts[name] = node
	if _parts.is_empty():
		var fallback := TextureRect.new()
		fallback.set_anchors_preset(Control.PRESET_FULL_RECT)
		fallback.texture = _Art.load_texture(_Art.enemy_portrait_path(archetype))
		fallback.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		fallback.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		add_child(fallback)
		_parts["fallback"] = fallback
	play_idle()


func play_idle() -> void:
	_stop_idle()
	_idle_tween = create_tween().set_loops()
	if _parts.has("torso"):
		_idle_tween.tween_property(_parts["torso"], "position:y", _parts["torso"].position.y - 3, 1.2)
		_idle_tween.tween_property(_parts["torso"], "position:y", _parts["torso"].position.y + 3, 1.2)
	if _parts.has("back_aura"):
		_idle_tween.parallel().tween_property(_parts["back_aura"], "modulate:a", 0.6, 1.0)
		_idle_tween.tween_property(_parts["back_aura"], "modulate:a", 1.0, 1.0)


func play_cast_windup() -> void:
	_stop_idle()
	var tw := create_tween()
	if _parts.has("right_upper_arm"):
		tw.tween_property(_parts["right_upper_arm"], "rotation", -0.4, _VT.DUR_CAST_WINDUP)
	if _parts.has("cast_glow"):
		tw.parallel().tween_property(_parts["cast_glow"], "modulate:a", 1.0, _VT.DUR_CAST_WINDUP)


func play_hit() -> void:
	var tw := create_tween()
	tw.tween_property(self, "modulate", Color(1.4, 0.75, 0.75), 0.12)
	tw.tween_property(self, "modulate", Color.WHITE, 0.25)


func play_last_stand() -> void:
	play_idle()
	if _parts.has("back_aura"):
		var tw := create_tween().set_loops()
		tw.tween_property(_parts["back_aura"], "modulate", Color(1.3, 0.5, 0.6), 0.5)
		tw.tween_property(_parts["back_aura"], "modulate", Color.WHITE, 0.5)


func _stop_idle() -> void:
	if _idle_tween != null and _idle_tween.is_valid():
		_idle_tween.kill()
	_idle_tween = null
