extends Node
class_name HybridStoryUi

## Presentation of the wizard's story over the one simulation: a person to talk to, a dialogue panel, the dungeon underground and the
## Mastermind duel board. No rules live here: every action is a wizard op sent to the Python world (talk, choose, enter, dungeon_move,
## dungeon_interact, duel_begin, duel_guess, duel_abandon) and every picture is drawn from the reply. All pictures are labelled
## placeholders (coloured shapes), not final art.

const TALK_RANGE := 3
const TILE := 26
const KIND_COLOR := {"door": Color(0.55, 0.4, 0.25), "logs": Color(0.6, 0.6, 0.7), "sign": Color(0.9, 0.85, 0.6), "pickup": Color(0.95, 0.8, 0.2), "exit": Color(0.4, 0.9, 0.5)}
const COLOURS := [Color(0.9, 0.25, 0.2), Color(0.3, 0.55, 0.95), Color(0.3, 0.8, 0.35), Color(0.95, 0.85, 0.25), Color(0.7, 0.4, 0.9), Color(0.95, 0.6, 0.2)]
const COLOUR_NAMES := ["Red", "Blue", "Green", "Yellow", "Purple", "Orange"]

var world: Node
var layer: CanvasLayer
var dialog: PanelContainer
var dialog_title: Label
var dialog_text: RichTextLabel
var choices_box: VBoxContainer
var npc_id := ""
var dungeon: Control
var inv_label: Label
var msg_label: Label
var view: Dictionary = {}
var selected := 0          ## index into the inventory (number keys)
var spell := -1            ## 0 Flame, 1 Frost, 6 Vine (Q, W, R)
var duel: PanelContainer
var duel_slots: Array = []
var duel_hist: RichTextLabel
var duel_info: Label
var guess: Array = [-1, -1, -1, -1]
var last_status := ""


func setup(p_world: Node) -> void:
	world = p_world
	layer = CanvasLayer.new()
	layer.name = "StoryLayer"
	layer.layer = 14
	world.add_child(layer)
	_build_dialog()
	_build_dungeon()
	_build_duel()


# ---------------------------------------------------------------- panels

func _build_dialog() -> void:
	dialog = PanelContainer.new()
	dialog.name = "StoryDialog"
	dialog.position = Vector2(320, 380)
	dialog.custom_minimum_size = Vector2(640, 0)
	dialog.visible = false
	var v := VBoxContainer.new()
	dialog.add_child(v)
	dialog_title = Label.new()
	dialog_title.name = "DialogTitle"
	v.add_child(dialog_title)
	dialog_text = RichTextLabel.new()
	dialog_text.name = "DialogText"
	dialog_text.fit_content = true
	dialog_text.custom_minimum_size = Vector2(620, 70)
	dialog_text.bbcode_enabled = false
	v.add_child(dialog_text)
	choices_box = VBoxContainer.new()
	choices_box.name = "Choices"
	v.add_child(choices_box)
	var close := Button.new()
	close.name = "DialogClose"
	close.text = "Leave (Esc)"
	close.pressed.connect(close_dialog)
	v.add_child(close)
	layer.add_child(dialog)


func _build_dungeon() -> void:
	dungeon = Control.new()
	dungeon.name = "DungeonView"
	dungeon.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	dungeon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	dungeon.visible = false
	dungeon.draw.connect(_draw_dungeon)
	layer.add_child(dungeon)
	inv_label = Label.new()
	inv_label.name = "Inventory"
	inv_label.position = Vector2(12, 70)
	dungeon.add_child(inv_label)
	msg_label = Label.new()
	msg_label.name = "Message"
	msg_label.position = Vector2(12, 640)
	msg_label.custom_minimum_size = Vector2(1100, 0)
	msg_label.autowrap_mode = TextServer.AUTOWRAP_WORD
	dungeon.add_child(msg_label)


func _build_duel() -> void:
	duel = PanelContainer.new()
	duel.name = "DuelBoard"
	duel.position = Vector2(760, 90)
	duel.custom_minimum_size = Vector2(420, 0)
	duel.visible = false
	var v := VBoxContainer.new()
	duel.add_child(v)
	var t := Label.new()
	t.text = "The gallery warden's code (placeholder board)"
	v.add_child(t)
	duel_info = Label.new()
	duel_info.name = "DuelInfo"
	v.add_child(duel_info)
	var row := HBoxContainer.new()
	row.name = "Slots"
	v.add_child(row)
	for i in 4:
		var b := Button.new()
		b.name = "Slot%d" % i
		b.text = "?"
		b.custom_minimum_size = Vector2(60, 40)
		b.pressed.connect(_cycle_slot.bind(i))
		row.add_child(b)
		duel_slots.append(b)
	var palette := HBoxContainer.new()
	palette.name = "Palette"
	v.add_child(palette)
	for c in 6:
		var pb := Button.new()
		pb.name = "Colour%d" % c
		pb.text = COLOUR_NAMES[c].substr(0, 1)
		pb.modulate = COLOURS[c]
		pb.custom_minimum_size = Vector2(40, 34)
		pb.pressed.connect(_pick_colour.bind(c))
		palette.add_child(pb)
	var cast := Button.new()
	cast.name = "Cast"
	cast.text = "Cast this weave"
	cast.pressed.connect(submit_guess)
	v.add_child(cast)
	var leave := Button.new()
	leave.name = "DuelLeave"
	leave.text = "Step back"
	leave.pressed.connect(func() -> void: _op({"op": "duel_abandon"}))
	v.add_child(leave)
	duel_hist = RichTextLabel.new()
	duel_hist.name = "History"
	duel_hist.fit_content = true
	duel_hist.custom_minimum_size = Vector2(400, 120)
	v.add_child(duel_hist)
	layer.add_child(duel)


# ---------------------------------------------------------------- ops

func _op(message: Dictionary) -> Dictionary:
	var reply: Dictionary = world._sim.op(message)
	_apply_reply(reply)
	return reply


func _apply_reply(reply: Dictionary) -> void:
	if reply.has("view"):
		view = reply["view"] if typeof(reply["view"]) == TYPE_DICTIONARY else {}
	var d: Dictionary = reply.get("duel", {}) if typeof(reply.get("duel", {})) == TYPE_DICTIONARY else {}
	_show_duel(d)
	var inside := not view.is_empty()
	if dungeon.visible != inside:
		dungeon.visible = inside
		world._input_locked = inside or dialog.visible
	if inside:
		inv_label.text = "Inventory: %s   [number keys select, E use, Q/W/R spell Flame/Frost/Vine]\nSelected: %s  spell: %s" % [
			", ".join(PackedStringArray(view.get("inventory", []))), _selected_item(), str(spell) if spell >= 0 else "-"]
	if reply.has("text") and str(reply["text"]) != "":
		msg_label.text = str(reply["text"])
	last_status = str(reply.get("status", ""))
	dungeon.queue_redraw()


func refresh() -> void:
	_op({"op": "story_view"})


func _selected_item() -> String:
	var inv: Array = view.get("inventory", [])
	return str(inv[selected]) if selected < inv.size() else ""


# ---------------------------------------------------------------- dialogue

func person_at(screen_pos: Vector2) -> Dictionary:
	var xf: Transform2D = world.get_viewport().get_canvas_transform().affine_inverse()
	var wp: Vector2 = xf * screen_pos
	var tile := Vector2(floor(wp.x / world.TPX), floor(wp.y / world.TPX))
	for e in world._snapshot.get("entities", []):
		if str(e.get("class", "")) in ["npc", "landmark"] and Vector2(float(e["tx"]), float(e["ty"])) == tile:
			return e
	return {}


func try_click(screen_pos: Vector2) -> bool:
	if dungeon.visible:
		return false
	var e := person_at(screen_pos)
	if e.is_empty():
		return false
	use_entity(e)
	return true


func use_entity(e: Dictionary) -> void:
	var p: Dictionary = world._snapshot.get("player", {})
	var dist := absi(int(p.get("tx", 0)) - int(e["tx"])) + absi(int(p.get("ty", 0)) - int(e["ty"]))
	if str(e["class"]) == "npc":
		var reply := _op({"op": "talk", "npc": str(e["id"])})
		if str(reply.get("status", "")) == "ok":
			npc_id = str(e["id"])
			_show_dialog(reply)
		else:
			_toast("%s (%s)" % [str(e.get("label", "")), str(reply.get("reason", ""))])
	elif str(e["class"]) == "landmark":
		var reply := _op({"op": "enter", "dungeon": str(e["dungeon"])})
		if str(reply.get("status", "")) == "ok":
			close_dialog()
		else:
			_toast("The gallery is too far (%s)" % str(reply.get("reason", "")))


func nearest_interactive() -> Dictionary:
	var p: Dictionary = world._snapshot.get("player", {})
	var best := {}
	var bd := 999
	for e in world._snapshot.get("entities", []):
		if str(e.get("class", "")) in ["npc", "landmark"]:
			var d := absi(int(p.get("tx", 0)) - int(e["tx"])) + absi(int(p.get("ty", 0)) - int(e["ty"]))
			if d <= TALK_RANGE and d < bd:
				bd = d
				best = e
	return best


func _toast(text: String) -> void:
	if world.god != null:
		world.god._say(text)
	print("STORY toast: ", text)


func _show_dialog(reply: Dictionary) -> void:
	dialog.visible = true
	world._input_locked = true
	dialog_title.text = "%s  [%s]" % [str(reply.get("name", "")), str(reply.get("quest_status", ""))]
	dialog_text.text = "\n".join(PackedStringArray(reply.get("lines", [])))
	for c in choices_box.get_children():
		choices_box.remove_child(c)
		c.queue_free()
	for c in reply.get("choices", []):
		var b := Button.new()
		b.name = "Choice_%s" % str(c["id"])
		b.text = str(c["text"])
		b.disabled = not bool(c.get("available", false))
		b.pressed.connect(_choose.bind(str(c["id"])))
		choices_box.add_child(b)


func _choose(choice: String) -> void:
	var reply := _op({"op": "choose", "npc": npc_id, "choice": choice})
	if str(reply.get("status", "")) == "ok":
		dialog_text.text = str(reply.get("text", "")) + "\n\n" + "\n".join(PackedStringArray(reply.get("lines", [])))
		for c in choices_box.get_children():
			choices_box.remove_child(c)
			c.queue_free()
		for c in reply.get("choices", []):
			var b := Button.new()
			b.name = "Choice_%s" % str(c["id"])
			b.text = str(c["text"])
			b.disabled = not bool(c.get("available", false))
			b.pressed.connect(_choose.bind(str(c["id"])))
			choices_box.add_child(b)


func close_dialog() -> void:
	dialog.visible = false
	world._input_locked = dungeon.visible


# ---------------------------------------------------------------- dungeon

func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	var k: InputEventKey = event
	if dialog.visible and k.keycode == KEY_ESCAPE:
		close_dialog()
		get_viewport().set_input_as_handled()
		return
	if not dungeon.visible:
		if k.keycode == KEY_T:
			var reply := _op({"op": "treat"})
			_toast("Treatment: %s" % str(reply.get("status", reply.get("reason", ""))))
			get_viewport().set_input_as_handled()
			return
		if k.keycode == KEY_E:
			var e := nearest_interactive()
			if not e.is_empty():
				use_entity(e)
				get_viewport().set_input_as_handled()
		return
	if duel.visible:
		return
	match k.keycode:
		KEY_UP, KEY_W:
			_op({"op": "dungeon_move", "dx": 0, "dy": -1})
		KEY_DOWN, KEY_S:
			_op({"op": "dungeon_move", "dx": 0, "dy": 1})
		KEY_LEFT, KEY_A:
			_op({"op": "dungeon_move", "dx": -1, "dy": 0})
		KEY_RIGHT, KEY_D:
			_op({"op": "dungeon_move", "dx": 1, "dy": 0})
		KEY_E:
			interact_nearest()
		KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6, KEY_7, KEY_8:
			selected = k.keycode - KEY_1
			_op({"op": "story_view"})
		KEY_Q:
			spell = 0
			_op({"op": "story_view"})
		KEY_R:
			spell = 6
			_op({"op": "story_view"})
		KEY_F:
			spell = 1
			_op({"op": "story_view"})
		KEY_B:
			_op({"op": "duel_begin"})
	get_viewport().set_input_as_handled()


func interact_nearest() -> void:
	var pos: Array = view.get("pos", [0, 0])
	var best := {}
	var bd := 9
	for e in view.get("entities", []):
		var d := absi(int(pos[0]) - int(e["pos"][0])) + absi(int(pos[1]) - int(e["pos"][1]))
		if d <= 1 and d < bd:
			bd = d
			best = e
	if best.is_empty():
		msg_label.text = "Nothing within reach."
		return
	var msg := {"op": "dungeon_interact", "entity": str(best["id"])}
	if _selected_item() != "":
		msg["item"] = _selected_item()
	if spell >= 0:
		msg["spell"] = spell
	var reply := _op(msg)
	if str(reply.get("status", "")) == "duel_required":
		_op({"op": "duel_begin"})
	if reply.has("text") and str(reply["text"]) != "":
		msg_label.text = str(reply["text"])


func _draw_dungeon() -> void:
	if view.is_empty():
		return
	var rows: Array = view.get("rows", [])
	var origin := Vector2(20, 100)
	var vp := dungeon.get_viewport_rect().size
	dungeon.draw_rect(Rect2(Vector2.ZERO, vp), Color(0.04, 0.04, 0.06, 0.96), true)
	# the camera follows the wizard vertically: 4 rooms are taller than the screen
	var pos: Array = view.get("pos", [0, 0])
	var off := Vector2(vp.x * 0.5 - float(rows[0].length()) * TILE * 0.5, vp.y * 0.5 - float(pos[1]) * TILE)
	for y in rows.size():
		for x in String(rows[y]).length():
			var ch := String(rows[y])[x]
			var col := Color(0.12, 0.12, 0.15)
			if ch == ".":
				col = Color(0.32, 0.27, 0.22)
			elif ch == ":":
				col = Color(0.55, 0.5, 0.4)
			dungeon.draw_rect(Rect2(off + Vector2(x, y) * TILE, Vector2(TILE - 1, TILE - 1)), col, true)
	var font := ThemeDB.fallback_font
	for e in view.get("entities", []):
		var p := off + Vector2(float(e["pos"][0]), float(e["pos"][1])) * TILE
		var col: Color = KIND_COLOR.get(str(e["kind"]), Color(1, 0, 1))
		dungeon.draw_rect(Rect2(p + Vector2(3, 3), Vector2(TILE - 7, TILE - 7)), col, true)
		dungeon.draw_string(font, p + Vector2(6, TILE - 9), str(e["kind"]).substr(0, 1).to_upper(), HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color(0, 0, 0))
	var c := off + Vector2(float(pos[0]), float(pos[1])) * TILE + Vector2(TILE, TILE) * 0.5
	dungeon.draw_colored_polygon(PackedVector2Array([c + Vector2(0, -11), c + Vector2(10, 9), c + Vector2(-10, 9)]), Color(0.75, 0.6, 1.0))
	dungeon.draw_string(font, Vector2(200, 30), "%s - rooms solved: %s   (placeholder tiles)" % [str(view.get("name", "")), str(view.get("solved", []))], HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color(1, 1, 1))


# ---------------------------------------------------------------- duel

func _show_duel(d: Dictionary) -> void:
	duel.visible = not d.is_empty()
	if d.is_empty():
		return
	duel_info.text = "Casts %d of %d. Pick a colour, then a slot; or click a slot to cycle it." % [int(d.get("casts_used", 0)), int(d.get("max_casts", 0))]
	var lines: Array = []
	for g in d.get("guesses", []):
		var names: Array = []
		for c in g["guess"]:
			names.append(COLOUR_NAMES[int(c)])
		lines.append("%d: %s  exact %d, colour %d" % [int(g["cast"]), " ".join(PackedStringArray(names)), int(g["exact"]), int(g["colour_only"])])
	duel_hist.text = "\n".join(PackedStringArray(lines))


func _cycle_slot(i: int) -> void:
	guess[i] = (int(guess[i]) + 1) % 6
	_refresh_slots()


var _next_slot := 0


func _pick_colour(c: int) -> void:
	guess[_next_slot] = c
	_next_slot = (_next_slot + 1) % 4
	_refresh_slots()


func _refresh_slots() -> void:
	for i in 4:
		var b: Button = duel_slots[i]
		b.text = COLOUR_NAMES[int(guess[i])].substr(0, 1) if int(guess[i]) >= 0 else "?"
		b.modulate = COLOURS[int(guess[i])] if int(guess[i]) >= 0 else Color(1, 1, 1)


func submit_guess() -> void:
	for g in guess:
		if int(g) < 0:
			duel_info.text = "Fill all four slots first."
			return
	var reply := _op({"op": "duel_guess", "guess": guess.duplicate()})
	guess = [-1, -1, -1, -1]
	_next_slot = 0
	_refresh_slots()
	if str(reply.get("status", "")) in ["solved", "exhausted"]:
		duel.visible = false
		msg_label.text = "The warden yields (%s). Walk back out when you are ready." % str(reply.get("result", {}).get("outcome", ""))
