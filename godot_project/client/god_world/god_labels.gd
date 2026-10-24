extends Node
class_name GodLabels

## The two-step label contract (docs/GOD_WORLD_PRD.md 12.2): HIDDEN -> tap a thing -> LABEL (a small anchored, tappable label naming it) -> tap the
## label -> DETAILS (a bottom sheet). Tap another thing: its label replaces the first. Tap empty world: dismiss. Back: DETAILS -> LABEL -> HIDDEN.
## No distance, sight or dialogue condition: a god inspects anything. The label is anchored with the same transform the world is drawn with and
## stays screen-sized; its touch target is at least 48 dp.

const _VT = preload("res://client/scripts/visual_theme.gd")
const NarrativeCard = preload("res://client/ui/narrative_card.gd")
const _RM = preload("res://client/ui/responsive_modal.gd")

enum State { HIDDEN, LABEL, DETAILS }

var world: Node  # god_world.gd
var state: int = State.HIDDEN
var selected_id := ""
var label_btn: Button
var sheet: Control  # DmbNarrativeCard
var _layer: CanvasLayer
var _shade: ColorRect  # a dark backing under the sheet: the card's own style is translucent and buildings showed through the text
var _label_data: Dictionary = {}
var _details: Dictionary = {}
var opens := 0  # test counters
var detail_opens := 0


func setup(p_world: Node) -> void:
	world = p_world
	_layer = CanvasLayer.new()
	_layer.name = "LabelLayer"
	_layer.layer = 12
	world.add_child(_layer)
	label_btn = Button.new()
	label_btn.name = "GodLabel"
	label_btn.visible = false
	label_btn.focus_mode = Control.FOCUS_NONE
	label_btn.add_theme_font_size_override("font_size", 26)
	label_btn.add_theme_stylebox_override("normal", _VT.flat_panel_style(Color(0.08, 0.06, 0.14, 0.92), 12))
	label_btn.add_theme_stylebox_override("hover", _VT.flat_panel_style(Color(0.12, 0.09, 0.2, 0.95), 12))
	label_btn.add_theme_stylebox_override("pressed", _VT.flat_panel_style(Color(0.2, 0.15, 0.3, 0.95), 12))
	label_btn.add_theme_color_override("font_color", _VT.COLOR_TEXT_PRIMARY)
	label_btn.pressed.connect(_on_label_pressed)
	_layer.add_child(label_btn)
	_shade = ColorRect.new()
	_shade.name = "DetailsShade"
	_shade.color = Color(0.05, 0.04, 0.09, 0.8)
	_shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_shade.visible = false
	_layer.add_child(_shade)
	sheet = NarrativeCard.new()
	_layer.add_child(sheet)
	sheet.setup(world, "sheet", "GodDetails")
	sheet.footer_pressed.connect(func(_id: String) -> void: back())
	sheet.choice_pressed.connect(func(_id: String) -> void: back())


func _process(_delta: float) -> void:
	_shade.visible = state == State.DETAILS and sheet.visible
	if _shade.visible:
		_shade.position = sheet.panel.global_position
		_shade.size = sheet.panel.size
	if state == State.HIDDEN:
		return
	_place_label()


## First-stage selection: a tap on a thing. Replaces any earlier selection.
func select(id: String) -> void:
	if id == "":
		clear()
		return
	var reply: Dictionary = world.sim_op({"op": "label", "id": id})
	if str(reply.get("status", "")) != "ok":
		return
	_label_data = reply.get("label", {})
	selected_id = id
	state = State.LABEL
	opens += 1
	sheet.hide_card()
	var title := str(_label_data.get("title", id))
	var sub := str(_label_data.get("subtitle", ""))
	label_btn.text = title if sub == "" else "%s\n%s" % [title, sub]
	var fac := str(_label_data.get("faction", ""))
	var col: Color = world.view.faction_colors.get(fac, _VT.COLOR_ACCENT_GOLD) if fac != "" else _VT.COLOR_ACCENT_GOLD
	label_btn.add_theme_color_override("font_color", col.lightened(0.35) if fac != "" else _VT.COLOR_TEXT_PRIMARY)
	label_btn.visible = true
	label_btn.reset_size()
	_place_label()
	world.view.selected_id = id
	world.view.queue_redraw()


## The second, distinct gesture: the label itself was tapped.
func _on_label_pressed() -> void:
	if state != State.LABEL or selected_id == "":
		return
	open_details()


func open_details() -> void:
	var reply: Dictionary = world.sim_op({"op": "inspect", "id": selected_id})
	if str(reply.get("status", "")) != "ok":
		return
	_details = reply.get("details", {})
	state = State.DETAILS
	detail_opens += 1
	var lines: Array = _details.get("lines", [])
	var body := ""
	for l in lines:
		body += str(l) + "\n\n"
	sheet.show_card(str(_details.get("title", "")), str(_details.get("subtitle", "")), body.strip_edges(), [], [{"id": "close", "text": "Close"}])
	label_btn.visible = false


func back() -> bool:
	if state == State.DETAILS:
		sheet.hide_card()
		state = State.LABEL
		label_btn.visible = true
		_place_label()
		return true
	if state == State.LABEL:
		clear()
		return true
	return false


func clear() -> void:
	state = State.HIDDEN
	selected_id = ""
	label_btn.visible = false
	sheet.hide_card()
	if world != null and world.view != null:
		world.view.selected_id = ""
		world.view.queue_redraw()


func _place_label() -> void:
	if selected_id == "" or world.view == null:
		return
	var anchor: Vector2 = world.view.anchor_of(selected_id)
	if anchor == Vector2.INF:
		if state == State.LABEL:
			label_btn.visible = false  # gone (a caravan arrived): the next tap selects afresh
		return
	var sp: Vector2 = world.camera_ctl.world_to_screen(anchor)
	var vis: Vector2 = world.get_viewport().get_visible_rect().size
	var min_touch := 48.0 * 1.6  # 48 dp in the 720-wide base viewport
	var size := label_btn.get_combined_minimum_size()
	size.x = maxf(size.x + 24.0, min_touch)
	size.y = maxf(size.y + 8.0, min_touch)
	label_btn.size = size
	var pos := sp - Vector2(size.x * 0.5, size.y + 18.0)
	var top_strip := 120.0
	var bottom := vis.y - 150.0
	pos.x = clampf(pos.x, 12.0, vis.x - size.x - 12.0)
	pos.y = clampf(pos.y, top_strip, bottom - size.y)
	label_btn.position = pos
	var offscreen := sp.x < -40.0 or sp.y < -40.0 or sp.x > vis.x + 40.0 or sp.y > vis.y + 40.0
	if state == State.LABEL:
		label_btn.visible = not offscreen  # the identity is kept; the label hides with its anchor


func refresh_details() -> void:
	if state == State.DETAILS and selected_id != "":
		var reply: Dictionary = world.sim_op({"op": "inspect", "id": selected_id})
		if str(reply.get("status", "")) == "ok":
			_details = reply.get("details", {})
			var body := ""
			for l in _details.get("lines", []):
				body += str(l) + "\n\n"
			sheet.body_label.text = body.strip_edges()


func ui_state() -> Dictionary:
	return {"state": ["HIDDEN", "LABEL", "DETAILS"][state], "id": selected_id, "label": label_btn.text if label_btn.visible else "", "label_rect": Rect2(label_btn.position, label_btn.size),
			"details_title": sheet.title_label.text if sheet.visible else "", "opens": opens, "detail_opens": detail_opens}
