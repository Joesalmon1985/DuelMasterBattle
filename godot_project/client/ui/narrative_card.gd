extends Control
class_name DmbNarrativeCard

## One card for every narrative panel: a conversation, the arrival text, an inspect panel, the journal, the pause menu. It is built from the
## existing design files (visual_theme.gd for colour and style, responsive_modal.gd for sizes) so all of them look like the same game.
##
## Layout contract (tested in client/tests/run_hybrid_ui.gd at five window sizes): the card is at most `metrics.width` physical pixels wide and always
## fully inside the viewport; text wraps inside it and never grows it; a long body or many choices scroll inside the card; the footer buttons stay
## visible; every button is at least 48 physical pixels tall. Sizes are physical pixels converted by the stretch scale, never shrunk to fit.
##
## kind "sheet": anchored to the bottom centre (conversations, inspecting). kind "modal": centred (arrival, journal, menu).

const _VT = preload("res://client/scripts/visual_theme.gd")
const _RM = preload("res://client/ui/responsive_modal.gd")

signal choice_pressed(id: String)
signal footer_pressed(id: String)

var world: Node
var kind := "sheet"
var panel: PanelContainer
var title_label: Label
var subtitle_label: Label
var progress_label: Label
var scroll: ScrollContainer
var body_box: VBoxContainer
var body_label: RichTextLabel
var choices_box: VBoxContainer
var footer_box: HBoxContainer
var _header: VBoxContainer
var _inner: VBoxContainer
var _choice_ids: Array = []
var _footer_ids: Array = []
var _primary_id := ""
var _fit_queued := false


func setup(p_world: Node, p_kind: String, p_name: String) -> void:
	world = p_world
	kind = p_kind
	name = p_name
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false
	panel = PanelContainer.new()
	panel.name = "Panel"
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(panel)
	_inner = VBoxContainer.new()
	_inner.name = "Inner"
	panel.add_child(_inner)
	_header = VBoxContainer.new()
	_header.name = "Header"
	_inner.add_child(_header)
	title_label = Label.new()
	title_label.name = "Title"
	title_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_header.add_child(title_label)
	subtitle_label = Label.new()
	subtitle_label.name = "Subtitle"
	subtitle_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_header.add_child(subtitle_label)
	progress_label = Label.new()
	progress_label.name = "Progress"
	progress_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_header.add_child(progress_label)
	scroll = ScrollContainer.new()
	scroll.name = "Scroll"
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_inner.add_child(scroll)
	body_box = VBoxContainer.new()
	body_box.name = "Body"
	body_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(body_box)
	body_label = RichTextLabel.new()
	body_label.name = "Text"
	body_label.bbcode_enabled = false
	body_label.fit_content = true
	body_label.scroll_active = false
	body_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body_box.add_child(body_label)
	choices_box = VBoxContainer.new()
	choices_box.name = "Choices"
	choices_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body_box.add_child(choices_box)
	footer_box = HBoxContainer.new()
	footer_box.name = "Footer"
	footer_box.alignment = BoxContainer.ALIGNMENT_END
	_inner.add_child(footer_box)
	get_viewport().size_changed.connect(relayout)
	relayout()


## Fill the card. `choices` and `footer` are [{id, text, kind ("choice" or "primary"), disabled}]. Choice buttons are named Choice_<id> and are
## inside the scrolling body; footer buttons are named Footer_<id> and stay visible below it.
func show_card(title: String, subtitle: String, body: String, choices: Array, footer: Array, progress := "") -> void:
	title_label.text = title
	subtitle_label.text = subtitle
	subtitle_label.visible = subtitle != ""
	progress_label.text = progress
	progress_label.visible = progress != ""
	body_label.text = body
	body_label.visible = body != ""
	for c in choices_box.get_children():
		choices_box.remove_child(c)
		c.queue_free()
	for c in footer_box.get_children():
		footer_box.remove_child(c)
		c.queue_free()
	_choice_ids = []
	_footer_ids = []
	_primary_id = ""
	for c in choices:
		var b := Button.new()
		b.name = "Choice_%s" % str(c["id"]).replace(":", "_")  # (a node name cannot hold a colon: the id is kept in meta)
		b.set_meta("choice_id", str(c["id"]))
		b.text = str(c["text"])
		b.disabled = bool(c.get("disabled", false))
		b.pressed.connect(func() -> void: choice_pressed.emit(str(c["id"])))
		choices_box.add_child(b)
		_choice_ids.append(str(c["id"]))
		if str(c.get("kind", "choice")) == "primary" and _primary_id == "":
			_primary_id = "choice:" + str(c["id"])
	for c in footer:
		var b := Button.new()
		b.name = "Footer_%s" % str(c["id"])
		b.set_meta("choice_id", str(c["id"]))
		b.text = str(c["text"])
		b.disabled = bool(c.get("disabled", false))
		b.pressed.connect(func() -> void: footer_pressed.emit(str(c["id"])))
		footer_box.add_child(b)
		_footer_ids.append(str(c["id"]))
		if str(c.get("kind", "choice")) == "primary" and _primary_id == "":
			_primary_id = "footer:" + str(c["id"])
	visible = true
	relayout()


func hide_card() -> void:
	visible = false


## What Enter or Space does: the primary button, if the card has one.
func activate_primary() -> bool:
	if not visible or _primary_id == "":
		return false
	var parts := _primary_id.split(":", true, 1)
	var b: Button = choice_button(parts[1]) if parts[0] == "choice" else footer_button(parts[1])
	if b == null or b.disabled:
		return false
	b.pressed.emit()
	return true


## What number keys do: press the Nth choice.
func activate_choice_index(i: int) -> bool:
	if not visible or i < 0 or i >= _choice_ids.size():
		return false
	var b: Button = choice_button(str(_choice_ids[i]))
	if b == null or b.disabled:
		return false
	b.pressed.emit()
	return true


func choice_button(id: String) -> Button:
	for b in choices_box.get_children():
		if str(b.get_meta("choice_id", "")) == id:
			return b
	return null


func footer_button(id: String) -> Button:
	for b in footer_box.get_children():
		if str(b.get_meta("choice_id", "")) == id:
			return b
	return null


func has_choice(id: String) -> bool:
	return _choice_ids.has(id)


func choice_ids() -> Array:
	return _choice_ids.duplicate()


## Recompute every size from the window: fonts, button heights, width, and (after layout settles) the height of the scrolling body.
func relayout() -> void:
	if panel == null:
		return
	var info := _RM.window_info(world)
	var m := _RM.metrics(info, kind)
	var k: float = info["k"]
	panel.add_theme_stylebox_override("panel", _VT.narr_card_style(k))
	panel.custom_minimum_size = Vector2(float(m["width"]) * k, 0.0)
	var gap := int(round(float(m["gap"]) * k))
	for box in [_inner, _header, body_box, choices_box]:
		(box as BoxContainer).add_theme_constant_override("separation", gap)
	footer_box.add_theme_constant_override("separation", gap)
	title_label.add_theme_font_size_override("font_size", int(round(float(m["title"]) * k)))
	title_label.add_theme_color_override("font_color", _VT.COLOR_GOLD)
	subtitle_label.add_theme_font_size_override("font_size", int(round(float(m["small"]) * k)))
	subtitle_label.add_theme_color_override("font_color", _VT.COLOR_PARCHMENT_DIM)
	progress_label.add_theme_font_size_override("font_size", int(round(float(m["small"]) * k)))
	progress_label.add_theme_color_override("font_color", _VT.COLOR_GOLD)
	body_label.add_theme_font_size_override("normal_font_size", int(round(float(m["body"]) * k)))
	body_label.add_theme_color_override("default_color", _VT.COLOR_PARCHMENT)
	for b in choices_box.get_children():
		_style_button(b, "choice", m, k)
	for b in footer_box.get_children():
		var primary := _primary_id == "footer:" + str(b.get_meta("choice_id", ""))
		_style_button(b, "primary" if primary else "choice", m, k)
	for b in choices_box.get_children():
		if _primary_id == "choice:" + str(b.get_meta("choice_id", "")):
			_style_button(b, "primary", m, k)
	_place(m, k)
	if not _fit_queued:
		_fit_queued = true
		_fit_later.call_deferred()


## Position the panel explicitly from its real size (anchor presets read the size before the content is known): bottom centre for a sheet,
## centre for a modal, always fully inside the viewport.
func _place(m: Dictionary, k: float) -> void:
	var info := _RM.window_info(world)
	var vis: Vector2 = info["vis"]
	var sz := panel.get_combined_minimum_size()
	sz.x = minf(sz.x, vis.x)
	sz.y = minf(sz.y, vis.y)
	panel.size = sz
	var x := (vis.x - sz.x) * 0.5
	var y := (vis.y - sz.y) * 0.5
	if kind == "sheet":
		y = vis.y - sz.y - float(m["margin"]) * k
	panel.position = Vector2(clampf(x, 0.0, maxf(vis.x - sz.x, 0.0)), clampf(y, 0.0, maxf(vis.y - sz.y, 0.0)))


func _style_button(b: Button, btn_kind: String, m: Dictionary, k: float) -> void:
	_VT.style_narr_button(b, k, btn_kind, float(m["body"]))
	b.custom_minimum_size = Vector2(0, float(m["button_h"]) * k)
	var in_footer := b.get_parent() == footer_box
	b.size_flags_horizontal = Control.SIZE_EXPAND_FILL if not in_footer or btn_kind == "primary" else Control.SIZE_SHRINK_END
	if in_footer:
		b.custom_minimum_size.x = minf(float(m["width"]) * 0.32, 180.0) * k


func _fit_later() -> void:
	_fit_queued = false
	if panel == null:
		return
	# the wrapped text only knows its height once it has a width, which it gets from the first layout pass: fit twice
	for _pass in 2:
		await get_tree().process_frame
		_fit_once()


func _fit_once() -> void:
	var info := _RM.window_info(world)
	var m := _RM.metrics(info, kind)
	var k: float = info["k"]
	var chrome := _header.get_combined_minimum_size().y + footer_box.get_combined_minimum_size().y + float(panel.get_theme_stylebox("panel").get_minimum_size().y) + float(m["gap"]) * k * 2.0
	var room := float(m["max_h"]) * k - chrome
	# the body's height from the label itself (its min size is refreshed lazily), the choices from their buttons
	var inner_w := float(m["width"]) * k - float(panel.get_theme_stylebox("panel").get_minimum_size().x)
	var bar_w := scroll.get_v_scroll_bar().get_combined_minimum_size().x  # a scrollbar takes width from the text, not from the card
	body_label.custom_minimum_size.x = maxf(inner_w - bar_w - float(m["gap"]) * k * 0.5, 0.0)
	var want := choices_box.get_combined_minimum_size().y
	if body_label.visible:
		want += float(body_label.get_content_height()) + float(m["gap"]) * k
	scroll.custom_minimum_size = Vector2(0, clampf(want, minf(40.0 * k, room), maxf(room, 40.0 * k)))
	panel.reset_size()
	_place(m, k)
