extends RefCounted
class_name DmbSemanticPlaceholder

## Draw readable semantic placeholders. Sets meta `semantic_id` on Controls.


static func apply_identity(node: CanvasItem, semantic_id: String) -> void:
	node.set_meta("semantic_id", semantic_id)
	if node is Control:
		(node as Control).tooltip_text = semantic_id


static func make_badge(semantic_id: String, size: Vector2 = Vector2(48, 48), desc: Dictionary = {}) -> Control:
	## Honour registry shape/border/abbrev so placeholders stay distinguishable.
	var panel := PanelContainer.new()
	panel.name = "Sem_" + semantic_id.replace(".", "_")
	panel.custom_minimum_size = size
	apply_identity(panel, semantic_id)
	var shape := str(desc.get("shape", "rect"))
	var border := str(desc.get("border", "solid"))
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.15, 0.16, 0.2, 0.95)
	style.border_color = Color(0.85, 0.85, 0.88)
	var border_w := 2
	if border == "double":
		border_w = 3
		style.border_color = Color(0.95, 0.9, 0.55)
	elif border == "dashed" or border == "dotted":
		border_w = 1
		style.border_color = Color(0.65, 0.8, 0.95)
	style.set_border_width_all(border_w)
	var radius := 4
	if shape == "circle" or shape == "oval" or shape == "blob":
		radius = int(min(size.x, size.y) / 2.0)
	elif shape == "rounded_rect" or shape == "portrait_rect":
		radius = 10
	elif shape == "diamond" or shape == "hex" or shape == "triangle":
		radius = 2
	style.set_corner_radius_all(radius)
	panel.add_theme_stylebox_override("panel", style)
	var v := VBoxContainer.new()
	v.alignment = BoxContainer.ALIGNMENT_CENTER
	panel.add_child(v)
	var shape_lbl := Label.new()
	shape_lbl.text = _shape_glyph(shape)
	shape_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	shape_lbl.add_theme_font_size_override("font_size", 14)
	v.add_child(shape_lbl)
	var abbr := Label.new()
	var abbrev := str(desc.get("abbrev", ""))
	if abbrev.is_empty():
		abbrev = semantic_id.get_slice(".", semantic_id.get_slice_count(".") - 1)
	abbr.text = abbrev.substr(0, 4)
	abbr.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	abbr.add_theme_font_size_override("font_size", 11)
	v.add_child(abbr)
	if desc.has("label") and str(desc.get("label")) != "":
		panel.tooltip_text = "%s [%s]" % [str(desc.get("label")), semantic_id]
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
		"line":
			return "—"
		"rounded_rect":
			return "▢"
		_:
			return "■"
