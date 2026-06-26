extends Node2D
class_name SpellVfx
const _VT = preload("res://client/scripts/visual_theme.gd")

const _Art = preload("res://client/scripts/art.gd")
const _FeedbackChip = preload("res://client/components/feedback_chip.gd")

var essence_id: int = 0
var _layers: Array = []


func setup(essence: int) -> void:
	essence_id = essence
	for c in get_children():
		c.queue_free()
	_layers.clear()
	for layer_name in ["trail", "outer_aura", "inner_glow", "core_glyph"]:
		var spr := Sprite2D.new()
		spr.texture = _Art.load_texture(_Art.essence_layer_path(essence, layer_name))
		if spr.texture == null:
			continue
		spr.centered = true
		spr.modulate = DmbColourData.COLOURS[essence].lerp(Color.WHITE, 0.25)
		add_child(spr)
		_layers.append(spr)


func launch_toward(target: Vector2, duration: float = _VT.DUR_PROJECTILE) -> Tween:
	var tw := create_tween()
	tw.tween_property(self, "global_position", target, duration).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	for spr in _layers:
		tw.parallel().tween_property(spr, "rotation", spr.rotation + PI * 0.5, duration)
	return tw


static func spawn_impact(parent: Node, at: Vector2) -> void:
	var root := Node2D.new()
	root.global_position = at
	parent.add_child(root)
	for part in ["impact_flash", "shockwave_ring", "ward_ripple"]:
		var spr := Sprite2D.new()
		spr.texture = _Art.load_texture(_Art.effect_part_path(part))
		if spr.texture == null:
			continue
		spr.centered = true
		root.add_child(spr)
		var tw := root.create_tween()
		spr.scale = Vector2(0.2, 0.2)
		tw.tween_property(spr, "scale", Vector2(1.4, 1.4), _VT.DUR_IMPACT)
		tw.parallel().tween_property(spr, "modulate:a", 0.0, _VT.DUR_IMPACT)
	root.get_tree().create_timer(_VT.DUR_IMPACT + 0.1).timeout.connect(root.queue_free)


static func spawn_feedback_burst(parent: Control, fracture: int, echo: int, fade: int) -> void:
	var cluster := HBoxContainer.new()
	cluster.alignment = BoxContainer.ALIGNMENT_CENTER
	cluster.add_theme_constant_override("separation", 10)
	parent.add_child(cluster)
	var kinds := [
		["fracture", fracture],
		["echo", echo],
		["fade", fade],
	]
	kinds.shuffle()
	for pair in kinds:
		var chip := _FeedbackChip.new()
		chip.setup(pair[0], int(pair[1]))
		cluster.add_child(chip)
		chip.pop_in()
	cluster.get_tree().create_timer(2.5).timeout.connect(cluster.queue_free)
