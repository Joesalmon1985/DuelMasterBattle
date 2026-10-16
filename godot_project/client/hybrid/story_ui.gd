extends Node
class_name HybridStoryUi

## Presentation of the wizard's story over the one simulation: conversations, the arrival text, the journal, the dungeon underground and the Mastermind
## duel board. No rules live here: every action is a wizard op sent to the Python world (talk, choose, end_talk, enter, dungeon_move, ...) and every
## picture is drawn from the reply. Conversations, the arrival and the journal are DmbNarrativeCards (client/ui/narrative_card.gd): one look, sized
## in physical pixels, scrolling when long.
##
## The conversation lifecycle the server defines (narrative/conversation.py) is followed exactly: a reply has `ends`; when it does the card shows the
## final response with ONE acknowledge button (Continue, or Begin the duel); Escape, the Leave button and the acknowledge button all end the
## conversation on the server (`end_talk`), which releases the person to go back to their work. Nothing on the client guesses from a button's label.

const _VT = preload("res://client/scripts/visual_theme.gd")
const NarrativeCard = preload("res://client/ui/narrative_card.gd")

const TALK_RANGE := 3
const TILE := 26
const KIND_COLOR := {"door": Color(0.55, 0.4, 0.25), "logs": Color(0.6, 0.6, 0.7), "sign": Color(0.9, 0.85, 0.6), "pickup": Color(0.95, 0.8, 0.2), "exit": Color(0.4, 0.9, 0.5)}
const COLOURS := [Color(0.9, 0.25, 0.2), Color(0.3, 0.55, 0.95), Color(0.3, 0.8, 0.35), Color(0.95, 0.85, 0.25), Color(0.7, 0.4, 0.9), Color(0.95, 0.6, 0.2)]
const COLOUR_NAMES := ["Red", "Blue", "Green", "Yellow", "Purple", "Orange"]
const WORLDVIEW_NAMES := {"M": "Monarchist", "A": "Anarchist", "R": "Religious", "G": "Guildist", "S": "Arcane Supremacist", "D": "Druidic", "C": "Illuminated"}

var world: Node
var layer: CanvasLayer
var dialog_card: Control   # the conversation card (DmbNarrativeCard, kind sheet)
var dialog: Control        # the same card: `dialog.visible` is "a conversation is open"
var dialog_title: Label
var dialog_text: RichTextLabel
var choices_box: VBoxContainer
var opening_card: Control  # the arrival text (modal)
var journal: Control       # the journal (modal)
var journal_text: RichTextLabel
var npc_id := ""
var conv_ends := false
var conv_duel: Dictionary = {}  # a duel lease waiting for the acknowledge button
var _conv_ms := 0
var _conv_managed := false  # the server owns this conversation's lifecycle (narrative/conversation.py): its replies carry a `subtitle`; the legacy story people's do not
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
var _opening_pages: Array = []
var _opening_i := 0
var _opening_done := false
var _acc := 0.0


func setup(p_world: Node) -> void:
	world = p_world
	layer = CanvasLayer.new()
	layer.name = "StoryLayer"
	layer.layer = 14
	world.add_child(layer)
	dialog_card = NarrativeCard.new()
	layer.add_child(dialog_card)
	dialog_card.setup(world, "sheet", "StoryDialog")
	dialog_card.choice_pressed.connect(_choose)
	dialog_card.footer_pressed.connect(_on_footer)
	dialog = dialog_card
	dialog_title = dialog_card.title_label
	dialog_text = dialog_card.body_label
	choices_box = dialog_card.choices_box
	opening_card = NarrativeCard.new()
	layer.add_child(opening_card)
	opening_card.setup(world, "modal", "StoryArrival")
	opening_card.footer_pressed.connect(_on_opening_footer)
	journal = NarrativeCard.new()
	layer.add_child(journal)
	journal.setup(world, "modal", "StoryJournal")
	journal.footer_pressed.connect(func(_id: String) -> void: set_journal_visible(false))
	journal_text = journal.body_label
	_build_dungeon()
	_build_duel()


func _process(delta: float) -> void:
	_acc += delta
	if _acc < 0.25:
		return
	_acc = 0.0
	_maybe_show_opening()
	if journal.visible:
		journal_text.text = journal_string()
	_check_conversation_alive()


## True when a card (conversation, arrival, journal) owns the screen.
func covering() -> bool:
	return dialog.visible or opening_card.visible or journal.visible or dungeon.visible


static func _dir(dx: int, dy: int) -> String:
	var ns := "north" if dy < -2 else ("south" if dy > 2 else "")
	var ew := "west" if dx < -2 else ("east" if dx > 2 else "")
	return (ns + ("-" if ns != "" and ew != "" else "") + ew) if ns + ew != "" else "here"


## The HUD's objective: the outbreak in this region, else the journal's current objective (the next lesson or the open quest), else the legacy
## story fixture's quest giver; plus what E does if someone is within reach.
func objective_text() -> String:
	var snap: Dictionary = world._snapshot
	if snap.is_empty():
		return ""
	var p: Dictionary = snap.get("player", {})
	var px := int(p.get("tx", 0))
	var py := int(p.get("ty", 0))
	var lines: PackedStringArray = []
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
	var goal := str(journal_data().get("objective", ""))
	if goal != "":
		lines.append(goal)
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
			lines.append("%s is %d tiles %s." % [str(best.get("label", "Someone")), bd, _dir(int(best["tx"]) - px, int(best["ty"]) - py)])
	var near := nearest_interactive()
	if not near.is_empty():
		var who := str(near.get("label", "them"))
		if str(near.get("class", "")) in ["worker", "carrier", "unit"]:
			who = person_name(str(near.get("id", "")))
		lines.append(("Press E to enter %s." if str(near.get("class", "")) == "landmark" else "Press E to talk to %s.") % who)
	return "\n".join(lines)



# ---------------------------------------------------------------- panels

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

## Clicks on the dungeon entrance. People, buildings and trees are picked by the inspect panel (wizard_labels.gd).
func person_at(screen_pos: Vector2) -> Dictionary:
	var xf: Transform2D = world.get_viewport().get_canvas_transform().affine_inverse()
	var cell: Vector2 = (xf * screen_pos) / float(world.TPX)
	var best := {}
	var bd := 1.25
	for e in world._snapshot.get("entities", []):
		if typeof(e) != TYPE_DICTIONARY or str(e.get("class", "")) != "landmark":
			continue
		var d := Vector2(float(e["tx"]) + 0.5, float(e["ty"]) + 0.5).distance_to(cell)
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
	if str(e["class"]) in ["npc", "worker", "carrier", "unit"]:
		var reply := _op({"op": "talk", "npc": str(e["id"])})
		if str(reply.get("status", "")) == "ok":
			_conv_ms = int(world._snapshot.get("game_ms", 0))
			_show_dialog(reply)
		else:
			_toast(_why(str(reply.get("reason", "")), e))
	elif str(e["class"]) == "landmark":
		var reply := _op({"op": "enter", "dungeon": str(e["dungeon"])})
		if str(reply.get("status", "")) == "ok":
			close_dialog()
		else:
			_toast("The gallery is too far (%s)" % str(reply.get("reason", "")))


func _why(reason: String, e: Dictionary) -> String:
	var who := person_name(str(e.get("id", ""))) if person_name(str(e.get("id", ""))) != "" else str(e.get("label", "them"))
	match reason:
		"too_far":
			return "Walk closer to talk to %s." % who
		"duel_open":
			return "Finish the duel first."
		"dead":
			return "%s is gone." % who
		"no_such_person":
			return "%s is not here any more." % who
	return "%s cannot talk now (%s)." % [who, reason]


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
			if bool(e.get("dead", false)) or bool(e.get("hostile", false)):
				continue  # nobody to talk to: the mentor's body, the stranger
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
	print("STORY toast: ", text)
	if world.hud != null:
		world.hud.flash(text)
	elif world.god != null:
		world.god._say(text)


## What a reply says: the person's answer to the last choice, then what they say next.
func reply_text(reply: Dictionary) -> String:
	var parts: PackedStringArray = []
	if str(reply.get("text", "")) != "":
		parts.append(str(reply["text"]))
	var lines: Array = reply.get("lines", [])
	if not lines.is_empty():
		parts.append("\n\n".join(PackedStringArray(lines)))
	return "\n\n".join(parts)


func _show_dialog(reply: Dictionary) -> void:
	npc_id = str(reply.get("npc", npc_id))
	_conv_managed = reply.has("subtitle")
	conv_ends = bool(reply.get("ends", false))
	var lease = reply.get("duel_lease", {})
	conv_duel = lease if typeof(lease) == TYPE_DICTIONARY else {}
	var choices: Array = []
	for c in reply.get("choices", []):
		choices.append({"id": str(c["id"]), "text": str(c["text"]), "disabled": not bool(c.get("available", true))})
	var footer: Array = []
	if conv_ends:
		footer.append({"id": "ack", "text": "Begin the duel" if not conv_duel.is_empty() else "Continue", "kind": "primary"})
	else:
		footer.append({"id": "leave", "text": "Leave (Esc)"})
	dialog_card.show_card(str(reply.get("name", "")), str(reply.get("subtitle", "")), reply_text(reply), choices, footer)
	world._input_locked = true


func _choose(choice: String) -> void:
	var reply := _op({"op": "choose", "npc": npc_id, "choice": choice})
	if str(reply.get("status", "")) == "ok":
		_show_dialog(reply)
	else:
		_toast("That is no longer possible (%s)." % str(reply.get("reason", "")))


func _on_footer(id: String) -> void:
	if id == "ack":
		acknowledge()
	else:
		close_dialog()


## The final response has been read: end the conversation, then (if one was waiting) open the duel board.
func acknowledge() -> void:
	var lease := conv_duel
	close_dialog(false)
	if not lease.is_empty():
		world.open_story_duel(lease)


## The one way a conversation closes on the client: the server is told (the person is released), a duel that was waiting for its acknowledgement is
## abandoned unless `abandon_duel` is false, and control returns to the game.
func close_dialog(abandon_duel := true) -> void:
	if npc_id != "" and dialog.visible:
		if abandon_duel and not conv_duel.is_empty():
			world._sim.op({"op": "duel_abandon"})
		world._sim.op({"op": "end_talk", "npc": npc_id, "reason": "closed"})
	npc_id = ""
	conv_ends = false
	conv_duel = {}
	dialog_card.hide_card()
	world._input_locked = dungeon.visible or opening_card.visible


## The server can end a conversation (the person walked off the map, died, was removed, the talk went idle): the card closes with it.
func _check_conversation_alive() -> void:
	if not dialog.visible or npc_id == "" or world._duel_open or not _conv_managed:
		return
	var snap_ms := int(world._snapshot.get("game_ms", 0))
	if snap_ms <= _conv_ms + 1500:
		return  # no snapshot from after the conversation began yet
	if not (journal_data().get("talking", []) as Array).has(npc_id):
		npc_id = ""
		conv_ends = false
		conv_duel = {}
		dialog_card.hide_card()
		world._input_locked = dungeon.visible
		_toast("The conversation ended.")


# ---------------------------------------------------------------- keys

func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	var k: InputEventKey = event
	if opening_card.visible:  # the arrival text: Escape skips it (the Skip button does the same), Enter continues
		if k.keycode == KEY_ESCAPE:
			finish_opening()
		elif k.keycode in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
			opening_card.activate_primary()
		get_viewport().set_input_as_handled()  # the arrival is modal: no other key reaches the game behind it
		return
	if dialog.visible:  # a conversation owns the keyboard: Escape leaves (or acknowledges), Enter takes the primary button, 1-9 pick a reply
		if k.keycode == KEY_ESCAPE:
			if conv_ends:
				acknowledge()
			else:
				close_dialog()
		elif k.keycode in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
			dialog_card.activate_primary()
		elif k.keycode >= KEY_1 and k.keycode <= KEY_9:
			dialog_card.activate_choice_index(k.keycode - KEY_1)
		get_viewport().set_input_as_handled()  # a conversation is modal: E, T and the rest do not reach the game behind it
		return
	if journal.visible:
		if k.keycode == KEY_ESCAPE or k.keycode == KEY_J:
			set_journal_visible(false)
		get_viewport().set_input_as_handled()
		return
	if not dungeon.visible:
		if k.keycode == KEY_J:
			set_journal_visible(true)
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

## After a lesson duel the teacher answers: the server's `follow_up` is an ordinary talk reply (it begins a new conversation with the same person).
func show_follow_up(follow: Variant) -> void:
	if typeof(follow) != TYPE_DICTIONARY or str(follow.get("status", "")) != "ok":
		return
	_conv_ms = int(world._snapshot.get("game_ms", 0))
	_show_dialog(follow)


func narrative() -> Dictionary:
	var st = world._snapshot.get("story", {})
	var n = st.get("narrative", {}) if typeof(st) == TYPE_DICTIONARY else {}
	return n if typeof(n) == TYPE_DICTIONARY else {}


func journal_data() -> Dictionary:
	var j = narrative().get("journal", {})
	return j if typeof(j) == TYPE_DICTIONARY else {}


func _maybe_show_opening() -> void:
	if _opening_done or dialog.visible or dungeon.visible or world._duel_open or opening_card.visible:
		return
	var lines: Array = journal_data().get("opening", [])
	if lines.is_empty():
		return
	_opening_pages = lines.duplicate()
	_opening_i = 0
	world.paused = true  # the world waits while the arrival is read
	_show_opening_page()


func _show_opening_page() -> void:
	world._input_locked = true
	var dots := ""
	for i in _opening_pages.size():
		dots += ("o " if i == _opening_i else ". ").replace("o", "\u25CF").replace(".", "\u25CB")
	var last := _opening_i >= _opening_pages.size() - 1
	opening_card.show_card("Arrival", "", str(_opening_pages[_opening_i]), [],
		[{"id": "skip", "text": "Skip"}, {"id": "next", "text": "Begin" if last else "Continue", "kind": "primary"}],
		"%s   %d / %d" % [dots.strip_edges(), _opening_i + 1, _opening_pages.size()])


func _on_opening_footer(id: String) -> void:
	if id == "skip":
		finish_opening()
		return
	_opening_i += 1
	if _opening_i < _opening_pages.size():
		_show_opening_page()
	else:
		finish_opening()


## Close the arrival text (Skip, Escape and Begin all end here, and so does a test): the simulation is told it has been seen, and time runs again.
func finish_opening() -> void:
	_opening_done = true
	if not _opening_pages.is_empty():
		_opening_pages = []
		opening_card.hide_card()
		world._input_locked = dungeon.visible or dialog.visible
		world.paused = false
		world._sim.op({"op": "opening_done"})
	else:
		opening_card.hide_card()


## The Game Over screen's New game: nothing of the old world's panels survives (the arrival text will show again for the new one).
func reset_for_new_game() -> void:
	_opening_done = false
	_opening_pages = []
	_opening_i = 0
	opening_card.hide_card()
	journal.hide_card()
	npc_id = ""
	conv_ends = false
	conv_duel = {}
	view = {}
	dungeon.visible = false
	_progress_reset()


func _progress_reset() -> void:
	if world.has_method("reset_progress_notice"):
		world.reset_progress_notice()


func journal_string() -> String:
	var j := journal_data()
	if j.is_empty():
		return "Nothing yet."
	var out: PackedStringArray = []
	var goal := str(j.get("objective", ""))
	if goal != "":
		out.append("OBJECTIVE")
		out.append("  " + goal)
		out.append("")
	var spells: Array = j.get("spells", [])
	out.append("Spells: %s.  Weave: %d slots." % [", ".join(PackedStringArray(spells)) if not spells.is_empty() else "none yet", int(j.get("weave_size", 0))])
	out.append("")
	out.append("LESSONS")
	for l in j.get("lessons", []):
		out.append("  [%s] %s" % ["x" if bool(l.get("done", false)) else " ", str(l.get("title", ""))])
	var nxt := str(j.get("next_lesson", ""))
	if nxt != "":
		out.append("  Next: " + nxt)
	for q in j.get("quests", []):
		out.append("")
		out.append("%s  (%s)" % [str(q.get("title", "")).to_upper(), str(q.get("status", ""))])
		if str(q.get("objective", "")) != "":
			out.append("  " + str(q["objective"]))
		for who in q.get("people", []):
			out.append("  - %s, %s: %s" % [str(who.get("name", "")), str(who.get("occupation", "")), str(who.get("where", ""))])
	var notes: Array = j.get("notes", [])
	if not notes.is_empty():
		out.append("")
		out.append("NOTES")
		for n in notes:
			out.append("  - " + str(n.get("text", "")))
	var c = j.get("campaign", {})
	if typeof(c) == TYPE_DICTIONARY and not (c as Dictionary).is_empty():
		var asp = c.get("aspects", {})
		if typeof(asp) == TYPE_DICTIONARY and not (asp as Dictionary).is_empty():
			out.append("")
			out.append("ASPECTS")
			var bits: PackedStringArray = []
			for a in ["reason", "empathy", "authority", "guile", "resolve", "curiosity", "wonder"]:
				bits.append("%s %d" % [str(a).capitalize(), int(asp.get(a, 0))])
			out.append("  " + ", ".join(bits))
		var wv = c.get("worldview", {})
		if typeof(wv) == TYPE_DICTIONARY and not (wv as Dictionary).is_empty():
			var lean := ""
			var best := 0
			for code in WORLDVIEW_NAMES:
				if int(wv.get(code, 0)) > best:
					best = int(wv[code])
					lean = str(WORLDVIEW_NAMES[code])
			if lean != "":
				out.append("")
				out.append("LEANINGS")
				var parts: PackedStringArray = []
				for code in WORLDVIEW_NAMES:
					if int(wv.get(code, 0)) != 0:
						parts.append("%s %d" % [str(WORLDVIEW_NAMES[code]), int(wv[code])])
				out.append("  Leaning: %s (%s)" % [lean, ", ".join(parts)])
	return "\n".join(out)


func set_journal_visible(on: bool) -> void:
	if on and world.mp:
		return  # Wizard World has no journal panel (plan amendment 11)
	if on:
		journal.show_card("Journal", "", journal_string(), [], [{"id": "close", "text": "Close (J)", "kind": "primary"}])
	else:
		journal.hide_card()


func toggle_journal() -> void:
	set_journal_visible(not journal.visible)
