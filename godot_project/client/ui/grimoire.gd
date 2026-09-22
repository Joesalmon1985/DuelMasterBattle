extends Control
class_name DmbGrimoirePanel

## Pointer-only spell selection — no remote cast from this screen.

const ResponsiveModal = preload("res://client/ui/responsive_modal.gd")
const SemanticPlaceholder = preload("res://client/world/semantic_placeholder.gd")

signal closed
signal spell_selected(spell_id: String)

var _margin: MarginContainer
var _panel: PanelContainer
var _close_btn: Button
var _list: VBoxContainer
var _status: Label
var _spells: Array = []
var _selected: String = ""


func _ready() -> void:
	visible = false
	var parts: Dictionary = ResponsiveModal.build_shell(self, "Grimoire")
	_margin = parts["margin"]
	_panel = parts["panel"]
	_close_btn = parts["close_btn"]
	_close_btn.pressed.connect(hide_panel)
	var body: VBoxContainer = parts["body"]
	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.text = "Select a spell for the next local cast. Cannot cast remotely from here."
	body.add_child(_status)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_child(scroll)
	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_list)
	var prepare := Button.new()
	prepare.text = "Prepare selected"
	prepare.custom_minimum_size = Vector2(0, 48)
	prepare.pressed.connect(_prepare)
	body.add_child(prepare)
	resized.connect(_relayout)
	_relayout()


func show_spells(spells: Array) -> void:
	_spells = spells
	visible = true
	_refresh()
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


func _refresh() -> void:
	for c in _list.get_children():
		c.queue_free()
	if _spells.is_empty():
		var empty := Label.new()
		empty.text = "No discovered spells yet."
		empty.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_list.add_child(empty)
		return
	for raw in _spells:
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var sp: Dictionary = raw
		var sid := str(sp.get("id", ""))
		var row := HBoxContainer.new()
		var sem := str(sp.get("semantic_id") or ("card.spell." + sid))
		row.add_child(SemanticPlaceholder.make_badge(sem, Vector2(48, 48), {"abbrev": str(sp.get("label", sid)).substr(0, 3), "shape": "portrait_rect"}))
		var btn := Button.new()
		btn.toggle_mode = true
		btn.button_pressed = sid == _selected
		btn.text = str(sp.get("label", sid))
		btn.custom_minimum_size = Vector2(0, 48)
		btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		btn.pressed.connect(func(): _selected = sid; _status.text = "Selected %s" % sid; _refresh())
		row.add_child(btn)
		_list.add_child(row)


func _prepare() -> void:
	if _selected == "":
		_status.text = "Select a spell first."
		return
	spell_selected.emit(_selected)
	_status.text = "Prepared %s for next local cast." % _selected
