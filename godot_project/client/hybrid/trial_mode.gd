extends Node
## The Trial of Champions on the client (plan M5): "zone mode". While this wizard is inside, the hybrid scene shows a Deathtrap Dungeon zone built by
## the Overworld's legacy tile builder (cave tiles, props, creatures, pickups, people) instead of the hex world. Nothing here decides anything: every
## step goes to the host (`trial_move`, a refusal snaps the avatar back), a look, a pickup, a talk and a fight are host ops (`trial_interact`,
## `trial_choose`), a creature is a Ward Duel lease on the real board, the other wizard and the bodies in the zone are drawn from the host's view,
## and the pocket strip shows what the wizard carries. `world.trial_mode` is this node; `active` is "inside".

const NarrativeCard = preload("res://client/ui/narrative_card.gd")
const _VT = preload("res://client/scripts/visual_theme.gd")

var world: Node
var active := false
var view: Dictionary = {}  # the host's `trial` view (wizard_rts/trial/run.py `view`)
var card: Control  # the Trial's card: a reading, a person's lines, a riddle, the way out (DmbNarrativeCard, kind sheet)
var strip: Label  # the pocket strip
var leave_btn: Button
var overlay: Node2D  # bodies and the resurrection channel, above the tile sprites
var _pending_lease: Dictionary = {}  # a creature's lease waiting for "Begin the duel"
var _card_entity := ""  # the entity the open card belongs to (its choices go to `trial_choose`)
var _card_kind := ""  # "prompt", "lease", "body", "leave", "text"
var _others: Dictionary = {}  # seat -> actor key of another wizard drawn in this zone
var _travel_t := 0.0
var _host_pos := Vector2i(-1, -1)  # where the host last said we stand (its reply to our step)
var _seen_pos := Vector2i(-1, -1)  # a host position that differed from ours on the previous poll (a stale poll is ignored; a repeat is believed)
var last_reply: Dictionary = {}  # the last interaction reply (tests)
var _trace := OS.get_environment("HYBRID_SHOT_DIR") != ""  # headed tests: print every validated step


func setup(p_world: Node) -> void:
	world = p_world
	var layer := CanvasLayer.new()
	layer.name = "TrialLayer"
	layer.layer = 7
	add_child(layer)
	strip = Label.new()
	strip.name = "PocketStrip"
	strip.set_anchors_preset(Control.PRESET_TOP_LEFT)
	strip.offset_left = 14
	strip.offset_right = 520
	strip.offset_top = 150
	strip.offset_bottom = 230
	strip.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	strip.add_theme_font_size_override("font_size", 19)
	strip.add_theme_color_override("font_color", Color(0.95, 0.9, 0.75))
	strip.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	strip.add_theme_constant_override("outline_size", 5)
	strip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	strip.visible = false
	layer.add_child(strip)
	leave_btn = Button.new()
	leave_btn.name = "LeaveTrialButton"
	leave_btn.text = "Leave the Trial"
	leave_btn.focus_mode = Control.FOCUS_NONE
	leave_btn.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	leave_btn.offset_left = -16 - 250
	leave_btn.offset_right = -16
	leave_btn.offset_top = 150
	leave_btn.offset_bottom = 150 + 62
	leave_btn.add_theme_font_size_override("font_size", 20)
	leave_btn.add_theme_stylebox_override("normal", _VT.gem_button_style())
	leave_btn.add_theme_stylebox_override("hover", _VT.gem_button_style())
	leave_btn.add_theme_stylebox_override("pressed", _VT.gem_button_style(true))
	leave_btn.add_theme_color_override("font_color", _VT.COLOR_ACCENT_GOLD)
	leave_btn.pressed.connect(_offer_leave)
	leave_btn.visible = false
	layer.add_child(leave_btn)
	card = NarrativeCard.new()
	layer.add_child(card)
	card.setup(world, "sheet", "TrialCard")
	card.choice_pressed.connect(_on_choice)
	card.footer_pressed.connect(_on_footer)
	overlay = Node2D.new()
	overlay.name = "TrialOverlay"
	overlay.z_index = 4
	overlay.draw.connect(_draw_overlay)
	world.add_child(overlay)


func _process(delta: float) -> void:
	if not active:
		return
	overlay.queue_redraw()
	if _travel_t > 0.0:
		_travel_t -= delta


func covering() -> bool:
	return card != null and card.visible


# ---------------------------------------------------------------- in and out

## Through the gate (the landmark on the map, tapped or E). The host decides: too far, grounded, a duel open, dead.
func enter() -> Dictionary:
	var reply: Dictionary = world._sim.op({"op": "trial_enter"})
	if str(reply.get("status", "")) == "ok":
		_enter_zone(reply.get("view", {}))
		_toast("The doors of the Trial close behind you.", 4.0)
	else:
		match str(reply.get("reason", "")):
			"too_far":
				_toast("Walk up to the gate first.")
			"grounded":
				_toast("%s: %s" % [str(reply.get("name", "Your mother")), str(reply.get("line", "Not one step further."))], 6.0)
			"duel_open":
				_toast("Finish the duel first.")
			"dead":
				pass
			_:
				_toast("The gate does not open (%s)." % str(reply.get("reason", "")))
	return reply


func _enter_zone(v: Dictionary) -> void:
	if v.is_empty():
		return
	var zone := str(v.get("zone", ""))
	var pos: Array = v.get("pos", [10, 11])
	if not active:
		active = true
		if world.wizard_labels != null:
			world.wizard_labels.close()
		if world.story_ui != null:
			world.story_ui.close_dialog()
		for pid in world._mp_players.keys():  # the hex world's avatars go; the zone shows who is in it from the host's view
			world.remove_actor("lan:" + pid)
		world._mp_players.clear()
		world._touch.set_action_visible(true)
		strip.visible = true
	elif zone == world.area_id:
		_apply_view(v)
		_sync_pose(v)
		return
	for k in _others.values():
		world.remove_actor(k)
	_others.clear()
	_host_pos = Vector2i(int(pos[0]), int(pos[1]))
	_seen_pos = Vector2i(-1, -1)
	world.load_area(zone, Vector2i(int(pos[0]), int(pos[1])), str(v.get("facing", "up")))
	_free_camera()  # load_area limited the camera to the small zone: it must follow the wizard (and zoom on them) wherever they stand
	world._clear_semantic_labels()  # the legacy semantic layer stays out: the host owns every interaction here
	for e in world._entities:
		e.erase("semantic")
	world._hud_area_lbl.text = str(v.get("name", "The Trial"))
	_apply_view(v)
	world.queue_redraw()


## The host's view each poll: taken and defeated things vanish, the other wizard moves, the pocket strip follows; an empty view means "outside".
func apply(v: Dictionary) -> void:
	if v.is_empty():
		if active:
			var keep := _card_kind == "champion" and card.visible
			_exit_zone()
			if keep:
				world._input_locked = true  # the champion reads the last page over the daylight
				card.visible = true
		return
	if not active or str(v.get("zone", "")) != world.area_id:
		_enter_zone(v)  # resurrected inside, or the picture fell behind the host
		return
	_apply_view(v)
	_sync_pose(v)


## The host's position wins over ours, but a poll that left the host before our last step is older than what we know (its reply can even arrive
## while the step's own call waits): a differing position is believed only when two polls in a row say it (a resurrection stood us up elsewhere).
func _sync_pose(v: Dictionary) -> void:
	if world._moving or world._dead_mode:
		return
	var hp := Vector2i(int(v["pos"][0]), int(v["pos"][1]))
	if hp == world._john_pos:
		_seen_pos = Vector2i(-1, -1)
		return
	if hp == _seen_pos:  # twice in a row: not a poll that left before our last step (those are answered inside the step's own call)
		world.set_john_pos(hp, str(v.get("facing", world._john_facing)))
		_host_pos = hp
		_seen_pos = Vector2i(-1, -1)
	else:
		_seen_pos = hp


func _apply_view(v: Dictionary) -> void:
	view = v
	var present := {}
	for e in v.get("entities", []):
		present[str(e["id"])] = true
	for e in world._entities:
		var id := str(e.get("id", ""))
		if id == "" or str(e.get("kind", "")) in ["exit", "trigger"]:
			continue
		var show := present.has(id)
		var node = e.get("node")
		if node != null and is_instance_valid(node):
			node.visible = show
		var p := Vector2i(int(e["pos"][0]), int(e["pos"][1]))
		if show:
			if not world._entity_at.has(p):
				world._entity_at[p] = e
		elif world._entity_at.has(p) and str(world._entity_at[p].get("id", "")) == id:
			world._entity_at.erase(p)
	var seen := {}
	for o in v.get("others", []):
		var seat := str(o["seat"])
		if bool(o.get("dead", false)):
			continue  # a dead wizard is a body (drawn from `bodies`), not a standing figure
		seen[seat] = true
		var tile := Vector2i(int(o["x"]), int(o["y"]))
		var key := "trial:" + seat
		var node = world.actor(key)
		if node == null or not is_instance_valid(node):
			var idx := maxi(0, int(seat.substr(1)) - 2)
			node = world.spawn_actor(key, world.MP_SPRITES[idx % world.MP_SPRITES.size()], tile, str(o.get("facing", "down")))
			node.set_meta("tile", tile)
			_others[seat] = key
			var lbl := Label.new()
			lbl.name = "Name"
			lbl.text = str(o.get("name", seat))
			lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			lbl.add_theme_font_size_override("font_size", 18)
			lbl.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
			lbl.add_theme_constant_override("outline_size", 5)
			lbl.size = Vector2(160, 24)
			lbl.scale = Vector2(1.0 / maxf(node.scale.x, 0.01), 1.0 / maxf(node.scale.y, 0.01))
			lbl.position = Vector2(8.0 - 80.0 / maxf(node.scale.x, 0.01), -7.0)
			node.add_child(lbl)
		else:
			var prev: Vector2i = node.get_meta("tile", tile)
			if prev != tile:
				node.set_meta("tile", tile)
				world.move_actor(key, tile, world.POLL_SECONDS)
	for seat in _others.keys():
		if not seen.has(seat):
			world.remove_actor(_others[seat])
			_others.erase(seat)
	strip.text = strip_text(v)
	leave_btn.visible = bool(v.get("at_door", false)) and not world._dead_mode and not world._duel_open
	world._update_prompt()


func strip_text(v: Dictionary) -> String:
	var parts: PackedStringArray = []
	var names: PackedStringArray = []
	for p in v.get("pockets", []):
		names.append(str(p.get("name", p.get("id", ""))))
	parts.append("Pockets: " + (", ".join(names) if not names.is_empty() else "empty"))
	var gems: Array = v.get("gems", [])
	if not gems.is_empty():
		parts.append("Gems: " + ", ".join(PackedStringArray(gems.map(func(g): return str(g)))))
	var conds: Array = v.get("conditions", [])
	if not conds.is_empty():
		parts.append(", ".join(PackedStringArray(conds.map(func(c): return str(c).capitalize()))))
	return "\n".join(parts)


## The zone's tile under the pointer holds something within reach: use it. (The world's tap-to-inspect does not apply inside.)
func tap(screen_pos: Vector2) -> bool:
	if not active or card.visible or world._duel_open or world._dead_mode:
		return false
	var xf: Transform2D = world.get_viewport().get_canvas_transform().affine_inverse()
	var cell: Vector2 = (xf * screen_pos) / float(world.TPX)
	var t := Vector2i(int(floor(cell.x)), int(floor(cell.y)))
	var target := _target_at(t)
	if target == "":
		return false
	var d := absi(t.x - world._john_pos.x) + absi(t.y - world._john_pos.y)
	if d > 1:
		_toast("Walk closer.")
		return true
	interact_with(target)
	return true


func _target_at(t: Vector2i) -> String:
	for e in view.get("entities", []):
		if int(e["pos"][0]) == t.x and int(e["pos"][1]) == t.y:
			return str(e["id"])
	for b in view.get("bodies", []):
		if int(b["x"]) == t.x and int(b["y"]) == t.y:
			return "body:" + str(b["seat"])
	return ""


## The action button and E: what the wizard faces, else the nearest thing within a tile, else the door when standing in it.
func interact() -> void:
	if not active or card.visible or world._duel_open or world._moving or world._dead_mode:
		return
	var hv: Dictionary = world._sim.op({"op": "trial_view"}).get("view", {})
	if not hv.is_empty():
		var hp := Vector2i(int(hv["pos"][0]), int(hv["pos"][1]))
		if hp != world._john_pos:
			if _trace:
				print("TRIAL interact: host at %s, we at %s" % [str(hp), str(world._john_pos)])
			world.set_john_pos(hp)
			_host_pos = hp
		_apply_view(hv)
	var target := _target_at(world.facing_pos())
	if target == "":
		target = _target_at(world._john_pos)
	if target == "":
		var best := 2
		for e in view.get("entities", []):
			var d := absi(int(e["pos"][0]) - world._john_pos.x) + absi(int(e["pos"][1]) - world._john_pos.y)
			if d < best:
				best = d
				target = str(e["id"])
		for b in view.get("bodies", []):
			var d := absi(int(b["x"]) - world._john_pos.x) + absi(int(b["y"]) - world._john_pos.y)
			if d < best:
				best = d
				target = "body:" + str(b["seat"])
	if target == "":
		if bool(view.get("at_door", false)):
			_offer_leave()
		else:
			_toast("Nothing within reach.")
		return
	interact_with(target)


func interact_with(id: String) -> void:
	var reply: Dictionary = world._sim.op({"op": "trial_interact", "entity": id})
	last_reply = reply
	_handle(id, reply)


func _handle(id: String, reply: Dictionary) -> void:
	var st := str(reply.get("status", ""))
	if st == "started":  # a creature: its introduction, then the real board
		_pending_lease = reply.get("duel_lease", {})
		_card_entity = id
		_card_kind = "lease"
		_show(str(reply.get("name", "")), "lethal: there is no losing and walking away" if bool(reply.get("lethal", false)) else "", str(reply.get("intro", "")), [],
			[{"id": "begin", "text": "Begin the duel", "kind": "primary"}, {"id": "close", "text": "Step back"}])
		return
	if st != "ok":
		match str(reply.get("reason", "")):
			"too_far":
				_toast("Walk closer.")
			"no_such_entity":
				_toast("There is nothing there now.")
			"duel_open":
				_toast("Finish the duel first.")
			"pockets_full":
				_toast("Your pockets are full.")
			"dead":
				pass
			_:
				_toast("Not now (%s)." % str(reply.get("reason", "")))
		return
	if reply.has("taken"):
		_hide_entity(str(reply["taken"]))
	var item = reply.get("item", null)
	if typeof(item) == TYPE_DICTIONARY:
		world._sfx().fracture(1)
		_toast("Taken: %s" % str(item.get("name", item.get("id", ""))), 3.5)
	if reply.has("took") and not (reply["took"] as Array).is_empty():
		_toast("Taken: " + ", ".join(PackedStringArray(reply["took"])), 3.5)
	if reply.has("weave"):
		_toast("Your weave grows: %d places." % int(reply["weave"]), 4.0)
	if reply.has("spell"):
		_toast("A new colour: %s." % _colour_name(int(reply["spell"])), 4.0)
	var text := _reply_text(reply)
	var title := _title_of(id, reply)
	if reply.has("prompt") and typeof(reply["prompt"]) == TYPE_DICTIONARY:
		_show_prompt(id, reply["prompt"], text, title)
	elif id.begins_with("body:") and _can_resurrect(id):
		_card_entity = id
		_card_kind = "body"
		_show(title, "", text, [{"id": "resurrect", "text": "Bring them back"}], [{"id": "close", "text": "Leave them", "kind": "primary"}])
	elif text != "":
		_card_entity = id
		_card_kind = "text"
		_show(title, "", text, [], [{"id": "close", "text": "Continue", "kind": "primary"}])
	_refresh_view()


const COLOUR_NAMES := {0: "Flame", 1: "Frost", 3: "Stone", 4: "Light", 5: "Shadow", 6: "Vine"}


func _colour_name(c: int) -> String:
	return str(COLOUR_NAMES.get(c, "colour %d" % c))


func _title_of(id: String, reply: Dictionary) -> String:
	if str(reply.get("name", "")) != "":
		return str(reply["name"])
	for e in view.get("entities", []):
		if str(e["id"]) == id and str(e.get("name", "")) != "":
			return str(e["name"])
	if id.begins_with("body:"):
		for b in view.get("bodies", []):
			if "body:" + str(b["seat"]) == id:
				return str(b.get("name", "A body"))
	return ""


func _reply_text(reply: Dictionary) -> String:
	var parts: PackedStringArray = []
	if str(reply.get("text", "")) != "":
		parts.append(str(reply["text"]))
	var lines: Array = reply.get("lines", [])
	if not lines.is_empty():
		parts.append("\n\n".join(PackedStringArray(lines)))
	return "\n\n".join(parts)


func _show_prompt(id: String, prompt: Dictionary, lead: String, title: String) -> void:
	_card_entity = id
	_card_kind = "prompt"
	var body := str(prompt.get("text", ""))
	if lead != "" and not body.begins_with(lead) and lead != body:
		body = lead + "\n\n" + body
	var choices: Array = []
	for c in prompt.get("choices", []):
		choices.append({"id": str(c["id"]), "text": str(c["text"])})
	var footer: Array = [{"id": "close", "text": "Continue", "kind": "primary"}] if choices.is_empty() else [{"id": "close", "text": "Step back"}]
	_show(title, "", body, choices, footer)


func _can_resurrect(id: String) -> bool:
	if world._dead_mode:
		return false
	for b in view.get("bodies", []):
		if "body:" + str(b["seat"]) == id:
			return not bool(b.get("old", false))
	return false


func _hide_entity(id: String) -> void:
	for e in world._entities:
		if str(e.get("id", "")) == id:
			var node = e.get("node")
			if node != null and is_instance_valid(node):
				node.visible = false
			var p := Vector2i(int(e["pos"][0]), int(e["pos"][1]))
			if world._entity_at.has(p) and str(world._entity_at[p].get("id", "")) == id:
				world._entity_at.erase(p)
	var ents: Array = view.get("entities", [])
	view["entities"] = ents.filter(func(e): return str(e["id"]) != id)
	world._update_prompt()


func _refresh_view() -> void:
	var reply: Dictionary = world._sim.op({"op": "trial_view"})
	if str(reply.get("status", "")) == "ok" and not (reply.get("view", {}) as Dictionary).is_empty():
		_apply_view(reply["view"])


# ---------------------------------------------------------------- the card

func _show(title: String, subtitle: String, body: String, choices: Array, footer: Array) -> void:
	card.show_card(title, subtitle, body, choices, footer)
	world._input_locked = true
	world._held_dir = Vector2i.ZERO


func _close_card() -> void:
	card.hide_card()
	_card_entity = ""
	_card_kind = ""
	if not world._dead_mode and not world._duel_open:
		world._input_locked = false


func _on_choice(id: String) -> void:
	if _card_kind == "leave":
		if id == "leave":
			_close_card()
			leave()
		return
	if _card_kind == "body" and id == "resurrect":
		var seat := _card_entity.trim_prefix("body:")
		_close_card()
		var reply: Dictionary = world._sim.op({"op": "resurrect", "target": seat})
		if str(reply.get("status", "")) != "started":
			_toast("You cannot bring them back from here (%s)." % str(reply.get("reason", "")))
		return
	if _card_kind == "prompt":
		var entity := _card_entity
		var reply: Dictionary = world._sim.op({"op": "trial_choose", "entity": entity, "choice": id})
		last_reply = reply
		if str(reply.get("status", "")) == "started":  # the choice began a duel: the false eye's guardian, Ivy's thorns, the tribe's champion
			_close_card()
			_handle(entity, reply)
			return
		if str(reply.get("status", "")) != "ok":
			_close_card()
			_toast("That is no longer possible (%s)." % str(reply.get("reason", "")))
			return
		if bool(reply.get("champion", false)):
			_close_card()
			_show("", "", str(reply.get("prompt", {}).get("text", "")), [], [{"id": "close", "text": "Into the daylight", "kind": "primary"}])
			_card_kind = "champion"
			world._sfx().fracture(3)
			return
		if reply.has("prompt") and typeof(reply["prompt"]) == TYPE_DICTIONARY:
			_show_prompt(entity, reply["prompt"], "", card.title_label.text)
		else:
			_close_card()
		_refresh_view()


func _on_footer(id: String) -> void:
	if _card_kind == "champion":
		_card_kind = ""
		_close_card()
		return
	if _card_kind == "lease":
		var lease := _pending_lease
		_pending_lease = {}
		_close_card()
		if id == "begin":
			world.open_story_duel(lease)
		else:
			world._sim.op({"op": "duel_abandon"})
		return
	_close_card()


## After a creature's duel resolved (hybrid_world `_cmd`): what the host made of it.
func after_duel(t: Dictionary) -> void:
	if t.is_empty():
		return
	if bool(t.get("killed", false)):
		_hide_entity(str(t.get("entity", "")))
		world._sfx().fracture(3)
	elif bool(t.get("dead", false)):
		world._sfx().defeat()
	else:
		world._sfx().denied()
	if t.has("spell"):
		_toast("A new colour: %s." % _colour_name(int(t["spell"])), 4.0)
	if str(t.get("text", "")) != "":
		_toast(str(t["text"]), 6.0)


func _offer_leave() -> void:
	if not active or card.visible or not bool(view.get("at_door", false)):
		return
	_card_entity = ""
	_card_kind = "leave"
	_show("The way out", "", "The gate is behind you. The run goes on without you, and you may come back in; what you carry comes with you.",
		[{"id": "leave", "text": "Leave the Trial"}], [{"id": "close", "text": "Stay", "kind": "primary"}])


func leave() -> Dictionary:
	var reply: Dictionary = world._sim.op({"op": "trial_leave"})
	if str(reply.get("status", "")) == "ok":
		_exit_zone()
		_toast("Daylight. The Rollkeeper does not look up.", 4.0)
	else:
		match str(reply.get("reason", "")):
			"not_at_the_door":
				_toast("The way out is the way you came in.")
			"duel_open":
				_toast("Finish the duel first.")
			_:
				_toast("You cannot leave now (%s)." % str(reply.get("reason", "")))
	return reply


func _free_camera() -> void:
	world._camera.limit_left = -10000000
	world._camera.limit_top = -10000000
	world._camera.limit_right = 10000000
	world._camera.limit_bottom = 10000000


func _exit_zone() -> void:
	active = false
	view = {}
	_pending_lease = {}
	for k in _others.values():
		world.remove_actor(k)
	_others.clear()
	card.hide_card()
	_card_entity = ""
	if _card_kind != "champion":
		_card_kind = ""
	strip.visible = false
	leave_btn.visible = false
	for c in world._tiles_root.get_children():
		c.queue_free()
	for c in world._props_root.get_children():
		c.queue_free()
	for c in world._actors_root.get_children():
		if not world._is_persistent_actor(c):
			c.queue_free()
	world._entities.clear()
	world._entity_at.clear()
	world._fire_frames.clear()
	world._cutscene_actors.clear()
	world.area_id = "hybrid"
	world.area = {"id": "hybrid", "name": "Wizard RTS", "rows": ["."]}
	world.grid_w = 2000
	world.grid_h = 2000
	_free_camera()
	world._hud_area_lbl.text = "Wizard RTS"
	world._prompt_lbl.text = ""
	world._touch.set_action_label("")
	if not world._dead_mode and not world._duel_open:
		world._input_locked = false
	world.refresh_snapshot()
	world._place_john_from_snapshot()
	world._update_john_sprite(0)
	world.queue_redraw()


# ---------------------------------------------------------------- walking

## Another wizard's tile is not free (the host refuses it too).
func blocked(p: Vector2i) -> bool:
	for k in _others.values():
		var n = world.actor(k)
		if n != null and is_instance_valid(n) and n.get_meta("tile", Vector2i(-99, -99)) == p:
			return true
	return false


## A tile was stepped onto locally: the host validates it (sync: the next poll must not see a stale tile). A refusal puts us back.
func arrived() -> void:
	var d := _dir_of(world._john_facing)
	var reply: Dictionary = world._sim.op({"op": "trial_move", "dx": d.x, "dy": d.y, "facing": world._john_facing})
	var st := str(reply.get("status", ""))
	_seen_pos = Vector2i(-1, -1)  # a poll answered while this call waited is older than this reply
	if reply.has("pos"):
		_host_pos = Vector2i(int(reply["pos"][0]), int(reply["pos"][1]))
	if _trace:
		print("TRIAL move %s -> %s: %s %s" % [str(d), str(world._john_pos), st, str(reply.get("pos", reply.get("reason", "")))])
	if st == "ok":
		if bool(reply.get("changed_zone", false)):
			var text := str(reply.get("travel_text", ""))
			_enter_zone(reply.get("view", {}))
			if text != "":
				_toast(text, 5.0)
			world._sfx().fracture(1)
		return
	var back: Vector2i = world._john_pos - d
	if reply.has("pos"):
		back = Vector2i(int(reply["pos"][0]), int(reply["pos"][1]))
	world.set_john_pos(back)
	if st == "rejected":
		match str(reply.get("reason", "")):
			"not_yet":
				_toast(str(reply.get("text", "The way on is not open.")), 5.0)
			"duel_open", "dead", "not_inside":
				pass
			_:
				_toast("You cannot go that way.")


static func _dir_of(facing: String) -> Vector2i:
	match facing:
		"left":
			return Vector2i(-1, 0)
		"right":
			return Vector2i(1, 0)
		"up":
			return Vector2i(0, -1)
	return Vector2i(0, 1)


# ---------------------------------------------------------------- drawing

func _draw_overlay() -> void:
	if not active:
		return
	var tpx := float(world.TPX)
	for b in view.get("bodies", []):
		var c := Vector2((float(b["x"]) + 0.5) * tpx, (float(b["y"]) + 0.5) * tpx)
		world._art._draw_body(overlay, c)
		if bool(b.get("old", false)):
			overlay.draw_string(ThemeDB.fallback_font, c + Vector2(-40, 34), "a body, long cold", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color(0.7, 0.7, 0.8))
		else:
			overlay.draw_string(ThemeDB.fallback_font, c + Vector2(-30, 34), str(b.get("name", "")), HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color(0.9, 0.85, 1.0))
	var res: Dictionary = world._res_fx
	if not res.is_empty() and res.has("tile"):
		var t: Array = res["tile"]
		var c := Vector2((float(t[0]) + 0.5) * tpx, (float(t[1]) + 0.5) * tpx)
		var total := maxf(1.0, float(res.get("total_ms", 6000)))
		var done := clampf(1.0 - float(res.get("left_ms", 0)) / total, 0.0, 1.0)
		var time_s := Time.get_ticks_msec() / 1000.0
		overlay.draw_arc(c, 40.0, 0.0, TAU, 40, Color(0.5, 0.8, 1.0, 0.35), 3.0)
		overlay.draw_arc(c, 40.0, -PI * 0.5, -PI * 0.5 + TAU * done, 40, Color(0.75, 0.95, 1.0, 0.95), 5.0)
		for k in 3:
			var a := time_s * 2.4 + float(k) * TAU / 3.0
			var r := 34.0 - 18.0 * done
			var col: Color = [Color(1.0, 0.45, 0.2), Color(0.4, 0.75, 1.0), Color(0.45, 0.9, 0.4)][k]
			overlay.draw_circle(c + Vector2(cos(a), sin(a)) * r, 7.0 + 3.0 * done, col)
		overlay.draw_circle(c, 6.0 + 10.0 * done, Color(1.0, 1.0, 1.0, 0.25 + 0.5 * done))


# ---------------------------------------------------------------- keys

func _unhandled_input(event: InputEvent) -> void:
	if not active or not (event is InputEventKey and event.pressed and not event.echo):
		return
	var k: InputEventKey = event
	if card.visible:
		if k.keycode == KEY_ESCAPE:
			_on_footer("close")
		elif k.keycode in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
			if not card.activate_primary():
				_on_footer("close")
		elif k.keycode >= KEY_1 and k.keycode <= KEY_9:
			card.activate_choice_index(k.keycode - KEY_1)
		get_viewport().set_input_as_handled()
		return
	if k.keycode == KEY_E:
		interact()
		get_viewport().set_input_as_handled()
	elif k.keycode == KEY_L and bool(view.get("at_door", false)):
		_offer_leave()
		get_viewport().set_input_as_handled()


func _toast(text: String, seconds := 3.0) -> void:
	print("TRIAL toast: ", text)
	if world.mp:
		world._mp_toast_show(text, seconds)
	elif world.hud != null:
		world.hud.flash(text, seconds)


# ---------------------------------------------------------------- tests

func ui_view() -> Dictionary:
	return view.duplicate(true)


func ui_card_text() -> String:
	return card.body_label.text if card.visible else ""


func ui_card_choices() -> Array:
	return card.choice_ids() if card.visible else []
