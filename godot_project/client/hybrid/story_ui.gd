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
var journal: PanelContainer  # lessons, spells, the quest and notes (J)
var journal_text: RichTextLabel
var _opening_pages: Array = []
var _opening_i := 0
var _opening_done := false
var hint: Label  # the objective line: where the quest giver is, what E or T will do here, the outbreak in this region
var _hint_acc := 0.0


func setup(p_world: Node) -> void:
	world = p_world
	layer = CanvasLayer.new()
	layer.name = "StoryLayer"
	layer.layer = 14
	world.add_child(layer)
	_build_dialog()
	_build_dungeon()
	_build_duel()
	_build_journal()
	hint = Label.new()
	hint.name = "StoryHint"
	hint.position = Vector2(16, 150)
	hint.custom_minimum_size = Vector2(760, 0)
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD
	hint.add_theme_font_size_override("font_size", 20)
	hint.add_theme_color_override("font_color", Color(1.0, 0.93, 0.55))
	hint.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.95))
	hint.add_theme_constant_override("outline_size", 5)
	hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(hint)


func _process(delta: float) -> void:
	_hint_acc += delta
	if _hint_acc < 0.25 or hint == null:
		return
	_hint_acc = 0.0
	_maybe_show_opening()
	if journal.visible:
		_refresh_journal()
	hint.text = objective_text()
	hint.visible = hint.text != "" and not dungeon.visible and (world.god == null or not world.god.active)


static func _dir(dx: int, dy: int) -> String:
	var ns := "N" if dy < -2 else ("S" if dy > 2 else "")
	var ew := "W" if dx < -2 else ("E" if dx > 2 else "")
	return ns + ew if ns + ew != "" else "here"


## One or two lines that tell the player what to do next, computed from the snapshot (never from quest text).
func objective_text() -> String:
	var snap: Dictionary = world._snapshot
	if snap.is_empty():
		return ""
	var p: Dictionary = snap.get("player", {})
	var px := int(p.get("tx", 0))
	var py := int(p.get("ty", 0))
	var lines: PackedStringArray = []
	var near := nearest_interactive()
	if not near.is_empty():
		if str(near.get("class", "")) in ["worker", "carrier", "unit"]:
			lines.append("Press E (or click, then Talk) to talk to %s." % person_name(str(near.get("id", ""))))
		elif str(near.get("class", "")) == "npc":
			lines.append("Press E (or click) to talk to %s." % str(near.get("label", "them")))
		else:
			lines.append("Press E to enter %s." % str(near.get("label", "the gallery")))
	else:
		var best := {}
		var bd := 1 << 30
		for e in snap.get("entities", []):
			if typeof(e) == TYPE_DICTIONARY and str(e.get("class", "")) == "npc" and bool(e.get("has_quest", false)):
				var d := absi(px - int(e["tx"])) + absi(py - int(e["ty"]))
				if d < bd:
					bd = d
					best = e
		if not best.is_empty():
			var what := str(best.get("hint", ""))
			if what == "":
				what = "Quest"
			lines.append("%s\n%s is %d tiles %s. Walk beside them and press E (or click, then Talk)." % [what, str(best.get("label", "someone")), bd, _dir(int(best["tx"]) - px, int(best["ty"]) - py)])
	var reg: Dictionary = snap.get("regions", {})
	var here := str(reg.get("player_region", ""))
	if int(reg.get("player_cubes", 0)) > 0:
		var imp: Dictionary = reg.get("impact", {}).get(here, {})
		var t := "%s here: %d of 3 marks (%s). Work runs at %d%%; %d workplaces slowed, %d closed." % [str(imp.get("label", "Outbreak")), int(reg.get("player_cubes", 0)),
			str(imp.get("clue", "")), int(round(float(imp.get("factor", 1.0)) * 100.0)), int(imp.get("slowed", 0)), int(imp.get("closed", 0))]
		if bool(reg.get("treating", false)):
			t += " Treating... %.0f s - stay inside the purple outline." % (float(reg.get("treat_left_ms", 0)) / 1000.0)
		elif int(reg.get("ready_in_ms", 0)) > 0:
			t += " Your strength returns in %.0f s." % (float(reg.get("ready_in_ms", 0)) / 1000.0)
		else:
			t += " Press T and stand still %.0f s to remove one mark." % (float(reg.get("treat_ms", 8000)) / 1000.0)
		lines.append(t)
	return "\n".join(lines)


# ---------------------------------------------------------------- panels

func _build_dialog() -> void:
	dialog = PanelContainer.new()
	dialog.name = "StoryDialog"
	dialog.position = Vector2(300, 360)
	dialog.custom_minimum_size = Vector2(760, 0)
	dialog.visible = false
	var box := StyleBoxFlat.new()  # an opaque, framed panel: the conversation must be readable over a busy settlement
	box.bg_color = Color(0.09, 0.07, 0.12, 0.96)
	box.border_color = Color(0.85, 0.7, 0.35)
	box.set_border_width_all(2)
	box.set_corner_radius_all(6)
	box.set_content_margin_all(12)
	dialog.add_theme_stylebox_override("panel", box)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	dialog.add_child(v)
	dialog_title = Label.new()
	dialog_title.name = "DialogTitle"
	dialog_title.add_theme_font_size_override("font_size", 22)
	dialog_title.add_theme_color_override("font_color", Color(1.0, 0.85, 0.45))
	v.add_child(dialog_title)
	dialog_text = RichTextLabel.new()
	dialog_text.name = "DialogText"
	dialog_text.fit_content = true
	dialog_text.custom_minimum_size = Vector2(736, 70)
	dialog_text.bbcode_enabled = false
	dialog_text.add_theme_font_size_override("normal_font_size", 18)
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
	# the figure is drawn above its tile and is small: accept a click on the body or the head, nearest person first (owner playtest:
	# a click on the miner landed on the mine behind him and only offered fire magic)
	var xf: Transform2D = world.get_viewport().get_canvas_transform().affine_inverse()
	var wp: Vector2 = xf * screen_pos
	var cell := wp / float(world.TPX)
	var best := {}
	var bd := 1.25
	for e in world._snapshot.get("entities", []):
		if typeof(e) != TYPE_DICTIONARY or not str(e.get("class", "")) in ["npc", "landmark"]:
			continue
		var centre := Vector2(float(e["tx"]) + 0.5, float(e["ty"]) + (0.0 if str(e.get("class", "")) == "npc" else 0.5))
		var d := centre.distance_to(cell)
		if d < bd:
			bd = d
			best = e
	return best


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
	if str(e["class"]) in ["npc", "worker", "carrier", "unit"]:
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


## The simulation's own workers, carriers and soldiers that have a character: {body id: {person_id, name, has_quest, quest_status}}.
func persons() -> Dictionary:
	var st = world._snapshot.get("story", {})
	if typeof(st) != TYPE_DICTIONARY:
		return {}
	var p = st.get("persons", {})
	return p if typeof(p) == TYPE_DICTIONARY else {}


func person_name(id: String) -> String:
	var rec = persons().get(id, null)
	return str(rec.get("name", "")) if typeof(rec) == TYPE_DICTIONARY else ""


## A drawn body (not one inside its building, not a corpse) that is a talk target.
func is_person_row(e: Dictionary) -> bool:
	return str(e.get("class", "")) in ["worker", "carrier", "unit"] and persons().has(str(e.get("id", ""))) and not bool(e.get("inside", false)) and bool(e.get("alive", true))


## The nearest thing E talks to or enters. The story's own people and entrances win over the simulation's workers, and a worker is not offered
## while a route hazard is within reach (E starts that duel there).
func nearest_interactive() -> Dictionary:
	var p: Dictionary = world._snapshot.get("player", {})
	var best := {}
	var bd := 999
	var best_body := {}
	var bbd := 999
	var hazard_near := false
	for e in world._snapshot.get("entities", []):
		var d := absi(int(p.get("tx", 0)) - int(e["tx"])) + absi(int(p.get("ty", 0)) - int(e["ty"]))
		if str(e.get("class", "")) in ["npc", "landmark"]:
			if d <= TALK_RANGE and d < bd:
				bd = d
				best = e
		elif str(e.get("kind", "")) == "hazard":
			if maxi(absi(int(p.get("tx", 0)) - int(e["tx"])), absi(int(p.get("ty", 0)) - int(e["ty"]))) <= TALK_RANGE:
				hazard_near = true
		elif d <= TALK_RANGE and d < bbd and is_person_row(e):
			bbd = d
			best_body = e
	if not best.is_empty() or hazard_near:
		return best
	return best_body


## Talk to a body by its entity id (the label's "Talk to" choice).
func talk_to(id: String) -> void:
	for e in world._snapshot.get("entities", []):
		if typeof(e) == TYPE_DICTIONARY and str(e.get("id", "")) == id:
			use_entity(e)
			return


func _toast(text: String) -> void:
	if world.god != null:
		world.god._say(text)
	print("STORY toast: ", text)


func _show_dialog(reply: Dictionary) -> void:
	dialog.visible = true
	world._input_locked = true
	dialog_title.text = str(reply.get("name", "")) if str(reply.get("quest_status", "")) == "" else "%s  [%s]" % [str(reply.get("name", "")), str(reply.get("quest_status", ""))]
	dialog_text.text = "\n".join(PackedStringArray(reply.get("lines", [])))
	for c in choices_box.get_children():
		choices_box.remove_child(c)
		c.queue_free()
	for c in reply.get("choices", []):
		var b := Button.new()
		b.name = "Choice_%s" % str(c["id"])
		b.text = str(c["text"])
		b.disabled = not bool(c.get("available", false))
		b.add_theme_font_size_override("font_size", 18)
		b.pressed.connect(_choose.bind(str(c["id"])))
		choices_box.add_child(b)


func _choose(choice: String) -> void:
	var reply := _op({"op": "choose", "npc": npc_id, "choice": choice})
	if str(reply.get("status", "")) == "ok" and reply.has("duel_lease"):
		var lease: Dictionary = reply["duel_lease"]
		close_dialog()
		world.open_story_duel(lease)  # the board takes over; the teacher answers when it finishes (show_follow_up)
		return
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
	if npc_id != "" and dialog.visible and _opening_pages.is_empty():
		world._sim.op({"op": "end_talk", "npc": npc_id})  # the person goes back to their routine
	npc_id = ""
	dialog.visible = false
	world._input_locked = dungeon.visible


# ---------------------------------------------------------------- dungeon

func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	var k: InputEventKey = event
	if dialog.visible and k.keycode == KEY_ESCAPE:
		if not _opening_pages.is_empty():
			finish_opening()
		else:
			close_dialog()
		get_viewport().set_input_as_handled()
		return
	if not dungeon.visible:
		if k.keycode == KEY_J and not dialog.visible:
			toggle_journal()
			get_viewport().set_input_as_handled()
			return
		if k.keycode == KEY_ESCAPE and journal.visible:
			journal.visible = false
			get_viewport().set_input_as_handled()
			return
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


# ---------------------------------------------------------------- the opening, the follow-up after a duel, the journal

## After a lesson duel the teacher answers: the server's `follow_up` is an ordinary talk reply.
func show_follow_up(follow: Variant) -> void:
	if typeof(follow) != TYPE_DICTIONARY or str(follow.get("status", "")) != "ok":
		return
	npc_id = str(follow.get("npc", ""))
	_show_dialog(follow)


func narrative() -> Dictionary:
	var st = world._snapshot.get("story", {})
	var n = st.get("narrative", {}) if typeof(st) == TYPE_DICTIONARY else {}
	return n if typeof(n) == TYPE_DICTIONARY else {}


func journal_data() -> Dictionary:
	var j = narrative().get("journal", {})
	return j if typeof(j) == TYPE_DICTIONARY else {}


func _maybe_show_opening() -> void:
	if _opening_done or dialog.visible or dungeon.visible or world._duel_open:
		return
	var lines: Array = journal_data().get("opening", [])
	if lines.is_empty():
		return
	_opening_pages = lines.duplicate()
	_opening_i = 0
	world.paused = true  # the world waits while the arrival is read
	_show_opening_page()


func _show_opening_page() -> void:
	dialog.visible = true
	world._input_locked = true
	dialog_title.text = "Arrival"
	dialog_text.text = str(_opening_pages[_opening_i])
	for c in choices_box.get_children():
		choices_box.remove_child(c)
		c.queue_free()
	var b := Button.new()
	b.name = "OpeningNext"
	b.text = "Continue" if _opening_i < _opening_pages.size() - 1 else "Begin"
	b.add_theme_font_size_override("font_size", 18)
	b.pressed.connect(_opening_next)
	choices_box.add_child(b)


func _opening_next() -> void:
	_opening_i += 1
	if _opening_i < _opening_pages.size():
		_show_opening_page()
		return
	finish_opening()


## Close the arrival text (also what a test calls): the simulation is told it has been seen, and time runs again.
func finish_opening() -> void:
	_opening_done = true
	if not _opening_pages.is_empty():
		_opening_pages = []
		dialog.visible = false
		world._input_locked = dungeon.visible
		world.paused = false
		world._sim.op({"op": "opening_done"})


func _build_journal() -> void:
	journal = PanelContainer.new()
	journal.name = "StoryJournal"
	journal.position = Vector2(60, 90)
	journal.custom_minimum_size = Vector2(560, 0)
	journal.visible = false
	var box := StyleBoxFlat.new()
	box.bg_color = Color(0.09, 0.07, 0.12, 0.96)
	box.border_color = Color(0.85, 0.7, 0.35)
	box.set_border_width_all(2)
	box.set_corner_radius_all(6)
	box.set_content_margin_all(12)
	journal.add_theme_stylebox_override("panel", box)
	var v := VBoxContainer.new()
	journal.add_child(v)
	var title := Label.new()
	title.text = "Journal  (J to close)"
	title.add_theme_font_size_override("font_size", 22)
	title.add_theme_color_override("font_color", Color(1.0, 0.85, 0.45))
	v.add_child(title)
	journal_text = RichTextLabel.new()
	journal_text.name = "JournalText"
	journal_text.fit_content = true
	journal_text.custom_minimum_size = Vector2(536, 120)
	journal_text.bbcode_enabled = false
	journal_text.add_theme_font_size_override("normal_font_size", 17)
	v.add_child(journal_text)
	layer.add_child(journal)


func journal_string() -> String:
	var j := journal_data()
	if j.is_empty():
		return "Nothing yet."
	var out: PackedStringArray = []
	var spells: Array = j.get("spells", [])
	out.append("Spells: %s   Weave: %d slots" % [", ".join(PackedStringArray(spells)) if not spells.is_empty() else "none yet", int(j.get("weave_size", 0))])
	out.append("")
	out.append("Lessons")
	for l in j.get("lessons", []):
		out.append("  [%s] %s" % ["x" if bool(l.get("done", false)) else " ", str(l.get("title", ""))])
	var nxt := str(j.get("next_lesson", ""))
	if nxt != "":
		out.append("  Next: " + nxt)
	var q: Dictionary = j.get("quest", {})
	if str(q.get("status", "none")) != "none":
		out.append("")
		out.append("%s  (%s)" % [str(q.get("title", "")), str(q.get("status", ""))])
		if str(q.get("objective", "")) != "":
			out.append("  " + str(q["objective"]))
	var notes: Array = j.get("notes", [])
	if not notes.is_empty():
		out.append("")
		out.append("Notes")
		for n in notes:
			out.append("  - " + str(n.get("text", "")))
	return "\n".join(out)


func _refresh_journal() -> void:
	journal_text.text = journal_string()


func toggle_journal() -> void:
	journal.visible = not journal.visible
	if journal.visible:
		_refresh_journal()
