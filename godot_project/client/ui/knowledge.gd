extends Control
class_name DmbKnowledgePanel

## Discovered map / history — knowledge-filtered. No army orders or global spells.

const ResponsiveModal = preload("res://client/ui/responsive_modal.gd")

signal closed
signal open_world_map_requested

var _margin: MarginContainer
var _panel: PanelContainer
var _close_btn: Button
var _facts: VBoxContainer
var _status: Label


func _ready() -> void:
	visible = false
	var parts: Dictionary = ResponsiveModal.build_shell(self, "Knowledge")
	_margin = parts["margin"]
	_panel = parts["panel"]
	_close_btn = parts["close_btn"]
	_close_btn.pressed.connect(hide_panel)
	var body: VBoxContainer = parts["body"]
	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.text = "Known people, places and Chronicle facts. Map opens read-only."
	body.add_child(_status)
	var map_btn := Button.new()
	map_btn.text = "Open World Map"
	map_btn.custom_minimum_size = Vector2(0, 48)
	map_btn.pressed.connect(func(): open_world_map_requested.emit())
	body.add_child(map_btn)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_child(scroll)
	_facts = VBoxContainer.new()
	_facts.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_facts.add_theme_constant_override("separation", 6)
	scroll.add_child(_facts)
	resized.connect(_relayout)
	_relayout()


func show_knowledge(entries: Array) -> void:
	visible = true
	for c in _facts.get_children():
		c.queue_free()
	if entries.is_empty():
		var empty := Label.new()
		empty.text = "Nothing discovered yet."
		empty.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_facts.add_child(empty)
	else:
		for raw in entries:
			if typeof(raw) != TYPE_DICTIONARY:
				continue
			var e: Dictionary = raw
			var lbl := Label.new()
			lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			lbl.text = "%s — %s" % [str(e.get("label", e.get("id", "?"))), str(e.get("summary", e.get("fact", "")))]
			lbl.add_theme_font_size_override("font_size", 13)
			_facts.add_child(lbl)
	_relayout()


func hide_panel() -> void:
	visible = false
	closed.emit()


func close_button() -> Button:
	return _close_btn


func _relayout() -> void:
	if _margin == null or _panel == null:
		return
	var vp := get_viewport_rect().size
	if vp.x < 1.0:
		return
	ResponsiveModal.apply_margins(_margin, vp)
	ResponsiveModal.apply_panel_bounds(_panel, vp, 0.94, 0.88)
