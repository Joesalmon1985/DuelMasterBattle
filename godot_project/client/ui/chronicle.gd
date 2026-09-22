extends Control
class_name DmbChroniclePanel

## Knowledge-filtered Chronicle. Responsive full-screen modal.

const ResponsiveModal = preload("res://client/ui/responsive_modal.gd")

signal closed

var _title: Label
var _debug := false
var _events: Array = []
var _margin: MarginContainer
var _panel: PanelContainer
var _close_btn: Button
var _debug_btn: Button
var _scroll: ScrollContainer
var _list_box: VBoxContainer


func _ready() -> void:
	visible = false
	var parts: Dictionary = ResponsiveModal.build_shell(self, "Chronicle")
	_margin = parts["margin"]
	_panel = parts["panel"]
	_title = parts["title"]
	_close_btn = parts["close_btn"]
	_close_btn.pressed.connect(hide_panel)
	var body: VBoxContainer = parts["body"]
	_scroll = ScrollContainer.new()
	_scroll.name = "EventScroll"
	_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	body.add_child(_scroll)
	_list_box = VBoxContainer.new()
	_list_box.name = "EventList"
	_list_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_list_box.add_theme_constant_override("separation", 6)
	_scroll.add_child(_list_box)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	body.add_child(row)
	_debug_btn = Button.new()
	_debug_btn.name = "DebugButton"
	_debug_btn.text = "Debug all"
	_debug_btn.custom_minimum_size = Vector2(120, 48)
	_debug_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_debug_btn.pressed.connect(_toggle_debug)
	row.add_child(_debug_btn)
	# Close already in header; keep a bottom Close for thumb reach on portrait.
	var bottom_close := Button.new()
	bottom_close.text = "Close"
	bottom_close.custom_minimum_size = Vector2(120, 48)
	bottom_close.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bottom_close.pressed.connect(hide_panel)
	row.add_child(bottom_close)
	resized.connect(_relayout)
	_relayout()


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED or what == NOTIFICATION_VISIBILITY_CHANGED:
		if visible:
			_relayout()


func show_events(events: Array, debug: bool = false) -> void:
	_events = events
	_debug = debug
	visible = true
	_relayout()
	_refresh()
	call_deferred("_relayout")


func hide_panel() -> void:
	visible = false
	closed.emit()


func close_button() -> Button:
	return _close_btn


func event_scroll() -> ScrollContainer:
	return _scroll


func _relayout() -> void:
	if _margin == null or _panel == null:
		return
	var vp := get_viewport_rect().size
	if vp.x < 1.0 or vp.y < 1.0:
		return
	ResponsiveModal.apply_margins(_margin, vp)
	ResponsiveModal.apply_panel_bounds(_panel, vp, 0.94, 0.88)
	if _list_box != null:
		_list_box.custom_minimum_size.x = maxf(120.0, _panel.size.x - 32.0)


func _toggle_debug() -> void:
	_debug = not _debug
	_refresh()


func _refresh() -> void:
	for child in _list_box.get_children():
		child.queue_free()
	_title.text = "Chronicle (debug)" if _debug else "Chronicle"
	var count := 0
	for raw in _events:
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var e: Dictionary = raw
		if not _debug and not bool(e.get("public", true)):
			continue
		var turn := int(e.get("turn", 0))
		var kind := str(e.get("kind", "event"))
		var summary := str(e.get("summary", ""))
		var lbl := Label.new()
		lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		lbl.text = "T%s · %s — %s" % [turn, kind, summary]
		lbl.add_theme_font_size_override("font_size", 13)
		_list_box.add_child(lbl)
		count += 1
	if count == 0:
		var empty := Label.new()
		empty.text = "No known Chronicle events yet."
		empty.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_list_box.add_child(empty)
