extends Control
class_name DialogueBox

## Bottom-anchored dialogue panel. Text types in; tap anywhere (or Space/Enter)
## to finish typing or advance. `choose_async` shows tappable options.

const _VT = preload("res://client/scripts/visual_theme.gd")

signal opened
signal closed
signal advanced
signal chosen(label: String)

var _panel: PanelContainer
var _name_lbl: Label
var _text_lbl: RichTextLabel
var _hint_lbl: Label
var _choices: VBoxContainer
var _open: bool = false
var _typing: bool = false
var _full_text: String = ""
var _type_tween: Tween
var _waiting_choice: bool = false
var _ignore_until_msec: int = 0

## Pagination (brief §19): long text is split into pages that fit the panel.
## First tap while typing completes the page; further taps turn pages; only
## the final page closes. Nothing is clipped or dropped.
const PAGE_CHARS := 190          # conservative budget for 24px font in a 210px panel
var _pages: Array = []
var _page_index: int = 0
var _pending_choice_options: Array = []
var _pending_choice_prompt: String = ""


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false
	_panel = PanelContainer.new()
	_panel.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	_panel.offset_left = 14
	_panel.offset_right = -14
	_panel.offset_top = -300
	_panel.offset_bottom = -300 + 210
	var style := _VT.panel_style(14)
	style.bg_color = Color(0.09, 0.07, 0.16, 0.96)
	_panel.add_theme_stylebox_override("panel", style)
	_panel.mouse_filter = Control.MOUSE_FILTER_STOP
	_panel.gui_input.connect(_on_gui_input)
	add_child(_panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	_panel.add_child(v)
	_name_lbl = Label.new()
	_VT.apply_label_secondary(_name_lbl)
	_name_lbl.add_theme_color_override("font_color", _VT.COLOR_ACCENT_GOLD)
	_name_lbl.add_theme_font_size_override("font_size", 20)
	v.add_child(_name_lbl)
	_text_lbl = RichTextLabel.new()
	_text_lbl.bbcode_enabled = false
	_text_lbl.fit_content = false
	_text_lbl.scroll_active = false
	_text_lbl.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_text_lbl.add_theme_font_size_override("normal_font_size", 24)
	_text_lbl.add_theme_color_override("default_color", _VT.COLOR_TEXT_PRIMARY)
	_text_lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	v.add_child(_text_lbl)
	_choices = VBoxContainer.new()
	_choices.add_theme_constant_override("separation", 8)
	v.add_child(_choices)
	_hint_lbl = Label.new()
	_hint_lbl.text = "▼ tap to continue"
	_VT.apply_label_caption(_hint_lbl)
	_hint_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	v.add_child(_hint_lbl)


func _unhandled_input(event: InputEvent) -> void:
	if not _open:
		return
	if event is InputEventKey and event.pressed and not event.echo and event.keycode in [KEY_SPACE, KEY_ENTER, KEY_Z, KEY_E]:
		advance()
		get_viewport().set_input_as_handled()


func _on_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		advance()


func is_open() -> bool:
	return _open


func is_waiting_choice() -> bool:
	return _waiting_choice


func say(speaker: String, text: String) -> void:
	_show(speaker, text)


## Awaitable: resolves when the player advances past this line.
func say_async(speaker: String, text: String) -> void:
	_show(speaker, text)
	await advanced


func choose_async(prompt: String, options: Array) -> String:
	_pending_choice_options = options.duplicate()
	_pending_choice_prompt = prompt
	_show("", prompt)
	if _pages.size() <= 1:
		_present_choices()
	# else: _present_choices() runs when the final page is reached in advance().
	var result: String = await chosen
	return result


func _present_choices() -> void:
	_typing = false
	if _type_tween and _type_tween.is_valid():
		_type_tween.kill()
	_text_lbl.visible_characters = -1
	_waiting_choice = true
	_hint_lbl.visible = false
	_panel.offset_top = -300 - 56 * _pending_choice_options.size()
	for o in _pending_choice_options:
		var b := Button.new()
		b.text = str(o)
		b.custom_minimum_size = Vector2(0, 56)
		_VT.style_secondary_button(b)
		var label := str(o)
		b.pressed.connect(func(): pick(label))
		_choices.add_child(b)
	_pending_choice_options = []


func pick(label: String) -> void:
	if not _waiting_choice:
		return
	var valid := false
	for c in _choices.get_children():
		if c is Button and (c as Button).text == label:
			valid = true
	if not valid:
		return
	_waiting_choice = false
	for c in _choices.get_children():
		c.queue_free()
	_panel.offset_top = -300
	_hint_lbl.visible = true
	_close()
	chosen.emit(label)


func _show(speaker: String, text: String) -> void:
	_name_lbl.text = speaker
	_name_lbl.visible = speaker != ""
	_full_text = text
	_pages = paginate(text)
	_page_index = 0
	if not _open:
		_open = true
		visible = true
		opened.emit()
	_show_page()


func _show_page() -> void:
	var page: String = _pages[_page_index] if _page_index < _pages.size() else ""
	_text_lbl.text = page
	_text_lbl.visible_characters = 0
	_typing = true
	_hint_lbl.visible = false
	_hint_lbl.text = "▼ tap to continue" if _page_index >= _pages.size() - 1 else "▼ more (%d/%d)" % [_page_index + 1, _pages.size()]
	_ignore_until_msec = Time.get_ticks_msec() + 180
	if _type_tween and _type_tween.is_valid():
		_type_tween.kill()
	var chars := page.length()
	_type_tween = create_tween()
	_type_tween.tween_property(_text_lbl, "visible_characters", chars, clampf(chars * 0.012, 0.15, 1.6))
	_type_tween.tween_callback(func():
		_typing = false
		_hint_lbl.visible = not _waiting_choice
	)


## Split text into panel-sized pages. Paragraph breaks are preferred cut points;
## an over-long paragraph is cut at the last word boundary before the budget.
## Concatenating pages (with the joins restored) reproduces the input exactly.
static func paginate(text: String, budget: int = PAGE_CHARS) -> Array:
	var pages: Array = []
	var current := ""
	for para in text.split("\n\n"):
		var candidate := para if current == "" else current + "\n\n" + para
		if candidate.length() <= budget:
			current = candidate
			continue
		if current != "":
			pages.append(current)
			current = ""
		# paragraph alone may still be too long: cut on word boundaries
		var rest := para
		while rest.length() > budget:
			var cut := rest.rfind(" ", budget)
			if cut <= 0:
				cut = budget
			pages.append(rest.substr(0, cut))
			rest = rest.substr(cut).strip_edges(true, false)
		current = rest
	if current != "" or pages.is_empty():
		pages.append(current)
	return pages


func advance() -> void:
	if not _open or _waiting_choice:
		return
	if Time.get_ticks_msec() < _ignore_until_msec:
		return
	if _typing:
		if _type_tween and _type_tween.is_valid():
			_type_tween.kill()
		_text_lbl.visible_characters = -1
		_typing = false
		_hint_lbl.visible = true
		return
	if _page_index < _pages.size() - 1:
		_page_index += 1
		_show_page()
		if _page_index == _pages.size() - 1 and not _pending_choice_options.is_empty():
			_present_choices()
		return
	_close()
	advanced.emit()


# --- Test/inspection API ---------------------------------------------------------

func ui_page_index() -> int:
	return _page_index


func ui_page_count() -> int:
	return _pages.size()


func ui_visible_text() -> String:
	return _text_lbl.text


func ui_is_typing() -> bool:
	return _typing


func _close() -> void:
	_open = false
	visible = false
	closed.emit()
