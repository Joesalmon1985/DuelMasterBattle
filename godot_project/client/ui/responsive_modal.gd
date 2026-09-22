extends RefCounted
class_name DmbResponsiveModal

## Shared full-screen modal chrome for G06 overlays (map / chronicle).
## Layout only — no gameplay ownership.


static func safe_margin(viewport_size: Vector2) -> float:
	return clampf(minf(viewport_size.x, viewport_size.y) * 0.03, 12.0, 20.0)


static func build_shell(host: Control, title_text: String = "") -> Dictionary:
	## Returns { dim, margin, panel, header, title, close_btn, body, root_v }
	## Uses MarginContainer → Panel (expand fill). No PRESET_CENTER / manual offsets.
	host.set_anchors_preset(Control.PRESET_FULL_RECT)
	host.mouse_filter = Control.MOUSE_FILTER_STOP
	var dim := ColorRect.new()
	dim.name = "Dim"
	dim.color = Color(0, 0, 0, 0.55)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_STOP
	host.add_child(dim)
	var margin := MarginContainer.new()
	margin.name = "SafeMargin"
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	margin.mouse_filter = Control.MOUSE_FILTER_IGNORE
	host.add_child(margin)
	var panel := PanelContainer.new()
	panel.name = "Panel"
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.08, 0.09, 0.12, 0.96)
	style.set_corner_radius_all(8)
	style.content_margin_left = 10
	style.content_margin_right = 10
	style.content_margin_top = 8
	style.content_margin_bottom = 8
	panel.add_theme_stylebox_override("panel", style)
	margin.add_child(panel)
	var root_v := VBoxContainer.new()
	root_v.name = "RootV"
	root_v.add_theme_constant_override("separation", 8)
	root_v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	root_v.size_flags_vertical = Control.SIZE_EXPAND_FILL
	panel.add_child(root_v)
	var header := HBoxContainer.new()
	header.name = "Header"
	header.add_theme_constant_override("separation", 8)
	root_v.add_child(header)
	var title := Label.new()
	title.name = "Title"
	title.text = title_text
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	title.add_theme_font_size_override("font_size", 16)
	header.add_child(title)
	var close_btn := Button.new()
	close_btn.name = "CloseButton"
	close_btn.text = "Close"
	close_btn.custom_minimum_size = Vector2(96, 48)
	close_btn.mouse_filter = Control.MOUSE_FILTER_STOP
	header.add_child(close_btn)
	var body := VBoxContainer.new()
	body.name = "Body"
	body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 8)
	root_v.add_child(body)
	return {
		"dim": dim,
		"margin": margin,
		"panel": panel,
		"header": header,
		"title": title,
		"close_btn": close_btn,
		"body": body,
		"root_v": root_v,
	}


static func apply_margins(margin: MarginContainer, viewport_size: Vector2) -> void:
	var m := int(safe_margin(viewport_size))
	margin.add_theme_constant_override("margin_left", m)
	margin.add_theme_constant_override("margin_right", m)
	margin.add_theme_constant_override("margin_top", m)
	margin.add_theme_constant_override("margin_bottom", m)


static func apply_panel_bounds(
	panel: Control,
	viewport_size: Vector2,
	width_frac: float = 0.94,
	height_frac: float = 0.88
) -> void:
	## With MarginContainer parent, expand-fill already maximises usable area.
	## Keep a soft minimum so tiny viewports still get a usable panel.
	var m := safe_margin(viewport_size) * 2.0
	var max_w := maxf(180.0, viewport_size.x - m)
	var max_h := maxf(220.0, viewport_size.y - m)
	var target_w := clampf(viewport_size.x * width_frac, 180.0, max_w)
	var target_h := clampf(viewport_size.y * height_frac, 220.0, max_h)
	panel.custom_minimum_size = Vector2(minf(target_w, max_w), minf(target_h, max_h))


static func rect_fully_inside(rect: Rect2, viewport: Rect2, tol: float = 1.0) -> bool:
	return (
		rect.position.x >= viewport.position.x - tol
		and rect.position.y >= viewport.position.y - tol
		and rect.end.x <= viewport.end.x + tol
		and rect.end.y <= viewport.end.y + tol
	)
