extends Control
class_name SpellbookHost

## Reusable animated spellbook presentation. Binds to SpellbookModel only.

const Margins = preload("res://client/ui/spellbook/spellbook_margins.gd")
const ModelScript = preload("res://client/ui/spellbook/spellbook_model.gd")

signal action_requested(action_id: String, payload: Dictionary, token: String)
signal targeting_cancelled(action_id: String)
signal close_requested
signal exit_menu_requested
signal classic_hud_toggled(enabled: bool)
signal world_target_needed(active: bool)

var model = null

var _blocker: ColorRect
var _compact: Control
var _compact_btn: Button
var _compact_summary: Label
var _open_root: Control
var _art: TextureRect
var _content_left: MarginContainer
var _content_right: MarginContainer
var _content_single: MarginContainer
var _left_box: VBoxContainer
var _right_box: VBoxContainer
var _single_box: VBoxContainer
var _header: Label
var _result_lbl: Label
var _body: RichTextLabel
var _actions: VBoxContainer
var _nav: HBoxContainer
var _page_tabs: HBoxContainer
var _log: RichTextLabel
var _confirm_panel: PanelContainer
var _targeting_card: Control
var _targeting_lbl: Label
var _targeting_guide: Label
var _tween: Tween
var _use_spread := false
var _press_guard_msec := 0
var _last_built_page := ""
var _built := false


func _ready() -> void:
	set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ensure_built()
	set_process(true)


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
	_blocker.color = Color(0, 0, 0, 0.35)
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

	# Build open-book art and page slots BEFORE add_child(_open_root) so the first
	# RESIZED notification can lay out against a populated tree (avoids empty-slot race).
	_open_root = Control.new()
	_open_root.name = "OpenBook"
	_open_root.visible = false
	_open_root.set_anchors_preset(PRESET_FULL_RECT)
	_open_root.mouse_filter = Control.MOUSE_FILTER_IGNORE

	_art = TextureRect.new()
	_art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_art.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_art.set_anchors_preset(PRESET_FULL_RECT)
	_art.offset_left = 8
	_art.offset_right = -8
	_art.offset_top = 24
	_art.offset_bottom = -24
	_art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_open_root.add_child(_art)

	_content_left = _make_content_slot()
	_content_right = _make_content_slot()
	_content_single = _make_content_slot()
	_open_root.add_child(_content_left)
	_open_root.add_child(_content_right)
	_open_root.add_child(_content_single)

	_left_box = VBoxContainer.new()
	_left_box.add_theme_constant_override("separation", 6)
	_content_left.add_child(_left_box)
	_right_box = VBoxContainer.new()
	_right_box.add_theme_constant_override("separation", 6)
	_content_right.add_child(_right_box)
	_single_box = VBoxContainer.new()
	_single_box.add_theme_constant_override("separation", 6)
	_content_single.add_child(_single_box)

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


func _make_content_slot() -> MarginContainer:
	var m := MarginContainer.new()
	m.visible = false
	m.mouse_filter = Control.MOUSE_FILTER_STOP
	m.add_theme_constant_override("margin_left", 8)
	m.add_theme_constant_override("margin_right", 8)
	m.add_theme_constant_override("margin_top", 8)
	m.add_theme_constant_override("margin_bottom", 8)
	return m


func _process(_delta: float) -> void:
	if model != null:
		model.tick_timeout()


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED:
		_layout_art_slots()


func _on_model_changed() -> void:
	if model == null:
		return
	_refresh_visibility()
	_refresh_compact()
	_refresh_targeting()
	_refresh_open()
	_refresh_confirm()
	emit_signal("world_target_needed", model.host_mode == ModelScript.HostMode.TARGETING)


func _refresh_visibility() -> void:
	var mode: int = model.host_mode
	_compact.visible = mode == ModelScript.HostMode.COMPACT
	_open_root.visible = mode == ModelScript.HostMode.OPEN
	_blocker.visible = mode == ModelScript.HostMode.OPEN or not model.confirm_pending.is_empty()
	_targeting_card.visible = mode == ModelScript.HostMode.TARGETING
	mouse_filter = Control.MOUSE_FILTER_IGNORE


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
	_use_spread = vp.x >= Margins.SPREAD_MIN_WIDTH and vp.x * 0.34 >= Margins.SPREAD_MIN_PAGE_WIDTH
	if _use_spread:
		_art.texture = load(Margins.TEX_BOOK)
		_place_slot(_content_left, Margins.BOOK_LEFT)
		_place_slot(_content_right, Margins.BOOK_RIGHT)
		_content_left.visible = true
		_content_right.visible = true
		_content_single.visible = false
	else:
		_art.texture = load(Margins.TEX_PAGE)
		_place_slot(_content_single, Margins.PAGE_CONTENT)
		_content_left.visible = false
		_content_right.visible = false
		_content_single.visible = true


func _place_slot(slot: MarginContainer, frac: Rect2) -> void:
	# Position relative to _art's drawn aspect-fit rectangle.
	var art_size := _art.size
	if art_size.x < 8 or art_size.y < 8:
		art_size = get_viewport_rect().size - Vector2(16, 48)
	var tex: Texture2D = _art.texture
	var tex_size := Vector2(1248, 832)
	if tex != null:
		tex_size = Vector2(tex.get_width(), tex.get_height())
	var scale := minf(art_size.x / tex_size.x, art_size.y / tex_size.y)
	var drawn := tex_size * scale
	var origin := _art.position + (art_size - drawn) * 0.5
	slot.set_anchors_preset(Control.PRESET_TOP_LEFT)
	slot.position = origin + Vector2(frac.position.x * drawn.x, frac.position.y * drawn.y)
	slot.size = Vector2(frac.size.x * drawn.x, frac.size.y * drawn.y)


func _rebuild_page_content() -> void:
	_clear_box(_left_box)
	_clear_box(_right_box)
	_clear_box(_single_box)
	var page: Dictionary = model.current_page()
	var page_id := str(page.get("id", ""))
	var animate := page_id != _last_built_page and _last_built_page != ""
	_last_built_page = page_id

	if _use_spread:
		_fill_status_column(_left_box)
		_fill_page_column(_right_box, page)
	else:
		_fill_status_column(_single_box)
		_fill_page_column(_single_box, page)

	if animate and not Margins.reduced_motion():
		_play_page_transition()


func _fill_status_column(box: VBoxContainer) -> void:
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

	_page_tabs = HBoxContainer.new()
	_page_tabs.add_theme_constant_override("separation", Margins.TOUCH_GAP)
	box.add_child(_page_tabs)
	for i in model.pages.size():
		var p: Dictionary = model.pages[i]
		var tab := Button.new()
		tab.text = str(p.get("title", p.get("id", "?")))
		tab.focus_mode = Control.FOCUS_NONE
		tab.toggle_mode = true
		tab.button_pressed = i == model.page_index
		tab.custom_minimum_size = Vector2(0, Margins.TOUCH_MIN)
		tab.pressed.connect(_on_tab.bind(i))
		_style_ink_button(tab)
		_page_tabs.add_child(tab)

	_nav = HBoxContainer.new()
	_nav.add_theme_constant_override("separation", Margins.TOUCH_GAP)
	box.add_child(_nav)
	var close_btn := Button.new()
	close_btn.text = "Close book"
	close_btn.focus_mode = Control.FOCUS_NONE
	close_btn.custom_minimum_size = Vector2(0, Margins.TOUCH_MIN)
	close_btn.pressed.connect(_on_close_pressed)
	_style_ink_button(close_btn)
	_nav.add_child(close_btn)
	var menu_btn := Button.new()
	menu_btn.text = "Exit to menu"
	menu_btn.focus_mode = Control.FOCUS_NONE
	menu_btn.custom_minimum_size = Vector2(0, Margins.TOUCH_MIN)
	menu_btn.pressed.connect(_on_exit_menu_pressed)
	_style_ink_button(menu_btn)
	_nav.add_child(menu_btn)


func _fill_page_column(box: VBoxContainer, page: Dictionary) -> void:
	_add_heading(box, str(page.get("title", "")))
	var kind := str(page.get("kind", "info"))
	if kind == "log":
		_log = RichTextLabel.new()
		_log.bbcode_enabled = false
		_log.fit_content = false
		_log.scroll_active = true
		_log.size_flags_vertical = Control.SIZE_EXPAND_FILL
		_log.custom_minimum_size = Vector2(0, 160)
		_log.add_theme_font_size_override("normal_font_size", Margins.scaled_font(Margins.CAPTION_FONT))
		_log.add_theme_color_override("default_color", Margins.TEXT_INK)
		_log.selection_enabled = true
		for line in model.log_lines:
			_log.append_text(str(line) + "\n")
		box.add_child(_log)
	else:
		var body := str(page.get("body", ""))
		if body != "":
			_add_body(box, body, Margins.TEXT_INK)
		var scroll := ScrollContainer.new()
		scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
		scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
		scroll.custom_minimum_size = Vector2(0, 120)
		box.add_child(scroll)
		_actions = VBoxContainer.new()
		_actions.add_theme_constant_override("separation", Margins.TOUCH_GAP)
		scroll.add_child(_actions)
		var actions: Array = page.get("actions", [])
		for act in actions:
			_add_action_button(_actions, act)


func _add_action_button(parent: VBoxContainer, act: Dictionary) -> void:
	var id := str(act.get("id", ""))
	var label := str(act.get("label", id))
	var b := Button.new()
	b.text = label
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(0, Margins.TOUCH_MIN)
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
	box.add_child(l)


func _add_caption(box: VBoxContainer, text: String) -> void:
	var l := Label.new()
	l.text = text
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.add_theme_font_size_override("font_size", Margins.scaled_font(Margins.CAPTION_FONT))
	l.add_theme_color_override("font_color", Margins.TEXT_MUTED)
	box.add_child(l)


func _add_body(box: VBoxContainer, text: String, color: Color) -> void:
	if text == "":
		return
	var l := Label.new()
	l.text = text
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.add_theme_font_size_override("font_size", Margins.scaled_font(Margins.BODY_FONT))
	l.add_theme_color_override("font_color", color)
	box.add_child(l)


func _clear_box(box: VBoxContainer) -> void:
	for c in box.get_children():
		c.queue_free()


func _style_ink_button(b: Button) -> void:
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


func _on_open_pressed() -> void:
	if _duplicate_press():
		return
	if model == null:
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
	if _duplicate_press():
		return
	if model == null:
		return
	if Margins.reduced_motion():
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
	if _duplicate_press():
		return
	if model:
		model.request_exit_menu()


func _on_cancel_targeting() -> void:
	if model:
		model.cancel_targeting()


func _on_tab(index: int) -> void:
	if model:
		model.goto_page(index)


func _on_action_pressed(action_id: String, payload: Dictionary, opts: Dictionary) -> void:
	if _duplicate_press():
		return
	if model == null:
		return
	model.request_action(action_id, payload, opts)


func _on_blocker_input(event: InputEvent) -> void:
	# Swallow all input so clicks cannot reach the world while the book is open.
	if event is InputEventMouseButton or event is InputEventScreenTouch:
		accept_event()


func _duplicate_press() -> bool:
	var now := Time.get_ticks_msec()
	if now < _press_guard_msec:
		return true
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
