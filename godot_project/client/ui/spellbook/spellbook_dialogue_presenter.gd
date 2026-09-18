extends Control
class_name SpellbookDialoguePresenter

## Book-backed dialogue surface compatible with DialogueBox say/choose/advance.
## Forwards consequences only through caller-supplied VillageQuestRunner paths.
## Separate gestures: tap line to finish reveal; tap Continue to advance.

const Margins = preload("res://client/ui/spellbook/spellbook_margins.gd")
const HostScript = preload("res://client/ui/spellbook/spellbook_host.gd")
const ModelScript = preload("res://client/ui/spellbook/spellbook_model.gd")

signal opened
signal closed
signal advanced
signal chosen(label: String)

var instant_text := false
var _model
var _host
var _open := false
var _typing := false
var _full_text := ""
var _visible_chars := 0
var _waiting_choice := false
var _choice_labels: Array = []
var _history: PackedStringArray = PackedStringArray()
var _speaker := ""
var _type_tween: Tween
var _ignore_until_msec := 0
var _line_box: VBoxContainer
var _speaker_lbl: Label
var _text_lbl: RichTextLabel
var _hint_lbl: Label
var _choice_scroll: ScrollContainer
var _choice_box: VBoxContainer
var _history_lbl: RichTextLabel
var _continue_btn: Button
var _close_btn: Button


func _ready() -> void:
	set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false
	_model = ModelScript.new()
	_model.begin_session("dialogue")
	_model.title = "Conversation"
	_model.set_connection(ModelScript.ConnState.READY)
	_model.set_pages([{
		"id": "dialogue",
		"title": "Dialogue",
		"kind": "info",
		"body": "",
		"actions": [],
	}])
	_host = HostScript.new()
	add_child(_host)
	_host.bind_model(_model)
	_host.close_requested.connect(_on_close_book)
	_build_overlay_widgets()


func _build_overlay_widgets() -> void:
	# Content is drawn inside the open book via a dedicated overlay panel for clarity.
	var panel := PanelContainer.new()
	panel.name = "DialogueOverlay"
	panel.set_anchors_preset(PRESET_BOTTOM_WIDE)
	panel.offset_left = 24
	panel.offset_right = -24
	panel.offset_top = -420
	panel.offset_bottom = -120
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(panel)
	_line_box = VBoxContainer.new()
	_line_box.add_theme_constant_override("separation", 8)
	panel.add_child(_line_box)
	_speaker_lbl = Label.new()
	_speaker_lbl.add_theme_font_size_override("font_size", Margins.scaled_font(Margins.HEADING_FONT))
	_speaker_lbl.add_theme_color_override("font_color", Margins.TEXT_ACCENT)
	_line_box.add_child(_speaker_lbl)
	_text_lbl = RichTextLabel.new()
	_text_lbl.bbcode_enabled = false
	_text_lbl.fit_content = false
	_text_lbl.scroll_active = true
	_text_lbl.custom_minimum_size = Vector2(0, 120)
	_text_lbl.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_text_lbl.add_theme_font_size_override("normal_font_size", Margins.scaled_font(Margins.BODY_FONT))
	_text_lbl.add_theme_color_override("default_color", Margins.TEXT_INK)
	_text_lbl.gui_input.connect(_on_text_gui)
	_line_box.add_child(_text_lbl)
	_hint_lbl = Label.new()
	_hint_lbl.add_theme_font_size_override("font_size", Margins.scaled_font(Margins.CAPTION_FONT))
	_hint_lbl.add_theme_color_override("font_color", Margins.TEXT_MUTED)
	_line_box.add_child(_hint_lbl)
	_choice_scroll = ScrollContainer.new()
	_choice_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_choice_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	# ~3 touch-sized choices visible; additional options scroll.
	_choice_scroll.custom_minimum_size = Vector2(0, Margins.TOUCH_MIN * 3.0 + Margins.TOUCH_GAP * 2.0)
	_choice_scroll.visible = false
	_line_box.add_child(_choice_scroll)
	_choice_box = VBoxContainer.new()
	_choice_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_choice_box.add_theme_constant_override("separation", Margins.TOUCH_GAP)
	_choice_scroll.add_child(_choice_box)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", Margins.TOUCH_GAP)
	_line_box.add_child(row)
	_continue_btn = Button.new()
	_continue_btn.text = "Continue"
	_continue_btn.focus_mode = Control.FOCUS_NONE
	_continue_btn.custom_minimum_size = Vector2(140, Margins.TOUCH_MIN)
	_continue_btn.pressed.connect(_on_continue)
	row.add_child(_continue_btn)
	_close_btn = Button.new()
	_close_btn.text = "Close book"
	_close_btn.focus_mode = Control.FOCUS_NONE
	_close_btn.custom_minimum_size = Vector2(140, Margins.TOUCH_MIN)
	_close_btn.pressed.connect(_on_close_book)
	row.add_child(_close_btn)
	_history_lbl = RichTextLabel.new()
	_history_lbl.custom_minimum_size = Vector2(0, 72)
	_history_lbl.scroll_active = true
	_history_lbl.add_theme_font_size_override("normal_font_size", Margins.scaled_font(Margins.CAPTION_FONT))
	_history_lbl.add_theme_color_override("default_color", Margins.TEXT_MUTED)
	_line_box.add_child(_history_lbl)


func is_open() -> bool:
	return _open


func is_waiting_choice() -> bool:
	return _waiting_choice


func say(speaker: String, text: String) -> void:
	_show(speaker, text)


func say_async(speaker: String, text: String) -> void:
	_show(speaker, text)
	await advanced


func choose_async(prompt: String, options: Array) -> String:
	_pending_choices(prompt, options)
	var result: String = await chosen
	return result


func advance() -> void:
	# Compatibility with DialogueBox: while typing, finish reveal only.
	if _typing:
		_finish_reveal()
		return
	if _waiting_choice:
		return
	_emit_advanced()


func pick(label: String) -> void:
	if not _waiting_choice:
		return
	if Time.get_ticks_msec() < _ignore_until_msec:
		return
	_waiting_choice = false
	_clear_choices()
	emit_signal("chosen", label)
	_history.append("> %s" % label)
	_refresh_history()


func pick_index(i: int) -> void:
	if i < 0 or i >= _choice_labels.size():
		return
	pick(str(_choice_labels[i]))


func _show(speaker: String, text: String) -> void:
	_open = true
	visible = true
	_model.open_book()
	_speaker = speaker
	_full_text = text
	_speaker_lbl.text = speaker
	_waiting_choice = false
	_clear_choices()
	_continue_btn.visible = true
	_continue_btn.text = "Continue"
	_hint_lbl.text = "Tap text to finish reveal · Continue advances"
	_history.append("%s: %s" % [speaker, text])
	_refresh_history()
	emit_signal("opened")
	_ignore_until_msec = Time.get_ticks_msec() + 180
	if instant_text or Margins.reduced_motion():
		_text_lbl.text = text
		_text_lbl.visible_characters = -1
		_typing = false
		return
	_typing = true
	_visible_chars = 0
	_text_lbl.text = text
	_text_lbl.visible_characters = 0
	if _type_tween != null and _type_tween.is_valid():
		_type_tween.kill()
	_type_tween = create_tween()
	var duration := clampf(float(text.length()) * 0.018, 0.2, 1.8)
	_type_tween.tween_method(_set_visible_chars, 0, text.length(), duration)
	_type_tween.tween_callback(func(): _typing = false)


func _set_visible_chars(n: int) -> void:
	_visible_chars = n
	_text_lbl.visible_characters = n


func _finish_reveal() -> void:
	if _type_tween != null and _type_tween.is_valid():
		_type_tween.kill()
	_text_lbl.visible_characters = -1
	_typing = false


func _pending_choices(prompt: String, options: Array) -> void:
	_show("", prompt)
	_finish_reveal()
	_waiting_choice = true
	_continue_btn.visible = false
	_hint_lbl.text = "Choose a response"
	_choice_labels = []
	_clear_choices()
	_choice_scroll.visible = true
	for o in options:
		var label := str(o)
		_choice_labels.append(label)
		var b := Button.new()
		b.text = label
		b.focus_mode = Control.FOCUS_NONE
		b.custom_minimum_size = Vector2(0, Margins.TOUCH_MIN)
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.pressed.connect(func(): pick(label))
		_choice_box.add_child(b)
	if options.size() > 3:
		_hint_lbl.text = "Choose a response — scroll for more"
	_ignore_until_msec = Time.get_ticks_msec() + 200


func _clear_choices() -> void:
	for c in _choice_box.get_children():
		c.queue_free()
	if _choice_scroll:
		_choice_scroll.visible = false


func _refresh_history() -> void:
	_history_lbl.clear()
	var start: int = maxi(0, _history.size() - 8)
	for i in range(start, _history.size()):
		_history_lbl.append_text(str(_history[i]) + "\n")


func _on_text_gui(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if _typing:
			_finish_reveal()
			accept_event()


func _on_continue() -> void:
	if Time.get_ticks_msec() < _ignore_until_msec:
		return
	if _typing:
		_finish_reveal()
		return
	_emit_advanced()


func _emit_advanced() -> void:
	emit_signal("advanced")


func _on_close_book() -> void:
	# Closing the book cancels presentation only — callers own quest cancellation.
	# Model close_book early-returns when already COMPACT so this cannot recurse
	# via host.close_requested → here → model.close_book → close_requested…
	if not _open:
		_model.close_book()
		return
	_open = false
	visible = false
	# Unblock choose_async awaiters without applying a choice consequence.
	if _waiting_choice:
		_waiting_choice = false
		_clear_choices()
		emit_signal("chosen", "")
	else:
		_clear_choices()
	_model.close_book()
	emit_signal("closed")
