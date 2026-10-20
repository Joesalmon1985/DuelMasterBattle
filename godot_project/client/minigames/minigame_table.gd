extends Control

## The one table every village game is played on (docs/PLAN_VILLAGE_MINIGAMES.md section 2.4). No rules live here: the Python host sends a `view`
## (title, message, log, areas, actions) and this control draws the areas with the widgets below and offers the actions as buttons. Every press is
## one `minigame_act` to the host; the reply's view replaces the picture. Leave (or Escape) sends `minigame_leave`, and the host's closing line
## comes back as the conversation's next card (hybrid_world.gd `_on_minigame_closed`).
##
## Areas by `kind`: "text" (a paragraph), "score" (you / them / target), "signs" (the last throws), "cards" (a hand or a row of cards, face up or
## down), "dice" (held or free), "tiles" (coloured number tiles, discs, carrots, swatches), "grid" (a board of cells with gates on the rim), "faces"
## (people with traits), "choices" (a labelled row of action buttons inside the body). Everything is drawn procedurally: no PNG is loaded here.

const _VT = preload("res://client/scripts/visual_theme.gd")
const _RM = preload("res://client/ui/responsive_modal.gd")
const CardWidget = preload("res://client/minigames/card_widget.gd")
const DieWidget = preload("res://client/minigames/die_widget.gd")
const TileWidget = preload("res://client/minigames/tile_widget.gd")
const GridWidget = preload("res://client/minigames/grid_widget.gd")
const FaceWidget = preload("res://client/minigames/face_widget.gd")

const SIGN_COLOURS := [Color(0.95, 0.45, 0.2), Color(0.35, 0.75, 0.35), Color(0.4, 0.65, 0.95), Color(0.95, 0.9, 0.55), Color(0.6, 0.6, 0.62), Color(0.5, 0.35, 0.6)]

signal closed(reply: Dictionary)
signal acted(reply: Dictionary)

var world: Node
var view: Dictionary = {}
var meta: Dictionary = {}  # game, npc, host, catalogue_title (from the host's reply)
var busy := false
var _dim: ColorRect
var _panel: PanelContainer
var _inner: VBoxContainer
var _title: Label
var _subtitle: Label
var _scroll: ScrollContainer
var _areas: VBoxContainer
var _message: Label
var _log: Label
var _actions: GridContainer
var _footer: HBoxContainer
var _leave: Button
var _action_buttons: Array = []
var _grid_selection := ""  # a grid cell picked, waiting for a direction
var _pending_timer := 0.0  # the reaction and memory games: time from the last view to the answer, sent with the action


func setup(p_world: Node) -> void:
	world = p_world
	name = "MinigameTable"
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	_dim = ColorRect.new()
	_dim.name = "Dim"
	_dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_dim.color = Color(0.05, 0.03, 0.08, 0.72)
	_dim.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_dim)
	_panel = PanelContainer.new()
	_panel.name = "Panel"
	add_child(_panel)
	_inner = VBoxContainer.new()
	_inner.name = "Inner"
	_panel.add_child(_inner)
	_title = Label.new()
	_title.name = "Title"
	_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_inner.add_child(_title)
	_subtitle = Label.new()
	_subtitle.name = "Subtitle"
	_subtitle.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_inner.add_child(_subtitle)
	_scroll = ScrollContainer.new()
	_scroll.name = "Scroll"
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_inner.add_child(_scroll)
	_areas = VBoxContainer.new()
	_areas.name = "Areas"
	_areas.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_scroll.add_child(_areas)
	_message = Label.new()
	_message.name = "Message"
	_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_inner.add_child(_message)
	_log = Label.new()
	_log.name = "Log"
	_log.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_inner.add_child(_log)
	_actions = GridContainer.new()
	_actions.name = "Actions"
	_actions.columns = 1
	_actions.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_inner.add_child(_actions)
	_footer = HBoxContainer.new()
	_footer.name = "Footer"
	_footer.alignment = BoxContainer.ALIGNMENT_END
	_inner.add_child(_footer)
	_leave = Button.new()
	_leave.name = "Leave"
	_leave.text = "Leave the table (Esc)"
	_leave.pressed.connect(leave)
	_footer.add_child(_leave)
	get_viewport().size_changed.connect(relayout)


func is_open() -> bool:
	return visible


## Lay the table from the host's reply to the `game:` choice (or to `minigame_view`): {game, npc, host, catalogue_title, view}.
func open(reply: Dictionary) -> void:
	meta = {"game": str(reply.get("game", "")), "npc": str(reply.get("npc", "")), "host": str(reply.get("host", "")), "catalogue_title": str(reply.get("catalogue_title", ""))}
	_grid_selection = ""
	busy = false
	visible = true
	apply(reply.get("view", {}))
	var sfx := get_node_or_null("/root/Sfx")
	if sfx:
		sfx.place()


func apply(v: Variant) -> void:
	view = v if typeof(v) == TYPE_DICTIONARY else {}
	_pending_timer = 0.0
	_render()


func close() -> void:
	visible = false
	view = {}
	_action_buttons = []


## One action to the host; the reply's view replaces the picture. `extra` adds fields the widgets collected (a grid move, a reaction time).
func act(action: Dictionary, extra: Dictionary = {}) -> void:
	if busy or world == null or world._sim == null:
		return
	busy = true
	var payload := {}
	for k in action:
		if k != "text" and k != "kind":
			payload[k] = action[k]
	for k in extra:
		payload[k] = extra[k]
	var reply: Dictionary = world._sim.op({"op": "minigame_act", "action": payload})
	busy = false
	var sfx := get_node_or_null("/root/Sfx")
	if str(reply.get("status", "")) == "ok":
		if sfx:
			sfx.tap()
		_grid_selection = ""
		apply(reply.get("view", {}))
		var vv: Dictionary = view
		if bool(vv.get("over", false)) and sfx:
			match str(vv.get("result", "")):
				"win": sfx.victory()
				"lose": sfx.defeat()
	else:
		if sfx:
			sfx.denied()
		if reply.has("view"):
			apply(reply.get("view", {}))
		_message.text = "That is not a move now (%s)." % str(reply.get("reason", ""))
	acted.emit(reply)


func leave() -> void:
	if world == null or world._sim == null:
		close()
		closed.emit({})
		return
	var reply: Dictionary = world._sim.op({"op": "minigame_leave"})
	close()
	closed.emit(reply)


func _unhandled_input(event: InputEvent) -> void:
	if not visible or not (event is InputEventKey and event.pressed and not event.echo):
		return
	var k: InputEventKey = event
	if k.keycode == KEY_ESCAPE:
		leave()
	elif k.keycode >= KEY_1 and k.keycode <= KEY_9:
		var i := k.keycode - KEY_1
		if i < _action_buttons.size() and not (_action_buttons[i] as Button).disabled:
			(_action_buttons[i] as Button).pressed.emit()
	get_viewport().set_input_as_handled()


func _process(delta: float) -> void:
	if visible:
		_pending_timer += delta


# ---------------------------------------------------------------- drawing

func _render() -> void:
	for c in _areas.get_children():
		_areas.remove_child(c)
		c.queue_free()
	for c in _actions.get_children():
		_actions.remove_child(c)
		c.queue_free()
	_action_buttons = []
	if view.is_empty():
		_title.text = meta.get("catalogue_title", "")
		_message.text = "The table is empty."
		relayout()
		return
	_title.text = str(view.get("title", meta.get("catalogue_title", "")))
	_subtitle.text = "with %s" % meta.get("host", "") if str(meta.get("host", "")) != "" else ""
	_subtitle.visible = _subtitle.text != ""
	for a in view.get("areas", []):
		if typeof(a) == TYPE_DICTIONARY:
			var node := _build_area(a)
			if node != null:
				_areas.add_child(node)
	_message.text = str(view.get("message", ""))
	var log: Array = view.get("log", [])
	var tail: Array = log.slice(maxi(0, log.size() - 3), log.size())
	_log.text = "\n".join(PackedStringArray(tail))
	_log.visible = not tail.is_empty()
	var over := bool(view.get("over", false))
	var shown: Array = []
	for a in view.get("actions", []):
		if typeof(a) == TYPE_DICTIONARY and not bool(a.get("hidden", false)):
			shown.append(a)
	_actions.columns = 1 if shown.size() <= 4 else (2 if shown.size() <= 10 else 3)
	var i := 0
	for a in shown:
		var b := Button.new()
		b.name = "Action_%d" % i
		b.text = ("%d. " % (i + 1) if i < 9 else "") + str(a.get("text", a.get("id", "")))
		b.set_meta("action", a)
		b.disabled = bool(a.get("disabled", false))
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.pressed.connect(_on_action.bind(a))
		_actions.add_child(b)
		_action_buttons.append(b)
		i += 1
	_leave.text = "Back to %s (Esc)" % meta.get("host", "them") if over else "Leave the table (Esc)"
	relayout()


func _on_action(a: Dictionary) -> void:
	var extra := {}
	if str(view.get("timed", "")) != "":
		extra["ms"] = int(round(_pending_timer * 1000.0))
	act(a, extra)


## A value from the host's JSON: whole numbers come as floats and are shown as integers.
static func _val(v: Variant) -> String:
	if typeof(v) == TYPE_FLOAT and is_equal_approx(v, round(v)):
		return str(int(v))
	return str(v)


func _label(text: String, small := false) -> Label:
	var l := Label.new()
	l.text = text
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.set_meta("small", small)
	return l


func _build_area(a: Dictionary) -> Control:
	var box := VBoxContainer.new()
	box.name = "Area_%s" % str(a.get("kind", "text"))
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var label := str(a.get("label", ""))
	if label != "":
		box.add_child(_label(label, true))
	match str(a.get("kind", "text")):
		"text":
			box.add_child(_label(str(a.get("text", ""))))
		"score":
			if a.has("rows"):
				var rows: Array = a["rows"]
				if rows.size() <= 3:
					var parts: PackedStringArray = []
					for r in rows:
						parts.append("%s %s" % [str(r.get("name", "")), _val(r.get("value", ""))])
					box.add_child(_label("   ".join(parts)))
				else:  # a slate: name and value in two columns
					var grid := GridContainer.new()
					grid.columns = 2
					grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
					for r in rows:
						var nl := _label(str(r.get("name", "")), true)
						nl.autowrap_mode = TextServer.AUTOWRAP_OFF
						nl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
						grid.add_child(nl)
						var vl := _label(_val(r.get("value", "")))
						vl.autowrap_mode = TextServer.AUTOWRAP_OFF
						vl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
						vl.size_flags_horizontal = Control.SIZE_SHRINK_END
						grid.add_child(vl)
					box.add_child(grid)
			else:
				var names: Array = a.get("names", ["You", "Them"])
				var t := "%s %d  -  %s %d" % [str(names[0]) if names.size() > 0 else "You", int(a.get("you", 0)), str(names[1]) if names.size() > 1 else "Them", int(a.get("them", 0))]
				if a.has("target"):
					t += "   (first to %d)" % int(a["target"])
				box.add_child(_label(t))
		"signs":
			var row := HBoxContainer.new()
			row.alignment = BoxContainer.ALIGNMENT_CENTER
			var names: Array = a.get("names", [])
			for item in a.get("items", []):
				var cell := VBoxContainer.new()
				cell.alignment = BoxContainer.ALIGNMENT_CENTER
				var sign: Control = TileWidget.new()
				var ci := int(item.get("colour", -1))
				sign.setup(str(item.get("sign", "?")), SIGN_COLOURS[ci % SIGN_COLOURS.size()] if ci >= 0 else Color(0.3, 0.28, 0.36), 84.0)
				cell.add_child(sign)
				cell.add_child(_label(str(item.get("label", "")), true))
				row.add_child(cell)
			if row.get_child_count() == 0 and not names.is_empty():
				box.add_child(_label(" / ".join(PackedStringArray(names))))
			box.add_child(row)
		"cards":
			box.add_child(_cards_row(a))
		"dice":
			box.add_child(_dice_row(a))
		"tiles":
			box.add_child(_tiles_row(a))
		"grid":
			var g: Control = GridWidget.new()
			g.configure(a, self)
			box.add_child(g)
		"faces":
			box.add_child(_faces_row(a))
		"choices":
			var flow := HFlowContainer.new()
			for c in a.get("items", []):
				var b := Button.new()
				b.text = str(c.get("text", c.get("id", "")))
				b.disabled = bool(c.get("disabled", false))
				b.pressed.connect(_on_action.bind(c))
				flow.add_child(b)
			box.add_child(flow)
		_:
			box.add_child(_label(JSON.stringify(a).substr(0, 200), true))
	return box


## Widgets call this with an action they composed (a card picked, a die held, a grid move).
func widget_act(action: Dictionary) -> void:
	_on_action(action)


func _cards_row(a: Dictionary) -> Control:
	var flow := HFlowContainer.new()
	flow.name = "Cards"
	var w := float(a.get("size", 56))
	for item in a.get("items", []):
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var c: Control = CardWidget.new()
		c.setup(item, w, self)
		c.name = "Card_%s" % str(item.get("id", "%s%s" % [item.get("rank", ""), item.get("suit", "")])).replace(":", "_")
		flow.add_child(c)
	if int(a.get("count", 0)) > 0 and flow.get_child_count() == 0:  # a hidden hand: so many face-down cards
		for i in int(a["count"]):
			var c: Control = CardWidget.new()
			c.setup({"down": true}, w, self)
			flow.add_child(c)
	return flow


func _dice_row(a: Dictionary) -> Control:
	var flow := HFlowContainer.new()
	flow.name = "Dice"
	var px := float(a.get("size", 64))
	for item in a.get("items", []):
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var d: Control = DieWidget.new()
		d.setup(item, px, self)
		d.name = "Die_%s" % str(item.get("id", item.get("value", "")))
		flow.add_child(d)
	return flow


func _tiles_row(a: Dictionary) -> Control:
	var flow := HFlowContainer.new()
	flow.name = "Tiles"
	var px := float(a.get("size", 64))
	for item in a.get("items", []):
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var t: Control = TileWidget.new()
		t.from_item(item, px, self)
		flow.add_child(t)
	return flow


func _faces_row(a: Dictionary) -> Control:
	var flow := HFlowContainer.new()
	flow.name = "Faces"
	var px := float(a.get("size", 96))
	for it in a.get("items", []):
		if typeof(it) != TYPE_DICTIONARY:
			continue
		var f: Control = FaceWidget.new()
		f.configure(it, px, self)
		flow.add_child(f)
	return flow


func relayout() -> void:
	if _panel == null:
		return
	var info := _RM.window_info(world if world != null else self)
	var m := _RM.metrics(info, "modal")
	var k: float = info["k"]
	var vis: Vector2 = info["vis"]
	position = Vector2.ZERO
	size = vis  # a child of a CanvasLayer gets no size from anchors: the dim and the click guard must cover the whole screen
	_dim.position = Vector2.ZERO
	_dim.size = vis
	_panel.add_theme_stylebox_override("panel", _VT.narr_card_style(k))
	var w: float = minf(float(m["width"]) * k * 1.12, vis.x - 2.0 * float(m["margin"]) * k)
	var h: float = vis.y - 2.0 * float(m["margin"]) * k
	_panel.custom_minimum_size = Vector2(w, 0.0)
	var gap := int(round(float(m["gap"]) * k))
	_inner.add_theme_constant_override("separation", gap)
	_areas.add_theme_constant_override("separation", gap)
	_actions.add_theme_constant_override("h_separation", gap)
	_actions.add_theme_constant_override("v_separation", gap)
	var inner_w: float = w - float(_panel.get_theme_stylebox("panel").get_minimum_size().x)
	var col_w: float = (inner_w - gap * (_actions.columns - 1)) / float(_actions.columns)
	_title.add_theme_font_size_override("font_size", int(round(float(m["title"]) * k)))
	_title.add_theme_color_override("font_color", _VT.COLOR_GOLD)
	_subtitle.add_theme_font_size_override("font_size", int(round(float(m["small"]) * k)))
	_subtitle.add_theme_color_override("font_color", _VT.COLOR_PARCHMENT_DIM)
	_message.add_theme_font_size_override("font_size", int(round(float(m["body"]) * k)))
	_message.add_theme_color_override("font_color", _VT.COLOR_PARCHMENT)
	_log.add_theme_font_size_override("font_size", int(round(float(m["small"]) * k)))
	_log.add_theme_color_override("font_color", _VT.COLOR_PARCHMENT_DIM)
	for l in _all_labels(_areas):
		var small: bool = l.has_meta("small") and bool(l.get_meta("small"))
		l.add_theme_font_size_override("font_size", int(round(float(m["small" if small else "body"]) * k)))
		l.add_theme_color_override("font_color", _VT.COLOR_PARCHMENT_DIM if small else _VT.COLOR_PARCHMENT)
	for b in _action_buttons:
		_VT.style_narr_button(b, k, "choice", float(m["body"]))
		(b as Button).custom_minimum_size = Vector2(col_w, float(m["button_h"]) * k)
		(b as Button).alignment = HORIZONTAL_ALIGNMENT_CENTER
	for b in _all_buttons(_areas):
		_VT.style_narr_button(b, k, "choice", float(m["small"]))
		(b as Button).custom_minimum_size = Vector2(0, float(m["button_h"]) * k * 0.9)
	_VT.style_narr_button(_leave, k, "primary", float(m["body"]))
	_leave.custom_minimum_size = Vector2(minf(inner_w * 0.6, 320.0 * k), float(m["button_h"]) * k)
	_fit(m, k, w, h, gap)
	if not _fit_queued:
		_fit_queued = true
		_fit_later.call_deferred(m, k, w, h, gap)


var _fit_queued := false


## The scrolling area gets the room the fixed parts leave (the narrative card's own rule), the panel is reset to its content and centred.
func _fit(m: Dictionary, k: float, w: float, h: float, gap: int) -> void:
	var chrome := 0.0
	for c in _inner.get_children():
		if c != _scroll:
			chrome += (c as Control).get_combined_minimum_size().y
	chrome += float(_panel.get_theme_stylebox("panel").get_minimum_size().y) + gap * (_inner.get_child_count() - 1)
	var room: float = h - chrome
	var want: float = _areas.get_combined_minimum_size().y + gap
	_scroll.custom_minimum_size = Vector2(0, clampf(want, minf(60.0 * k, room), maxf(room, 60.0 * k)))
	_panel.reset_size()
	var info := _RM.window_info(world if world != null else self)
	var vis: Vector2 = info["vis"]
	var sz := _panel.get_combined_minimum_size()
	sz.x = w
	sz.y = minf(sz.y, h)
	_panel.size = sz
	_panel.position = Vector2((vis.x - sz.x) * 0.5, maxf((vis.y - sz.y) * 0.5, float(m["margin"]) * k))


func _fit_later(m: Dictionary, k: float, w: float, h: float, gap: int) -> void:
	_fit_queued = false
	if _panel == null:
		return
	for _pass in 2:  # wrapped text knows its height only after a layout pass: fit twice
		await get_tree().process_frame
		_fit(m, k, w, h, gap)


func _all_labels(node: Node) -> Array:
	var out: Array = []
	if node is Label:
		out.append(node)
	for c in node.get_children():
		out += _all_labels(c)
	return out


func _all_buttons(node: Node) -> Array:
	var out: Array = []
	if node is Button:
		out.append(node)
	for c in node.get_children():
		out += _all_buttons(c)
	return out
