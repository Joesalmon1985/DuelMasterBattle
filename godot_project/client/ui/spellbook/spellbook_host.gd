extends Control
class_name SpellbookHost

## Reusable animated spellbook presentation. Binds to SpellbookModel only.
## Open book is a bounded centred panel. All text/controls live inside measured
## parchment-safe rectangles (see SpellbookMargins) — never on leather, spine,
## decorations, or outside the drawn artwork.

const Margins = preload("res://client/ui/spellbook/spellbook_margins.gd")
const ModelScript = preload("res://client/ui/spellbook/spellbook_model.gd")

signal action_requested(action_id: String, payload: Dictionary, token: String)
signal targeting_cancelled(action_id: String)
signal close_requested
signal exit_menu_requested
signal classic_hud_toggled(enabled: bool)
signal world_target_needed(active: bool)
signal overlay_blocking_changed(blocking: bool)

var model = null

var _blocker: ColorRect
var _compact: Control
var _compact_btn: Button
var _compact_summary: Label
var _open_root: Control
var _art: TextureRect
var _debug_layer: Control
var _content_left: Control
var _content_right: Control
var _content_single: Control
var _scroll_left: ScrollContainer
var _scroll_right: ScrollContainer
var _scroll_single: ScrollContainer
var _left_box: VBoxContainer
var _right_box: VBoxContainer
var _single_box: VBoxContainer
var _panel_close: Button
var _header: Label
var _result_lbl: Label
var _body: RichTextLabel
var _actions: VBoxContainer
var _nav: HBoxContainer
var _page_tabs: Control
var _log: RichTextLabel
var _confirm_panel: PanelContainer
var _targeting_card: Control
var _targeting_lbl: Label
var _targeting_guide: Label
var _tween: Tween
var _use_spread := false
var _press_guard_msec := 0
var _press_guard_key := ""
var _last_built_page := ""
var _built := false
var _was_blocking := false
var _tex_size := Vector2(1248, 832)
var _panel_size := Vector2.ZERO
var _drawn_size := Vector2.ZERO
var _drawn_origin := Vector2.ZERO


func _ready() -> void:
	set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ensure_built()
	set_process(true)
	set_process_unhandled_input(true)


func bind_model(m) -> void:
	_ensure_built()
	if model != null and model.changed.is_connected(_on_model_changed):
		model.changed.disconnect(_on_model_changed)
	model = m
	if model == null:
		return
	model.changed.connect(_on_model_changed)
	model.action_requested.connect(func(a, p, t): emit_signal("action_requested", a, p, t))
	model.targeting_cancelled.connect(func(a): emit_signal("targeting_cancelled", a))
	model.close_requested.connect(func(): emit_signal("close_requested"))
	model.exit_menu_requested.connect(func(): emit_signal("exit_menu_requested"))
	model.classic_hud_toggled.connect(func(e): emit_signal("classic_hud_toggled", e))
	_on_model_changed()


func _ensure_built() -> void:
	if _built:
		return
	_built = true
	_build()


func _build() -> void:
	_blocker = ColorRect.new()
	_blocker.name = "SpellbookBlocker"
	_blocker.color = Color(0, 0, 0, 0.42)
	_blocker.set_anchors_preset(PRESET_FULL_RECT)
	_blocker.mouse_filter = Control.MOUSE_FILTER_STOP
	_blocker.visible = false
	_blocker.gui_input.connect(_on_blocker_input)
	add_child(_blocker)

	_compact = Control.new()
	_compact.name = "CompactLauncher"
	_compact.set_anchors_preset(PRESET_BOTTOM_RIGHT)
	_compact.offset_left = -220
	_compact.offset_top = -Margins.COMPACT_BOTTOM_CLEARANCE - 110
	_compact.offset_right = -Margins.COMPACT_SIDE_PAD
	_compact.offset_bottom = -Margins.COMPACT_BOTTOM_CLEARANCE
	_compact.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_compact)

	var card_art := TextureRect.new()
	card_art.texture = load(Margins.TEX_CARD)
	card_art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	card_art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	card_art.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	card_art.set_anchors_preset(PRESET_FULL_RECT)
	card_art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_compact.add_child(card_art)

	var card_margin := MarginContainer.new()
	card_margin.set_anchors_preset(PRESET_FULL_RECT)
	card_margin.add_theme_constant_override("margin_left", 48)
	card_margin.add_theme_constant_override("margin_right", 18)
	card_margin.add_theme_constant_override("margin_top", 22)
	card_margin.add_theme_constant_override("margin_bottom", 22)
	card_margin.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_compact.add_child(card_margin)

	var cv := VBoxContainer.new()
	cv.add_theme_constant_override("separation", 4)
	card_margin.add_child(cv)

	_compact_btn = Button.new()
	_compact_btn.text = "Open Spellbook"
	_compact_btn.focus_mode = Control.FOCUS_NONE
	_compact_btn.custom_minimum_size = Vector2(0, Margins.TOUCH_MIN)
	_compact_btn.pressed.connect(_on_open_pressed)
	_style_ink_button(_compact_btn)
	cv.add_child(_compact_btn)

	_compact_summary = Label.new()
	_compact_summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_compact_summary.add_theme_font_size_override("font_size", Margins.scaled_font(Margins.CAPTION_FONT))
	_compact_summary.add_theme_color_override("font_color", Margins.TEXT_INK)
	_compact_summary.mouse_filter = Control.MOUSE_FILTER_IGNORE
	cv.add_child(_compact_summary)

	_targeting_card = Control.new()
	_targeting_card.name = "TargetingCard"
	_targeting_card.visible = false
	_targeting_card.set_anchors_preset(PRESET_BOTTOM_WIDE)
	_targeting_card.offset_left = 12
	_targeting_card.offset_right = -12
	_targeting_card.offset_top = -Margins.COMPACT_BOTTOM_CLEARANCE - 150
	_targeting_card.offset_bottom = -Margins.COMPACT_BOTTOM_CLEARANCE
	_targeting_card.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_targeting_card)

	var tbg := TextureRect.new()
	tbg.texture = load(Margins.TEX_CARD)
	tbg.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	tbg.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	tbg.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	tbg.set_anchors_preset(PRESET_FULL_RECT)
	tbg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_targeting_card.add_child(tbg)

	var tm := MarginContainer.new()
	tm.set_anchors_preset(PRESET_FULL_RECT)
	tm.add_theme_constant_override("margin_left", 56)
	tm.add_theme_constant_override("margin_right", 24)
	tm.add_theme_constant_override("margin_top", 18)
	tm.add_theme_constant_override("margin_bottom", 18)
	_targeting_card.add_child(tm)
	var tv := VBoxContainer.new()
	tm.add_child(tv)
	_targeting_lbl = Label.new()
	_targeting_lbl.add_theme_font_size_override("font_size", Margins.scaled_font(Margins.HEADING_FONT))
	_targeting_lbl.add_theme_color_override("font_color", Margins.TEXT_ACCENT)
	_targeting_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	tv.add_child(_targeting_lbl)
	_targeting_guide = Label.new()
	_targeting_guide.add_theme_font_size_override("font_size", Margins.scaled_font(Margins.BODY_FONT))
	_targeting_guide.add_theme_color_override("font_color", Margins.TEXT_INK)
	_targeting_guide.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	tv.add_child(_targeting_guide)
	var cancel := Button.new()
	cancel.text = "Cancel targeting"
	cancel.focus_mode = Control.FOCUS_NONE
	cancel.custom_minimum_size = Vector2(0, Margins.TOUCH_MIN)
	cancel.pressed.connect(_on_cancel_targeting)
	_style_ink_button(cancel)
	tv.add_child(cancel)

	_open_root = Control.new()
	_open_root.name = "OpenBook"
	_open_root.visible = false
	_open_root.mouse_filter = Control.MOUSE_FILTER_STOP
	_open_root.clip_contents = true

	_art = TextureRect.new()
	_art.name = "BookArt"
	_art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_art.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_art.set_anchors_preset(PRESET_FULL_RECT)
	_art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_open_root.add_child(_art)

	_debug_layer = Control.new()
	_debug_layer.name = "LayoutDebug"
	_debug_layer.set_anchors_preset(PRESET_FULL_RECT)
	_debug_layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_debug_layer.visible = false
	_open_root.add_child(_debug_layer)

	var left_pack := _make_page_viewport("LeftPage")
	_content_left = left_pack["slot"]
	_scroll_left = left_pack["scroll"]
	_left_box = left_pack["box"]
	var right_pack := _make_page_viewport("RightPage")
	_content_right = right_pack["slot"]
	_scroll_right = right_pack["scroll"]
	_right_box = right_pack["box"]
	var single_pack := _make_page_viewport("SinglePage")
	_content_single = single_pack["slot"]
	_scroll_single = single_pack["scroll"]
	_single_box = single_pack["box"]
	_open_root.add_child(_content_left)
	_open_root.add_child(_content_right)
	_open_root.add_child(_content_single)

	# Close lives inside parchment via page chrome — keep a handle for tests.
	_panel_close = Button.new()
	_panel_close.name = "CloseBook"
	_panel_close.visible = false
	_panel_close.focus_mode = Control.FOCUS_NONE
	_open_root.add_child(_panel_close)

	add_child(_open_root)

	_confirm_panel = PanelContainer.new()
	_confirm_panel.visible = false
	_confirm_panel.set_anchors_preset(PRESET_CENTER)
	_confirm_panel.offset_left = -180
	_confirm_panel.offset_right = 180
	_confirm_panel.offset_top = -120
	_confirm_panel.offset_bottom = 120
	_confirm_panel.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_confirm_panel)


## Hard parchment viewport: clip + scroll. Content cannot paint outside the slot.
func _make_page_viewport(slot_name: String) -> Dictionary:
	var slot := Control.new()
	slot.name = slot_name
	slot.visible = false
	slot.mouse_filter = Control.MOUSE_FILTER_STOP
	slot.clip_contents = true

	var scroll := ScrollContainer.new()
	scroll.name = "PageScroll"
	scroll.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	scroll.mouse_filter = Control.MOUSE_FILTER_STOP
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	slot.add_child(scroll)

	var margin := MarginContainer.new()
	margin.name = "InnerPad"
	margin.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	margin.mouse_filter = Control.MOUSE_FILTER_STOP
	scroll.add_child(margin)

	var box := VBoxContainer.new()
	box.name = "PageBox"
	box.add_theme_constant_override("separation", 6)
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	margin.add_child(box)
	return {"slot": slot, "scroll": scroll, "box": box, "margin": margin}


func _process(_delta: float) -> void:
	if model != null:
		model.tick_timeout()


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED:
		_layout_art_slots()


func _unhandled_input(event: InputEvent) -> void:
	if model == null:
		return
	var cancel := false
	if event.is_action_pressed("ui_cancel"):
		cancel = true
	elif event is InputEventKey and event.pressed and not event.echo \
			and (event.keycode == KEY_ESCAPE or event.physical_keycode == KEY_ESCAPE):
		cancel = true
	if not cancel:
		return
	if model.host_mode == ModelScript.HostMode.OPEN \
			or model.host_mode == ModelScript.HostMode.TARGETING \
			or not model.confirm_pending.is_empty():
		if not model.confirm_pending.is_empty():
			model.confirm_no()
		else:
			_on_close_pressed()
		get_viewport().set_input_as_handled()


func _on_model_changed() -> void:
	if model == null:
		return
	_refresh_visibility()
	_refresh_compact()
	_refresh_targeting()
	_refresh_open()
	_refresh_confirm()
	emit_signal("world_target_needed", model.host_mode == ModelScript.HostMode.TARGETING)
	var blocking := is_blocking_world()
	if blocking != _was_blocking:
		_was_blocking = blocking
		emit_signal("overlay_blocking_changed", blocking)


func _refresh_visibility() -> void:
	var mode: int = model.host_mode
	_compact.visible = mode == ModelScript.HostMode.COMPACT
	_open_root.visible = mode == ModelScript.HostMode.OPEN
	_blocker.visible = mode == ModelScript.HostMode.OPEN or not model.confirm_pending.is_empty()
	_targeting_card.visible = mode == ModelScript.HostMode.TARGETING
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	if mode == ModelScript.HostMode.OPEN or not model.confirm_pending.is_empty():
		z_index = 80
		move_to_front()
	elif mode == ModelScript.HostMode.TARGETING:
		z_index = 40
		move_to_front()
	else:
		z_index = 0


func _refresh_compact() -> void:
	var bits: PackedStringArray = PackedStringArray()
	bits.append(model.conn_label())
	if model.paused_badge:
		bits.append("PAUSED")
	if model.result_kind == ModelScript.ResultKind.PENDING:
		bits.append("…")
	elif model.result_label() != "":
		bits.append(model.result_label())
	_compact_summary.text = " · ".join(bits)
	if model.counters_line != "":
		_compact_summary.text += "\n" + model.counters_line
	_compact_btn.disabled = model.conn_state == ModelScript.ConnState.LOADING


func _refresh_targeting() -> void:
	if model.targeting.is_empty():
		return
	_targeting_lbl.text = "Target: %s" % str(model.targeting.get("label", "?"))
	_targeting_guide.text = str(model.targeting.get("guidance", ""))


func _refresh_confirm() -> void:
	for c in _confirm_panel.get_children():
		c.queue_free()
	if model.confirm_pending.is_empty():
		_confirm_panel.visible = false
		return
	_confirm_panel.visible = true
	_confirm_panel.move_to_front()
	var v := VBoxContainer.new()
	_confirm_panel.add_child(v)
	var t := Label.new()
	t.text = str(model.confirm_pending.get("label", "Confirm"))
	t.add_theme_font_size_override("font_size", Margins.scaled_font(Margins.HEADING_FONT))
	t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(t)
	var b := Label.new()
	b.text = str(model.confirm_pending.get("body", ""))
	b.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(b)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", Margins.TOUCH_GAP)
	v.add_child(row)
	var no := Button.new()
	no.text = "Cancel"
	no.custom_minimum_size = Vector2(120, Margins.TOUCH_MIN)
	no.focus_mode = Control.FOCUS_NONE
	no.pressed.connect(func(): model.confirm_no())
	row.add_child(no)
	var yes := Button.new()
	yes.text = "Confirm"
	yes.custom_minimum_size = Vector2(120, Margins.TOUCH_MIN)
	yes.focus_mode = Control.FOCUS_NONE
	yes.pressed.connect(func(): model.confirm_yes())
	row.add_child(yes)


func _refresh_open() -> void:
	if model.host_mode != ModelScript.HostMode.OPEN:
		return
	_layout_art_slots()
	_rebuild_page_content()


func _layout_art_slots() -> void:
	if _art == null or _open_root == null:
		return
	var vp := get_viewport_rect().size
	if vp.x < 8.0 or vp.y < 8.0:
		return

	# Candidate panel sizes for both art modes; choose spread only if parchment stays readable.
	var book_tex: Texture2D = load(Margins.TEX_BOOK)
	var page_tex: Texture2D = load(Margins.TEX_PAGE)
	var book_size := Vector2(1248, 832)
	var page_size := Vector2(1248, 832)
	if book_tex != null:
		book_size = Vector2(book_tex.get_width(), book_tex.get_height())
	if page_tex != null:
		page_size = Vector2(page_tex.get_width(), page_tex.get_height())

	var land_panel := _fit_panel(
		vp,
		book_size,
		Margins.OPEN_MAX_WIDTH_LANDSCAPE,
		Margins.OPEN_MAX_HEIGHT_LANDSCAPE,
		Margins.OPEN_VIEWPORT_FRAC_W_LANDSCAPE,
		Margins.OPEN_VIEWPORT_FRAC_H_LANDSCAPE
	)
	var port_panel := _fit_panel(
		vp,
		page_size,
		Margins.OPEN_MAX_WIDTH_PORTRAIT,
		Margins.OPEN_MAX_HEIGHT_PORTRAIT,
		Margins.OPEN_VIEWPORT_FRAC_W_PORTRAIT,
		Margins.OPEN_VIEWPORT_FRAC_H_PORTRAIT
	)
	var left_safe := Margins.safe_page_pixel_size(land_panel, book_size, Margins.BOOK_LEFT)
	var right_safe := Margins.safe_page_pixel_size(land_panel, book_size, Margins.BOOK_RIGHT)
	_use_spread = left_safe.x >= Margins.MIN_SAFE_PAGE_WIDTH_PX \
		and right_safe.x >= Margins.MIN_SAFE_PAGE_WIDTH_PX \
		and left_safe.y >= Margins.MIN_SAFE_PAGE_HEIGHT_PX \
		and right_safe.y >= Margins.MIN_SAFE_PAGE_HEIGHT_PX \
		and vp.x >= vp.y  # prefer single-page in tall portrait even if wide enough

	# Final panel must still keep readable parchment; otherwise fall back to single-page.
	if _use_spread:
		var check_left := Margins.safe_page_pixel_size(land_panel, book_size, Margins.BOOK_LEFT)
		var check_right := Margins.safe_page_pixel_size(land_panel, book_size, Margins.BOOK_RIGHT)
		if check_left.x < Margins.MIN_SAFE_PAGE_WIDTH_PX \
				or check_right.x < Margins.MIN_SAFE_PAGE_WIDTH_PX \
				or check_left.y < Margins.MIN_SAFE_PAGE_HEIGHT_PX \
				or check_right.y < Margins.MIN_SAFE_PAGE_HEIGHT_PX:
			_use_spread = false

	var tex: Texture2D = book_tex if _use_spread else page_tex
	_art.texture = tex
	_tex_size = book_size if _use_spread else page_size
	_panel_size = land_panel if _use_spread else port_panel

	var fit := minf(_panel_size.x / _tex_size.x, _panel_size.y / _tex_size.y)
	_drawn_size = _tex_size * fit
	# Keep open_root == drawn art bounds (no empty letterbox) so frac slots match pixels.
	_panel_size = _drawn_size
	_drawn_origin = Vector2.ZERO

	_open_root.set_anchors_preset(Control.PRESET_TOP_LEFT)
	_open_root.size = _panel_size
	_open_root.position = (vp - _panel_size) * 0.5
	_open_root.pivot_offset = _panel_size * 0.5

	_art.set_anchors_preset(PRESET_FULL_RECT)
	_art.offset_left = 0
	_art.offset_right = 0
	_art.offset_top = 0
	_art.offset_bottom = 0
	_art.stretch_mode = TextureRect.STRETCH_SCALE  # panel already aspect-fit; fill exactly

	var pad := Margins.inner_pad_px(minf(_drawn_size.x, _drawn_size.y))
	if _use_spread:
		_place_slot(_content_left, Margins.BOOK_LEFT, pad)
		_place_slot(_content_right, Margins.BOOK_RIGHT, pad)
		_content_left.visible = true
		_content_right.visible = true
		_content_single.visible = false
	else:
		_place_slot(_content_single, Margins.PAGE_CONTENT, pad)
		_content_left.visible = false
		_content_right.visible = false
		_content_single.visible = true

	_refresh_layout_debug()


func _fit_panel(
	vp: Vector2,
	tex_size: Vector2,
	max_w: float,
	max_h: float,
	frac_w: float,
	frac_h: float
) -> Vector2:
	var avail := Vector2(minf(max_w, vp.x * frac_w), minf(max_h, vp.y * frac_h))
	var fit := minf(avail.x / tex_size.x, avail.y / tex_size.y)
	return tex_size * fit


func _place_slot(slot: Control, frac: Rect2, pad: float) -> void:
	var r := Margins.slot_rect_in_panel(frac, _panel_size, _tex_size)
	slot.set_anchors_preset(Control.PRESET_TOP_LEFT)
	slot.anchor_right = 0.0
	slot.anchor_bottom = 0.0
	slot.position = r.position
	slot.size = r.size
	slot.clip_contents = true
	var pi := int(round(pad))
	for child in slot.get_children():
		if child is ScrollContainer:
			var scroll := child as ScrollContainer
			scroll.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
			scroll.clip_contents = true
			scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
			for m in child.get_children():
				if m is MarginContainer:
					m.add_theme_constant_override("margin_left", pi)
					m.add_theme_constant_override("margin_right", pi)
					m.add_theme_constant_override("margin_top", pi)
					m.add_theme_constant_override("margin_bottom", pi)
					# Lock scroll content to viewport width so labels wrap inside parchment.
					var view_w := maxf(32.0, r.size.x)
					m.custom_minimum_size = Vector2(view_w, 0.0)
					m.size_flags_horizontal = Control.SIZE_FILL


func _rebuild_page_content() -> void:
	_clear_box(_left_box)
	_clear_box(_right_box)
	_clear_box(_single_box)
	var page: Dictionary = model.current_page()
	var page_id := str(page.get("id", ""))
	var animate := page_id != _last_built_page and _last_built_page != ""
	_last_built_page = page_id
	var lean := _is_lean_page(page)

	if _use_spread:
		if lean:
			_fill_lean_nav(_left_box, page)
			_fill_lean_actions(_right_box, page)
		else:
			_fill_status_column(_left_box)
			_fill_page_column(_right_box, page)
	else:
		if lean:
			_fill_lean_nav(_single_box, page)
			_fill_lean_actions(_single_box, page)
		else:
			_fill_status_column(_single_box)
			_fill_page_column(_single_box, page)

	_constrain_page_box_widths()
	if animate and not Margins.reduced_motion():
		_play_page_transition()


func _constrain_page_box_widths() -> void:
	## Keep page VBox width ≤ parchment viewport so autowrap works and nothing grows wider.
	for pair in [
		[_scroll_left, _left_box, _content_left],
		[_scroll_right, _right_box, _content_right],
		[_scroll_single, _single_box, _content_single],
	]:
		var scroll: ScrollContainer = pair[0]
		var box: VBoxContainer = pair[1]
		var slot: Control = pair[2]
		if scroll == null or box == null or slot == null or not slot.visible:
			continue
		var pad := 0
		for m in scroll.get_children():
			if m is MarginContainer:
				pad = int(m.get_theme_constant("margin_left")) \
					+ int(m.get_theme_constant("margin_right"))
				m.custom_minimum_size = Vector2(maxf(32.0, slot.size.x), 0.0)
		var inner_w := maxf(24.0, slot.size.x - float(pad) - 4.0)
		box.custom_minimum_size = Vector2(inner_w, 0.0)
		box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		_force_wrap_width(box, inner_w)


func _force_wrap_width(node: Control, width: float) -> void:
	if node == null or width < 8.0:
		return
	if node is Label:
		var lbl := node as Label
		lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		lbl.custom_minimum_size = Vector2(width, lbl.custom_minimum_size.y)
	elif node is RichTextLabel:
		var rtl := node as RichTextLabel
		rtl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		rtl.fit_content = true
		rtl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		rtl.custom_minimum_size = Vector2(width, rtl.custom_minimum_size.y)
	elif node is Button or node is OptionButton:
		node.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		# Keep touch height; only cap width.
		var h: float = node.custom_minimum_size.y
		if h < Margins.TOUCH_MIN:
			h = Margins.TOUCH_MIN
		node.custom_minimum_size = Vector2(0.0, h)
	for child in node.get_children():
		if child is Control:
			_force_wrap_width(child as Control, width)


func _is_lean_page(page: Dictionary) -> bool:
	var id := str(page.get("id", ""))
	if id == "spells" or id == "hazard":
		return true
	return str(page.get("presentation", "")) == "battle_spells"


func _fill_lean_nav(box: VBoxContainer, _page: Dictionary) -> void:
	_add_heading(box, model.title)
	_add_caption(box, "Select a spell, then a unit in the world.")
	_add_page_nav(box)
	_add_close_row(box)


func _fill_lean_actions(box: VBoxContainer, page: Dictionary) -> void:
	_add_heading(box, str(page.get("title", "Spells")))
	var hint := str(page.get("body", ""))
	if hint != "":
		_add_caption(box, hint)
	_actions = VBoxContainer.new()
	_actions.add_theme_constant_override("separation", Margins.TOUCH_GAP)
	_actions.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_child(_actions)
	for act in page.get("actions", []):
		_add_action_button(_actions, act)


func _fill_status_column(box: VBoxContainer) -> void:
	## Left parchment (or top of single page): title, essential status, page nav, Close.
	_add_heading(box, model.title)
	_add_caption(box, model.conn_label() + (" · Game Time frozen" if model.paused_badge else ""))
	if model.error_reason != "":
		_add_body(box, model.error_reason, Margins.TEXT_DANGER)
	_add_body(box, model.status_line, Margins.TEXT_INK)
	_add_body(box, model.counters_line, Margins.TEXT_MUTED)
	_add_body(box, model.prompt_line, Margins.TEXT_ACCENT)
	_result_lbl = Label.new()
	_result_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_result_lbl.add_theme_font_size_override("font_size", Margins.scaled_font(Margins.RESULT_FONT))
	_paint_result(_result_lbl)
	box.add_child(_result_lbl)
	_add_page_nav(box)
	_add_close_row(box)


## Width-safe navigation: prev/next + OptionButton. Never a nonwrapping HBox of all tabs.
func _add_page_nav(box: VBoxContainer) -> void:
	var wrap := VBoxContainer.new()
	wrap.add_theme_constant_override("separation", 4)
	wrap.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_child(wrap)
	_page_tabs = wrap

	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 4)
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	wrap.add_child(row)

	var prev := Button.new()
	prev.text = "◀"
	prev.focus_mode = Control.FOCUS_NONE
	prev.custom_minimum_size = Vector2(Margins.TOUCH_MIN, Margins.TOUCH_MIN)
	prev.disabled = model.page_index <= 0
	prev.pressed.connect(func(): _on_tab(model.page_index - 1))
	_style_ink_button(prev)
	row.add_child(prev)

	var selector := OptionButton.new()
	selector.focus_mode = Control.FOCUS_NONE
	selector.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	selector.custom_minimum_size = Vector2(0, Margins.TOUCH_MIN)
	selector.clip_text = true
	for i in model.pages.size():
		var p: Dictionary = model.pages[i]
		selector.add_item(str(p.get("title", p.get("id", "?"))))
	selector.select(model.page_index)
	selector.item_selected.connect(_on_tab)
	_style_ink_button(selector)
	row.add_child(selector)

	var next := Button.new()
	next.text = "▶"
	next.focus_mode = Control.FOCUS_NONE
	next.custom_minimum_size = Vector2(Margins.TOUCH_MIN, Margins.TOUCH_MIN)
	next.disabled = model.page_index >= model.pages.size() - 1
	next.pressed.connect(func(): _on_tab(model.page_index + 1))
	_style_ink_button(next)
	row.add_child(next)

	var page_lbl := Label.new()
	page_lbl.text = "Page %d / %d" % [model.page_index + 1, max(1, model.pages.size())]
	page_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	page_lbl.add_theme_font_size_override("font_size", Margins.scaled_font(Margins.CAPTION_FONT))
	page_lbl.add_theme_color_override("font_color", Margins.TEXT_MUTED)
	wrap.add_child(page_lbl)


func _add_close_row(box: VBoxContainer) -> void:
	_nav = HBoxContainer.new()
	_nav.add_theme_constant_override("separation", Margins.TOUCH_GAP)
	_nav.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_child(_nav)
	var close_btn := Button.new()
	close_btn.text = "Close"
	close_btn.focus_mode = Control.FOCUS_NONE
	close_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	close_btn.custom_minimum_size = Vector2(0, Margins.TOUCH_MIN)
	close_btn.pressed.connect(_on_close_pressed)
	_style_ink_button(close_btn)
	_nav.add_child(close_btn)
	# Keep panel_close handle pointing at the live in-parchment control for tests.
	_panel_close = close_btn
	var menu_btn := Button.new()
	menu_btn.text = "Menu"
	menu_btn.focus_mode = Control.FOCUS_NONE
	menu_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	menu_btn.custom_minimum_size = Vector2(0, Margins.TOUCH_MIN)
	menu_btn.pressed.connect(_on_exit_menu_pressed)
	_style_ink_button(menu_btn)
	_nav.add_child(menu_btn)


func _fill_page_column(box: VBoxContainer, page: Dictionary) -> void:
	## Right parchment (or lower single-page): selected page body + actions.
	## Already inside a ScrollContainer — do not nest another scroll.
	_add_heading(box, str(page.get("title", "")))
	var kind := str(page.get("kind", "info"))
	if kind == "log":
		_log = RichTextLabel.new()
		_log.bbcode_enabled = false
		_log.fit_content = true
		_log.scroll_active = false
		_log.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		_log.custom_minimum_size = Vector2(0, 120)
		_log.add_theme_font_size_override("normal_font_size", Margins.scaled_font(Margins.CAPTION_FONT))
		_log.add_theme_color_override("default_color", Margins.TEXT_INK)
		_log.selection_enabled = true
		for line in model.log_lines:
			_log.append_text(str(line) + "\n")
		box.add_child(_log)
		return

	var body := str(page.get("body", ""))
	if body != "":
		# Plain ink on parchment — no opaque panel that reads as a generic UI card.
		_add_body(box, body, Margins.TEXT_INK)

	_actions = VBoxContainer.new()
	_actions.add_theme_constant_override("separation", Margins.TOUCH_GAP)
	_actions.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_child(_actions)
	for act in page.get("actions", []):
		_add_action_button(_actions, act)


func _add_action_button(parent: VBoxContainer, act: Dictionary) -> void:
	var id := str(act.get("id", ""))
	var label := str(act.get("label", id))
	var b := Button.new()
	b.text = label
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(0, Margins.TOUCH_MIN)
	b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	b.mouse_filter = Control.MOUSE_FILTER_STOP
	b.clip_text = true
	b.disabled = bool(act.get("disabled", false)) or model.pending_token != "" \
		or model.conn_state == ModelScript.ConnState.DISCONNECTED
	if str(act.get("hint", "")) != "":
		b.tooltip_text = str(act.get("hint", ""))
	_style_ink_button(b)
	if bool(act.get("destructive", false)):
		b.add_theme_color_override("font_color", Margins.TEXT_DANGER)
	var payload: Dictionary = act.get("payload", {})
	var opts: Dictionary = {
		"needs_confirm": bool(act.get("needs_confirm", false)),
		"confirm_label": str(act.get("confirm_label", label)),
		"confirm_body": str(act.get("confirm_body", "This changes game state.")),
		"needs_target": bool(act.get("needs_target", false)),
		"target_label": str(act.get("target_label", label)),
		"target_guidance": str(act.get("target_guidance", "Select a target in the world.")),
	}
	b.pressed.connect(_on_action_pressed.bind(id, payload, opts))
	parent.add_child(b)
	if str(act.get("disabled_reason", "")) != "" and b.disabled:
		var h := Label.new()
		h.text = str(act.get("disabled_reason", ""))
		h.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		h.add_theme_font_size_override("font_size", Margins.scaled_font(Margins.CAPTION_FONT))
		h.add_theme_color_override("font_color", Margins.TEXT_MUTED)
		parent.add_child(h)


func _paint_result(lbl: Label) -> void:
	var prefix: String = str(model.result_label())
	if prefix == "":
		lbl.text = "Result: —"
		lbl.add_theme_color_override("font_color", Margins.TEXT_MUTED)
		return
	lbl.text = "%s — %s" % [prefix, model.result_text]
	match model.result_kind:
		ModelScript.ResultKind.SUCCESS:
			lbl.add_theme_color_override("font_color", Margins.TEXT_OK)
		ModelScript.ResultKind.REJECTED, ModelScript.ResultKind.TIMEOUT, ModelScript.ResultKind.DISCONNECTED:
			lbl.add_theme_color_override("font_color", Margins.TEXT_DANGER)
		ModelScript.ResultKind.PENDING:
			lbl.add_theme_color_override("font_color", Margins.TEXT_PENDING)
		_:
			lbl.add_theme_color_override("font_color", Margins.TEXT_MUTED)


func _add_heading(box: VBoxContainer, text: String) -> void:
	var l := Label.new()
	l.text = text
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.add_theme_font_size_override("font_size", Margins.scaled_font(Margins.HEADING_FONT))
	l.add_theme_color_override("font_color", Margins.TEXT_ACCENT)
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_child(l)


func _add_caption(box: VBoxContainer, text: String) -> void:
	var l := Label.new()
	l.text = text
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.add_theme_font_size_override("font_size", Margins.scaled_font(Margins.CAPTION_FONT))
	l.add_theme_color_override("font_color", Margins.TEXT_MUTED)
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_child(l)


func _add_body(box: VBoxContainer, text: String, color: Color) -> void:
	if text == "":
		return
	var l := Label.new()
	l.text = text
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.add_theme_font_size_override("font_size", Margins.scaled_font(Margins.BODY_FONT))
	l.add_theme_color_override("font_color", color)
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_child(l)


func _clear_box(box: VBoxContainer) -> void:
	if box == null:
		return
	for c in box.get_children():
		c.queue_free()


func _style_ink_button(b: BaseButton) -> void:
	b.add_theme_font_size_override("font_size", Margins.scaled_font(Margins.BODY_FONT))
	b.add_theme_color_override("font_color", Margins.TEXT_INK)
	b.add_theme_color_override("font_disabled_color", Margins.TEXT_MUTED)
	b.add_theme_color_override("font_pressed_color", Margins.TEXT_ACCENT)


func _play_page_transition() -> void:
	if _tween != null and _tween.is_valid():
		_tween.kill()
	var target: Control = _content_single if not _use_spread else _content_right
	target.modulate.a = 0.35
	_tween = create_tween()
	_tween.tween_property(target, "modulate:a", 1.0, Margins.DUR_PAGE)


func _refresh_layout_debug() -> void:
	for c in _debug_layer.get_children():
		c.queue_free()
	_debug_layer.visible = Margins.layout_debug_enabled() and _open_root.visible
	if not _debug_layer.visible:
		return
	# Drawn texture bounds
	_debug_layer.add_child(_debug_rect(_drawn_origin, _drawn_size, Color(0.2, 0.8, 1.0, 0.85), "drawn"))
	if _use_spread:
		var lr := Margins.slot_rect_in_panel(Margins.BOOK_LEFT, _panel_size, _tex_size)
		var rr := Margins.slot_rect_in_panel(Margins.BOOK_RIGHT, _panel_size, _tex_size)
		_debug_layer.add_child(_debug_rect(lr.position, lr.size, Color(0.2, 1.0, 0.3, 0.9), "left-safe"))
		_debug_layer.add_child(_debug_rect(rr.position, rr.size, Color(1.0, 0.85, 0.2, 0.9), "right-safe"))
	else:
		var sr := Margins.slot_rect_in_panel(Margins.PAGE_CONTENT, _panel_size, _tex_size)
		_debug_layer.add_child(_debug_rect(sr.position, sr.size, Color(1.0, 0.4, 0.9, 0.9), "page-safe"))


func _debug_rect(pos: Vector2, size: Vector2, color: Color, label: String) -> Control:
	var root := Control.new()
	root.position = pos
	root.size = size
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var border := ColorRect.new()
	border.color = Color(color.r, color.g, color.b, 0.12)
	border.set_anchors_preset(PRESET_FULL_RECT)
	border.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(border)
	# Four edge lines
	for edge in [
		[Vector2(0, 0), Vector2(size.x, 2)],
		[Vector2(0, size.y - 2), Vector2(size.x, 2)],
		[Vector2(0, 0), Vector2(2, size.y)],
		[Vector2(size.x - 2, 0), Vector2(2, size.y)],
	]:
		var line := ColorRect.new()
		line.color = color
		line.position = edge[0]
		line.size = edge[1]
		line.mouse_filter = Control.MOUSE_FILTER_IGNORE
		root.add_child(line)
	var lbl := Label.new()
	lbl.text = label
	lbl.position = Vector2(4, 4)
	lbl.add_theme_font_size_override("font_size", 12)
	lbl.add_theme_color_override("font_color", color)
	lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(lbl)
	return root


func _on_open_pressed() -> void:
	if _duplicate_press("open"):
		return
	if model == null:
		return
	if model.host_mode == ModelScript.HostMode.OPEN:
		_on_close_pressed()
		return
	if Margins.reduced_motion():
		model.open_book()
		return
	model.open_book()
	_open_root.modulate.a = 0.0
	_open_root.scale = Vector2(0.96, 0.96)
	_open_root.pivot_offset = _open_root.size * 0.5
	if _tween != null and _tween.is_valid():
		_tween.kill()
	_tween = create_tween()
	_tween.set_parallel(true)
	_tween.tween_property(_open_root, "modulate:a", 1.0, Margins.DUR_OPEN)
	_tween.tween_property(_open_root, "scale", Vector2.ONE, Margins.DUR_OPEN)


func _on_close_pressed() -> void:
	if _duplicate_press("close"):
		return
	if model == null:
		return
	if Margins.reduced_motion():
		model.close_book()
		return
	if model.host_mode != ModelScript.HostMode.OPEN:
		model.close_book()
		return
	if _tween != null and _tween.is_valid():
		_tween.kill()
	_tween = create_tween()
	_tween.tween_property(_open_root, "modulate:a", 0.0, Margins.DUR_CLOSE)
	_tween.tween_callback(func():
		if model:
			model.close_book()
		_open_root.modulate.a = 1.0
	)


func _on_exit_menu_pressed() -> void:
	if _duplicate_press("exit"):
		return
	if model:
		model.request_exit_menu()


func _on_cancel_targeting() -> void:
	if model:
		model.cancel_targeting()


func _on_tab(index: int) -> void:
	if model == null:
		return
	if index < 0 or index >= model.pages.size():
		return
	model.goto_page(index)


func _on_action_pressed(action_id: String, payload: Dictionary, opts: Dictionary) -> void:
	if _duplicate_press("action:%s" % action_id):
		return
	if model == null:
		return
	model.request_action(action_id, payload, opts)


func _on_blocker_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
			accept_event()
			_on_close_pressed()
			return
		accept_event()
	elif event is InputEventScreenTouch:
		var st := event as InputEventScreenTouch
		if st.pressed:
			accept_event()
			_on_close_pressed()
			return
		accept_event()


func _duplicate_press(key: String = "") -> bool:
	var now := Time.get_ticks_msec()
	if key != "" and key == _press_guard_key and now < _press_guard_msec:
		return true
	_press_guard_key = key
	_press_guard_msec = now + 120
	return false


func is_blocking_world() -> bool:
	if model == null:
		return false
	return model.host_mode == ModelScript.HostMode.OPEN or not model.confirm_pending.is_empty()


func is_targeting() -> bool:
	return model != null and model.host_mode == ModelScript.HostMode.TARGETING


func accepts_world_target() -> bool:
	return is_targeting() and model != null and not model.world_input_blocked_for_select()


func open_panel_rect() -> Rect2:
	if _open_root == null or not _open_root.visible:
		return Rect2()
	return _open_root.get_global_rect()


func compact_open_button() -> Button:
	return _compact_btn


func panel_close_button() -> Button:
	return _panel_close


func uses_spread() -> bool:
	return _use_spread


## Geometry for automated layout assertions (global coordinates).
func layout_geometry() -> Dictionary:
	var out := {
		"use_spread": _use_spread,
		"panel": open_panel_rect(),
		"drawn_local": Rect2(_drawn_origin, _drawn_size),
		"safe_fracs": {
			"left": Margins.BOOK_LEFT,
			"right": Margins.BOOK_RIGHT,
			"page": Margins.PAGE_CONTENT,
		},
		"viewports": [],
	}
	if not _open_root.visible:
		return out
	var origin := _open_root.global_position
	out["drawn_global"] = Rect2(origin + _drawn_origin, _drawn_size)
	if _use_spread:
		out["safe_left_local"] = Margins.slot_rect_in_panel(Margins.BOOK_LEFT, _panel_size, _tex_size)
		out["safe_right_local"] = Margins.slot_rect_in_panel(Margins.BOOK_RIGHT, _panel_size, _tex_size)
		out["safe_left_global"] = Rect2(origin + out["safe_left_local"].position, out["safe_left_local"].size)
		out["safe_right_global"] = Rect2(origin + out["safe_right_local"].position, out["safe_right_local"].size)
	else:
		out["safe_page_local"] = Margins.slot_rect_in_panel(Margins.PAGE_CONTENT, _panel_size, _tex_size)
		out["safe_page_global"] = Rect2(origin + out["safe_page_local"].position, out["safe_page_local"].size)
	for slot in [_content_left, _content_right, _content_single]:
		if slot != null and slot.visible:
			out["viewports"].append({
				"name": slot.name,
				"global": slot.get_global_rect(),
				"clip": slot.clip_contents,
			})
	return out


## Returns human-readable violation strings; empty means layout is inside safe rects.
func layout_violations(epsilon: float = 1.5) -> Array:
	var geo := layout_geometry()
	var violations: Array = []
	if not bool(geo.get("use_spread", false)) and not geo.has("safe_page_global"):
		return ["book not open / no geometry"]
	var safes: Array = []
	if bool(geo.get("use_spread", false)):
		safes.append(["LeftPage", geo.get("safe_left_global")])
		safes.append(["RightPage", geo.get("safe_right_global")])
	else:
		safes.append(["SinglePage", geo.get("safe_page_global")])
	for vp in geo.get("viewports", []):
		var name := str(vp.get("name", ""))
		var rect: Rect2 = vp.get("global")
		var matched = null
		for pair in safes:
			if str(pair[0]) == name or (name == "SinglePage" and str(pair[0]) == "SinglePage"):
				matched = pair[1]
				break
		if matched == null:
			# Map LeftPage/RightPage names
			for pair in safes:
				if name.begins_with(str(pair[0]).substr(0, 4)):
					matched = pair[1]
					break
		if matched == null:
			continue
		var safe: Rect2 = matched
		if rect.position.x < safe.position.x - epsilon \
				or rect.position.y < safe.position.y - epsilon \
				or rect.end.x > safe.end.x + epsilon \
				or rect.end.y > safe.end.y + epsilon:
			violations.append(
				"%s viewport %s outside safe %s" % [name, str(rect), str(safe)]
			)
		if not bool(vp.get("clip", false)):
			violations.append("%s missing clip_contents" % name)
	return violations
