extends Control
class_name DmbChroniclePanel

## Knowledge-filtered Chronicle. Debug mode shows all recorded facts.

signal closed

var _list: ItemList
var _title: Label
var _debug := false
var _events: Array = []


func _ready() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_STOP
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.55)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.custom_minimum_size = Vector2(460, 420)
	panel.position = Vector2(-230, -210)
	add_child(panel)
	var v := VBoxContainer.new()
	panel.add_child(v)
	_title = Label.new()
	_title.text = "Chronicle"
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(_title)
	_list = ItemList.new()
	_list.custom_minimum_size = Vector2(440, 320)
	_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	v.add_child(_list)
	var row := HBoxContainer.new()
	v.add_child(row)
	var debug_btn := Button.new()
	debug_btn.text = "Debug all"
	debug_btn.pressed.connect(_toggle_debug)
	row.add_child(debug_btn)
	var close_btn := Button.new()
	close_btn.text = "Close"
	close_btn.pressed.connect(hide_panel)
	row.add_child(close_btn)


func show_events(events: Array, *, debug: bool = false) -> void:
	_events = events
	_debug = debug
	_refresh()
	visible = true


func hide_panel() -> void:
	visible = false
	closed.emit()


func _toggle_debug() -> void:
	_debug = not _debug
	_refresh()


func _refresh() -> void:
	_list.clear()
	_title.text = "Chronicle (debug)" if _debug else "Chronicle"
	for raw in _events:
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var e: Dictionary = raw
		if not _debug and not bool(e.get("public", true)):
			continue
		var turn := int(e.get("turn", 0))
		var kind := str(e.get("kind", "event"))
		var summary := str(e.get("summary", ""))
		_list.add_item("T%s · %s — %s" % [turn, kind, summary])
