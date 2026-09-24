extends Control
class_name DmbInventoryPanel

## Pointer-only inventory: use / give / equip / drop. Pause while open.

const ResponsiveModal = preload("res://client/ui/responsive_modal.gd")
const SemanticPlaceholder = preload("res://client/world/semantic_placeholder.gd")

signal closed
signal action_requested(action: String, item_id: String, extra: Dictionary)

var _margin: MarginContainer
var _panel: PanelContainer
var _close_btn: Button
var _list: VBoxContainer
var _status: Label
var _items: Array = []
var _selected: String = ""
var _pause_reason := "inventory"


func _ready() -> void:
	visible = false
	var parts: Dictionary = ResponsiveModal.build_shell(self, "Inventory")
	_margin = parts["margin"]
	_panel = parts["panel"]
	_close_btn = parts["close_btn"]
	_close_btn.pressed.connect(hide_panel)
	var body: VBoxContainer = parts["body"]
	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.text = "Select an item, then Use / Equip / Drop."
	body.add_child(_status)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.add_child(scroll)
	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_list.add_theme_constant_override("separation", 6)
	scroll.add_child(_list)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	body.add_child(row)
	for label_action in [["Use", "use"], ["Equip focus", "equip_focus"], ["Equip artifact", "equip_artifact"], ["Drop", "drop"]]:
		var btn := Button.new()
		btn.text = label_action[0]
		btn.custom_minimum_size = Vector2(0, 48)
		btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var act: String = label_action[1]
		btn.pressed.connect(func(): _emit_action(act))
		row.add_child(btn)
	resized.connect(_relayout)
	_relayout()


func show_items(items: Array) -> void:
	_items = items
	visible = true
	_refresh()
	_relayout()
	call_deferred("_relayout")


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


func _refresh() -> void:
	for c in _list.get_children():
		c.queue_free()
	if _items.is_empty():
		var empty := Label.new()
		empty.text = "Bag empty."
		empty.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_list.add_child(empty)
		return
	for raw in _items:
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var item: Dictionary = raw
		var iid := str(item.get("id", ""))
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 8)
		var sem := str(item.get("definition_id") or item.get("semantic_id") or "item.unknown")
		var badge := SemanticPlaceholder.make_badge(sem, Vector2(48, 48), {"abbrev": str(item.get("label", "?")).substr(0, 3), "shape": "rounded_rect"})
		row.add_child(badge)
		var btn := Button.new()
		btn.toggle_mode = true
		btn.button_pressed = iid == _selected
		btn.text = "%s%s" % [str(item.get("label", iid)), " [%s]" % item.get("equipped_slot") if str(item.get("equipped_slot", "")) != "" else ""]
		btn.custom_minimum_size = Vector2(0, 48)
		btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		btn.pressed.connect(func(): _select(iid))
		row.add_child(btn)
		_list.add_child(row)


func _select(item_id: String) -> void:
	_selected = item_id
	_status.text = "Selected %s" % item_id
	_refresh()


func _emit_action(action: String) -> void:
	if _selected == "":
		_status.text = "Select an item first."
		return
	var extra := {}
	if action == "equip_focus":
		action = "equip"
		extra["slot"] = "focus"
	elif action == "equip_artifact":
		action = "equip"
		extra["slot"] = "artifact"
	action_requested.emit(action, _selected, extra)
