extends Node
class_name HybridWizardLabels

## Wizard Mode inspection. Nothing floats over the world: clicking (or tapping) a person, a building, a tree or any other entity opens ONE inspect card
## (DmbNarrativeCard) with what it is and what the wizard can do with it: Talk, Burn it with fire magic, ask a worker out of a building. The click
## is taken on release (so a pinch or a drag never selects anything) and picks the figure that is drawn under the pointer: a person standing in a
## doorway beats the building, a building beats the tree behind it.
##
## Fire magic is a command to the simulation by stable id (`fire`). The simulation re-checks the range from the wizard's authoritative tile and, in
## the campaign, that Flame has been learned, so a stale client cannot burn what is far away or what it has no magic for. Pictures are never deleted
## locally: the next snapshot decides.

const _VT = preload("res://client/scripts/visual_theme.gd")
const NarrativeCard = preload("res://client/ui/narrative_card.gd")

const FIRE_RANGE := 3  # tiles; must equal wizard_rts/magic.py FIRE_RANGE
const RESURRECT_RANGE := 2  # tiles (Manhattan); must equal config.json mortality.resurrect_range
const CALL_RANGE := 6  # tiles; must equal wizard_rts/narrative/conversation.py CALLOUT_RANGE
const REFRESH_SECONDS := 0.3
const PRIORITY := {"npc": 0, "unit": 0, "building": 1, "worker": 2, "carrier": 3, "animal": 4, "rock": 5, "tree": 6}
const OCCUPATION := {"ranger": "Forester", "lumberjack": "Lumberjack", "stonemason": "Stonemason", "hunter": "Hunter", "carrier": "Carrier", "soldier": "Soldier"}

var world: Node
var enabled := true
var panel: Control  # the inspect card (DmbNarrativeCard)
var current_id := ""
var last_cast: Dictionary = {}
var last_reply: Dictionary = {}
var _workers: Array = []  # people at the open building, from the server: [{id, person, name, role, inside}]
var _who: Dictionary = {}  # the open person, from the server: {name, subtitle}
var _note := ""
var _sig := ""  # what the card shows now: it is only rebuilt when this changes (a rebuild would swallow a click in progress)
var _acc := 0.0


func setup(p_world: Node) -> void:
	world = p_world
	var layer := CanvasLayer.new()
	layer.name = "InspectLayer"
	layer.layer = 13
	world.add_child(layer)
	panel = NarrativeCard.new()
	layer.add_child(panel)
	panel.setup(world, "sheet", "InspectPanel")
	panel.choice_pressed.connect(_on_action)
	panel.footer_pressed.connect(func(_id: String) -> void: close())


func _active() -> bool:
	if world == null or not enabled or world._snapshot.is_empty() or world._duel_open:
		return false
	return world.god == null or not world.god.active


func _process(delta: float) -> void:
	if not panel.visible:
		return
	if not _active() or (world.story_ui != null and (world.story_ui.dialog.visible or world.story_ui.opening_card.visible)):
		close()
		return
	_acc += delta
	if _acc >= REFRESH_SECONDS:
		_acc = 0.0
		if entity(current_id).is_empty():
			close()  # it is gone (burned, died, walked off the map): the next snapshot decided
		else:
			_render()


# ------------------------------------------------------------------ entities and descriptions

func entity(id: String) -> Dictionary:
	for e in world._snapshot.get("entities", []):
		if typeof(e) == TYPE_DICTIONARY and str(e.get("id", "")) == id:
			return e
	return {}


func _tiles(e: Dictionary) -> Array:
	var out: Array = []
	for key in ["ground_footprint", "footprint"]:
		for p in e.get(key, []):
			out.append(Vector2i(int(p[0]), int(p[1])))
	if out.is_empty():
		out.append(Vector2i(int(e.get("tx", 0)), int(e.get("ty", 0))))
	return out


## Chebyshev tiles from the wizard to the nearest tile of the entity (what the simulation measures).
func distance_to(e: Dictionary) -> int:
	var best := 1 << 30
	var me: Vector2i = world._john_pos
	for t in _tiles(e):
		best = mini(best, maxi(absi(me.x - t.x), absi(me.y - t.y)))
	return best


func in_range(e: Dictionary) -> bool:
	return distance_to(e) <= FIRE_RANGE


func _species(e: Dictionary) -> String:
	return str(e.get("definition", "")).get_slice(".", 1).replace("_", " ").capitalize()


func describe(e: Dictionary) -> Dictionary:
	var cls := str(e.get("class", ""))
	var faction := str(e.get("faction_name", ""))
	var title := str(e.get("label", cls)).strip_edges()
	var far := ""
	var who: String = world.story_ui.person_name(str(e.get("id", ""))) if world.story_ui != null and cls in ["worker", "carrier", "unit"] else ""
	match cls:
		"tree":
			var sp := _species(e)
			title = "%s tree" % sp
			match str(e.get("stage", "")):
				"sapling": far = "A %s sapling, newly planted." % sp.to_lower()
				"pole": far = "A young %s, still growing." % sp.to_lower()
				"mature": far = "A %s tree, nearly full grown." % sp.to_lower()
				"old": far = "A tall old %s tree, ready for a lumberjack." % sp.to_lower()
				"felled": title = "Felled tree"; far = "A felled tree waiting to be cleared."
				_: far = "A %s." % sp.to_lower()
		"building":
			if bool(e.get("destroyed", false)):
				title = "Burning ruin"
				far = "%s is burning down." % str(e.get("label", "A building"))
			else:
				far = "%s (%s). %s" % [str(e.get("label", "A building")), faction if faction != "" else "no faction", str(e.get("status_text", ""))]
				if e.has("hp") and int(e.get("hp", 0)) < int(e.get("max_hp", 0)):
					far += " Damaged: %d of %d." % [int(e.get("hp", 0)) / 100, int(e.get("max_hp", 0)) / 100]
		"worker":
			title = str(e.get("role", "Worker")).replace("_", " ").capitalize()
			far = "%s of the %s, %s; carrying %s." % [title, faction, str(e.get("status", "idle")), str(e.get("carrying", "")) if str(e.get("carrying", "")) != "" else "nothing"]
		"carrier":
			title = "Carrier"
			far = "A road carrier of the %s, carrying %s." % [faction, str(e.get("cargo", "")) if str(e.get("cargo", "")) != "" else "nothing"]
		"unit":
			var naval := str(e.get("loco", "")) in ["naval", "lcraft"]
			far = "%s (%s)%s. Health %d of %d." % [str(e.get("label", "A unit")), faction, " - a ship" if naval else "", int(e.get("hp", 0)) / 100, int(e.get("max_hp", 0)) / 100]
			if not bool(e.get("alive", true)):
				far = "The remains of %s." % str(e.get("label", "a unit"))
		"animal":
			far = "A wild %s." % title.to_lower()
		"rock":
			title = "Rocks"
			far = "A rock formation holding %d loads of granite." % int(e.get("amount", 0))
		_:
			far = title
	if who != "":  # a body with a character: the person's name leads, and the role stays in the description
		far = "%s. %s" % [who, far]
		title = who
	var near := far + "\nYou are close enough to burn it with fire magic."
	return {"title": title, "far": far, "near": near, "person": who}


## The entity under a screen position (any distance), or {}.
func pick(screen_pos: Vector2) -> Dictionary:
	var wp: Vector2 = world.get_canvas_transform().affine_inverse() * screen_pos
	var tpx: float = world.TPX
	var cell := Vector2(wp.x / tpx, wp.y / tpx)
	var best: Dictionary = {}
	var best_score := 1.0e9
	for e in world._snapshot.get("entities", []):
		if typeof(e) != TYPE_DICTIONARY:
			continue
		var cls := str(e.get("class", ""))
		if not PRIORITY.has(cls) or bool(e.get("inside", false)):
			continue
		var tx := float(e.get("tx", 0))
		var ty := float(e.get("ty", 0))
		if absf(tx - cell.x) > 6.0 or absf(ty - cell.y) > 6.0:
			continue
		var hit := false
		var score := 0.0
		var tiles := _tiles(e)
		if cls in ["building"]:
			for t in tiles:
				if cell.x >= t.x and cell.x < t.x + 1 and cell.y >= t.y and cell.y < t.y + 1:
					hit = true
			score = 10.0  # on the footprint itself a figure standing there (a carrier at the door) is picked first
			# the roof of a building is drawn above its footprint: that part of the picture belongs to the building alone
			if not hit and tiles.size() == 1 and cell.x >= tx and cell.x < tx + 1 and cell.y >= ty - 1.0 and cell.y < ty:
				hit = true
				score = 0.3
		else:
			var vis: Dictionary = world._art._vis.get(str(e.get("id", "")), {})
			var pos := Vector2(tx, ty)
			if not vis.is_empty():
				pos = vis["pos"]
			var centre := pos + Vector2(0.5, 0.35)
			var reach := 0.75 if cls in ["unit", "worker", "carrier", "animal", "npc"] else 0.6
			if cls == "tree":
				centre = pos + Vector2(0.5, -0.45)  # a tree's crown is drawn above the tile it stands on: that is where people click
				reach = 0.75
			hit = centre.distance_to(cell) <= reach
			score = centre.distance_to(cell) + float(PRIORITY[cls]) * 0.2
		if hit and score < best_score:
			best_score = score
			best = e
	return best


# ------------------------------------------------------------------ the inspect card

func person_row(e: Dictionary) -> bool:
	if str(e.get("class", "")) == "npc":
		return true
	return str(e.get("class", "")) in ["worker", "carrier", "unit"] and not bool(e.get("inside", false)) and bool(e.get("alive", true))


func occupation_of(e: Dictionary) -> String:
	var cls := str(e.get("class", ""))
	if cls == "worker":
		return str(OCCUPATION.get(str(e.get("role", "")), str(e.get("role", "worker")).replace("_", " ").capitalize()))
	if cls == "carrier":
		return "Carrier"
	if cls == "unit":
		return "Soldier" if str(e.get("kind", "")) == "soldier" else str(e.get("label", "Unit"))
	if cls == "npc":
		return str(e.get("role", "villager")).capitalize()
	return ""


## Fire is gated by learning Flame in the campaign only (the server decides; the journal says whether it is gated, and what is known).
func flame_known() -> bool:
	var journal: Dictionary = world.story_ui.journal_data() if world.story_ui != null else {}
	if journal.is_empty() or not bool(journal.get("magic_gated", false)):
		return true
	return (journal.get("spells", []) as Array).has("Flame")


## Open the inspect card for the entity with this id.
func open(id: String) -> void:
	var e := entity(id)
	if e.is_empty():
		return
	current_id = id
	_workers = []
	_who = {}
	_note = ""
	if person_row(e) and world._sim != null:
		var who: Dictionary = world._sim.op({"op": "inspect_person", "npc": id})  # the server names everyone, near or far: one Person per body
		if str(who.get("status", "")) == "ok":
			_who = who
	if str(e.get("class", "")) == "building" and world._sim != null:
		var reply: Dictionary = world._sim.op({"op": "inspect_building", "building": id})
		if str(reply.get("status", "")) == "ok":
			_workers = reply.get("people", [])
	_render()


func close() -> void:
	_sig = ""
	current_id = ""
	_workers = []
	_who = {}
	if panel != null:
		panel.hide_card()


func _render() -> void:
	var e := entity(current_id)
	if e.is_empty():
		return
	var d := describe(e)
	var cls := str(e.get("class", ""))
	var near := in_range(e)
	var actions: Array = []
	var title := str(d["title"])
	var subtitle := ""
	var body := str(d["far"])
	if person_row(e):
		var pname := str(_who.get("name", e.get("label", "")))
		title = pname if pname != "" else title
		subtitle = str(_who.get("subtitle", occupation_of(e)))
		body = describe_person(e)
		var close_enough: bool = _manhattan(e) <= world.story_ui.TALK_RANGE
		if not bool(_who.get("dead", e.get("dead", false))) and not bool(_who.get("hostile", e.get("hostile", false))):
			actions.append({"id": "talk", "text": "Talk" if close_enough else "Talk (walk closer)", "kind": "primary", "disabled": not close_enough})
		elif bool(e.get("body", false)) and str(e.get("seat", "")) != LanSession.player_id:
			# a fallen apprentice: standing beside the body, a living wizard can bring them back (the host runs the channel)
			var near_body: bool = _manhattan(e) <= RESURRECT_RANGE
			var me_dead: bool = world.has_method("ui_dead") and world.ui_dead()
			actions.append({"id": "resurrect", "text": "Bring them back" if near_body else "Bring them back (walk closer)", "kind": "primary", "disabled": not near_body or me_dead})
	elif cls == "building":
		subtitle = "Building - %s" % (str(e.get("faction_name", "")) if str(e.get("faction_name", "")) != "" else "no faction")
		body = str(e.get("status_text", "")) if str(e.get("status_text", "")) != "" else str(d["far"])
		if bool(e.get("destroyed", false)):
			body = "It is burning down."
		if int(e.get("hp", 0)) < int(e.get("max_hp", 0)) and not bool(e.get("destroyed", false)):
			body += " Damaged: %d of %d." % [int(e.get("hp", 0)) / 100, int(e.get("max_hp", 0)) / 100]
		for w in _workers:
			var line := "%s, %s" % [str(w["name"]), str(OCCUPATION.get(str(w["role"]), str(w["role"])))]
			body += "\n" + line + (" - inside" if bool(w["inside"]) else " - out at work")
			if bool(w["inside"]):
				var can := maxi(absi(world._john_pos.x - int(e["tx"])), absi(world._john_pos.y - int(e["ty"]))) <= CALL_RANGE
				actions.append({"id": "call:" + str(w["id"]), "text": "Ask %s to come out" % str(w["name"]) + ("" if can else " (walk closer)"), "disabled": not can})
	else:
		subtitle = cls.capitalize()
	if _note != "":
		body += "\n\n" + _note
	var can_burn := near and flame_known()
	var burn_text := "Burn it with fire magic"
	if not flame_known():
		burn_text += " (you have no magic yet)"
	elif not near:
		burn_text += " (walk closer)"
	if cls != "npc":  # the narrative people (the mentor's body, the stranger) are not targets of the world's fire magic
		actions.append({"id": "burn", "text": burn_text, "disabled": not can_burn})
	# The card is only rebuilt when WHO it is about or WHAT can be done changes; a changing description (a building's status text) is updated in place,
	# so a click that is in flight on a button is never lost to a rebuild.
	var sig := JSON.stringify([title, subtitle, actions])
	if sig == _sig and panel.visible:
		if panel.body_label.text != body:
			panel.body_label.text = body
			panel.relayout()
		return
	_sig = sig
	panel.show_card(title, subtitle, body, actions, [{"id": "close", "text": "Close"}])


func describe_person(e: Dictionary) -> String:
	var cls := str(e.get("class", ""))
	var bits: PackedStringArray = []
	var carrying := str(e.get("carrying", ""))
	if cls == "worker":
		bits.append("Carrying a %s." % carrying if carrying != "" else "Not carrying anything.")
		var st := str(e.get("status", ""))
		if st != "" and st != "idle":
			bits.append("Currently %s." % st.replace("_", " "))
		else:
			bits.append("Waiting for work.")
	elif cls == "carrier":
		bits.append("Carrying a %s along the road." % str(e.get("cargo", "")) if str(e.get("cargo", "")) != "" else "Walking the road with nothing to carry.")
	elif cls == "unit":
		bits.append("Health %d of %d." % [int(e.get("hp", 0)) / 100, int(e.get("max_hp", 0)) / 100])
	elif cls == "npc":
		if bool(e.get("body", false)):
			bits.append("An apprentice, dead where they fell. The weave of three can call them back, if somebody stands beside them and holds it.")
		elif bool(e.get("dead", false)):
			bits.append("Their body lies where they fell. People have not dared to move it yet.")
		elif bool(e.get("hostile", false)):
			bits.append("A stranger in a dark travelling cloak. The air around him feels wrong.")
		else:
			bits.append("Stands where they usually stand, watching the square.")
	return " ".join(bits)


func _manhattan(e: Dictionary) -> int:
	return absi(world._john_pos.x - int(e["tx"])) + absi(world._john_pos.y - int(e["ty"]))


func _on_action(id: String) -> void:
	var e := entity(current_id)
	if e.is_empty():
		return
	if id == "talk":
		var target := current_id
		close()
		world.story_ui.talk_to(target)
	elif id == "resurrect":
		var seat := str(e.get("seat", current_id))
		var reply: Dictionary = world._sim.op({"op": "resurrect", "target": seat})
		if str(reply.get("status", "")) == "started":
			close()
			world._hud_area_lbl.text = "Weaving…"
		else:
			_note = {"too_far": "Stand beside the body first.", "already_channelling": "You are already weaving.", "dead": "The dead cannot weave.",
				"no_body": "There is nobody there to bring back."}.get(str(reply.get("reason", "")), "The weave will not take (%s)." % str(reply.get("reason", "")))
			_render()
	elif id == "burn":
		var target := current_id
		var reply := cast_fire(target)
		if str(reply.get("status", "")) == "ok":
			close()
		else:
			_note = fire_message(str(reply.get("reason", "failed")))
			_render()
	elif id.begins_with("call:"):
		var wid := id.trim_prefix("call:")
		var reply: Dictionary = world._sim.op({"op": "call_out", "npc": wid})
		if str(reply.get("status", "")) == "coming":
			close()
			world.story_ui._toast("%s is coming out." % str(reply.get("name", "They")))
		else:
			_note = {"too_far": "Walk closer to the building first.", "not_inside": "They are not inside.", "no_room": "There is no room to step out."}.get(str(reply.get("reason", "")), "They cannot come out now.")
			_render()


func fire_message(why: String) -> String:
	return {"too_far": "Too far away: walk closer to burn it.", "recharging": "The fire needs a moment to gather.", "already_destroyed": "It is already burning.",
		"already_dead": "It is already dead.", "no_target": "It is gone.", "spell_unknown": "You have not learned any magic yet. Find your teacher."}.get(why, "The spell fizzles (%s)." % why)


## The Fire interaction: a simulation command by stable id. The reply decides what is shown.
func cast_fire(id: String) -> Dictionary:
	var e := entity(id)
	last_cast = {"id": id, "class": str(e.get("class", ""))}
	var reply: Dictionary = world._sim.op({"op": "fire", "target": id})
	last_reply = reply
	if reply.has("snapshot"):
		world._apply_snapshot(reply["snapshot"])
	if str(reply.get("status", "")) == "ok":
		world._hud_area_lbl.text = "Fire!"
	return reply


# ------------------------------------------------------------------ pointer

## Left click in Wizard Mode (taken on release). Returns true when it opened an inspect card; a click on empty ground closes the open one.
func try_click(screen_pos: Vector2) -> bool:
	if not _active():
		return false
	var e := pick(screen_pos)
	if e.is_empty():
		close()
		return false
	open(str(e["id"]))
	return true
