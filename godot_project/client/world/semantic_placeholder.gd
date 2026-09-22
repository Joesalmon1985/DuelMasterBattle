extends RefCounted
class_name DmbSemanticPlaceholder

## Draw readable semantic placeholders. Sets meta `semantic_id` on Controls.


static func apply_identity(node: CanvasItem, semantic_id: String) -> void:
	node.set_meta("semantic_id", semantic_id)
	if node is Control:
		(node as Control).tooltip_text = semantic_id


static func make_badge(semantic_id: String, size: Vector2 = Vector2(48, 48), desc: Dictionary = {}) -> Control:
	var panel := PanelContainer.new()
	panel.name = "Sem_" + semantic_id.replace(".", "_")
	panel.custom_minimum_size = size
	apply_identity(panel, semantic_id)
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.15, 0.16, 0.2, 0.95)
	style.border_color = Color(0.85, 0.85, 0.88)
	style.set_border_width_all(2)
	style.set_corner_radius_all(4)
	panel.add_theme_stylebox_override("panel", style)
	var v := VBoxContainer.new()
	v.alignment = BoxContainer.ALIGNMENT_CENTER
	panel.add_child(v)
	var shape_lbl := Label.new()
	var shape := str(desc.get("shape", "rect"))
	shape_lbl.text = _shape_glyph(shape)
	shape_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	shape_lbl.add_theme_font_size_override("font_size", 14)
	v.add_child(shape_lbl)
	var abbr := Label.new()
	abbr.text = str(desc.get("abbrev", semantic_id.get_slice(".", semantic_id.get_slice_count(".") - 1))).substr(0, 4)
	abbr.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	abbr.add_theme_font_size_override("font_size", 11)
	v.add_child(abbr)
	return panel


static func _shape_glyph(shape: String) -> String:
	match shape:
		"triangle":
			return "▲"
		"diamond":
			return "◆"
		"circle":
			return "●"
		"hex":
			return "⬡"
		"star":
			return "★"
		"gear":
			return "⚙"
		"blob":
			return "◉"
		"oval":
			return "⬭"
		"trefoil":
			return "☢"
		"portrait_rect":
			return "▣"
		_:
			return "■"
