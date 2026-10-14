extends Node
class_name HybridWizardLabels

## Wizard Mode semantic labels over the hybrid world. This reuses the existing DuelMasterBattle interaction surface
## (client/world/world_interaction_label.gd and sim/world/world_interaction_resolver.gd) with the same semantic contract
## {knowledge_key, labels, observe_far, observe_near, interaction}: it does not add a second interaction system.
##
## - A few salient entities near the wizard carry a passive LABEL (trees only when very close), so a crowded base stays readable.
## - Clicking ANY entity, near or far, opens its label: far shows the description (OBSERVATION); within FIRE_RANGE it speaks and offers
##   the choices "Burn it with fire magic" / "Leave it alone" (RESPONSES).
## - Fire magic is a command to the simulation by stable entity id (`fire`). The simulation re-checks the range from the wizard's
##   authoritative tile, so a stale client cannot burn what is far away. Pictures are never deleted locally: the next snapshot decides.

const _Label = preload("res://client/world/world_interaction_label.gd")
const _Resolver = preload("res://sim/world/world_interaction_resolver.gd")

const FIRE_RANGE := 3  # tiles; must equal wizard_rts/magic.py FIRE_RANGE
const PASSIVE_RADIUS := 6
const TREE_PASSIVE_RADIUS := 3
const MAX_PASSIVE := 3  # owner playtest 12 Oct 2026: six labels in a settlement overlapped; three short, non-overlapping ones
const PASSIVE_CLASSES := ["building", "unit"]  # workers, carriers, animals, trees and rocks label only when clicked
const REFRESH_SECONDS := 0.3
const PRIORITY := {"unit": 0, "building": 1, "worker": 2, "carrier": 3, "animal": 4, "rock": 5, "tree": 6}

var world: Node
var enabled := true
var _entries: Dictionary = {}  # entity id -> {"lbl": label, "anchor": Node2D, "open": bool}
var _anchor_root: Node2D
var _acc := 0.0
var _last_pos := Vector2i(-1, -1)
var last_cast: Dictionary = {}
var last_reply: Dictionary = {}


func setup(p_world: Node) -> void:
	world = p_world
	_anchor_root = Node2D.new()
	_anchor_root.name = "WizardLabelAnchors"
	world.add_child(_anchor_root)


func _active() -> bool:
	if world == null or not enabled or world._snapshot.is_empty() or world._duel_open:
		return false
	return world.god == null or not world.god.active


func _process(delta: float) -> void:
	if not _active():
		_clear_all()
		return
	_acc += delta
	if _acc >= REFRESH_SECONDS:
		_acc = 0.0
		_refresh_passive()
	if world._john_pos != _last_pos:
		_last_pos = world._john_pos
		for id in _entries:
			var lbl = _entries[id]["lbl"]
			if is_instance_valid(lbl) and lbl.is_expanded():
				lbl.notify_player_moved()  # walking away closes a conversation, as everywhere else in the game
	for id in _entries.keys():
		_place_anchor(str(id))
	_drop_vanished()


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


func _semantic(e: Dictionary) -> Dictionary:
	var d := describe(e)
	return {
		"knowledge_key": "hybrid:%s" % str(e["id"]),
		"labels": [{"level": 0, "text": short_title(e)}],
		"observe_far": d["far"],
		"observe_near": d["near"],
		"interaction": "fire",
		"dismiss_on_move": true,
	}


# ------------------------------------------------------------------ label lifecycle

func labels() -> Dictionary:
	var out := {}
	for id in _entries:
		out[id] = _entries[id]["lbl"]
	return out


func label_for(id: String):
	if _entries.has(id):
		return _entries[id]["lbl"]
	return null


func _ensure(e: Dictionary):
	var id := str(e["id"])
	if _entries.has(id):
		return _entries[id]["lbl"]
	var anchor := Node2D.new()
	_anchor_root.add_child(anchor)
	var lbl = _Label.new()
	lbl.name = "Wizard_%s" % id.replace(":", "_")
	world._semantic_root.add_child(lbl)
	lbl.bind_bridge(_semantic(e), id, anchor, world._camera, Vector2(0, -40), Callable(self, "_level"))
	lbl.interact_requested.connect(_on_interact)
	lbl.response_chosen.connect(_on_response)
	_entries[id] = {"lbl": lbl, "anchor": anchor, "open": false}
	_place_anchor(id)
	return lbl


func _level(_key: String) -> int:
	return 1


func _place_anchor(id: String) -> void:
	if not _entries.has(id):
		return
	var e := entity(id)
	if e.is_empty():
		return
	var tpx: float = world.TPX
	var tile := Vector2(float(e.get("tx", 0)), float(e.get("ty", 0)))
	var vis: Dictionary = world._art._vis.get(id, {})
	if not vis.is_empty():
		tile = vis["pos"]
	var centre := (tile + Vector2(0.5, 0.5)) * tpx
	var tiles := _tiles(e)
	if tiles.size() > 1:
		var top := 1 << 30
		var minx := 1 << 30
		var maxx := -(1 << 30)
		for t in tiles:
			top = mini(top, t.y)
			minx = mini(minx, t.x)
			maxx = maxi(maxx, t.x)
		centre = Vector2((minx + maxx + 1) * 0.5, float(top)) * tpx
	(_entries[id]["anchor"] as Node2D).global_position = centre


func _drop_vanished() -> void:
	for id in _entries.keys():
		if entity(str(id)).is_empty():
			_remove(str(id))


func _remove(id: String) -> void:
	if not _entries.has(id):
		return
	var rec: Dictionary = _entries[id]
	if is_instance_valid(rec["lbl"]):
		rec["lbl"].queue_free()
	if is_instance_valid(rec["anchor"]):
		rec["anchor"].queue_free()
	_entries.erase(id)


func _clear_all() -> void:
	for id in _entries.keys():
		_remove(str(id))


func _refresh_passive() -> void:
	var me: Vector2i = world._john_pos
	var cands: Array = []
	for e in world._snapshot.get("entities", []):
		if typeof(e) != TYPE_DICTIONARY:
			continue
		var cls := str(e.get("class", ""))
		if not cls in PASSIVE_CLASSES or str(e.get("kind", "")) == "hazard" or bool(e.get("inside", false)):
			continue
		var d := distance_to(e)
		if d > PASSIVE_RADIUS:
			continue
		cands.append([int(PRIORITY[cls]) * 100 + d, e])
	cands.sort_custom(func(a, b): return a[0] < b[0])
	var keep := {}
	var taken: Array = []  # screen rectangles already used by a kept label: a label that would overlap one is not shown
	for c in cands:
		if keep.size() >= MAX_PASSIVE:
			break
		var r := _passive_rect(c[1])
		var clash := false
		for t in taken:
			if (t as Rect2).intersects(r):
				clash = true
				break
		if clash:
			continue
		taken.append(r)
		keep[str(c[1]["id"])] = c[1]
	if world.story_ui != null and world.story_ui.dialog.visible:
		keep.clear()  # an open conversation owns the screen
	for id in _entries.keys():
		var lbl = _entries[id]["lbl"]
		if not keep.has(id) and not (is_instance_valid(lbl) and lbl.is_expanded()):
			_remove(str(id))
	for id in keep:
		var lbl = _ensure(keep[id])
		if is_instance_valid(lbl) and not lbl.is_expanded():
			lbl.update_semantic(_semantic(keep[id]))
	# one expanded interaction owns the foreground: other labels step aside while it talks
	var owner = null
	for id in _entries:
		var lbl = _entries[id]["lbl"]
		if is_instance_valid(lbl) and lbl.is_expanded():
			owner = lbl
	for id in _entries:
		var lbl = _entries[id]["lbl"]
		if not is_instance_valid(lbl):
			continue
		lbl.set_foreground(lbl == owner)
		lbl.set_passive_suppressed(owner != null and lbl != owner and not lbl.is_expanded())


## Where a passive label would sit on screen (title width estimate), used to keep labels apart.
func _passive_rect(e: Dictionary) -> Rect2:
	# the same geometry world_interaction_label uses for a LABEL: width clamp(72 + 11 * chars, 96, 220), 48 high, 8 px above its anchor
	var tpx: float = world.TPX
	var wp := (Vector2(float(e.get("tx", 0)), float(e.get("ty", 0))) + Vector2(0.5, 0.5)) * tpx + Vector2(0, -40)
	var sp: Vector2 = world.get_canvas_transform() * wp
	var w := clampf(72.0 + float(short_title(e).length()) * 11.0, 96.0, 220.0)
	return Rect2(sp - Vector2(w * 0.5, 56.0), Vector2(w, 48.0)).grow(4.0)


## A short passive title: the kind of thing, not the faction and the full description.
func short_title(e: Dictionary) -> String:
	var t := str(describe(e)["title"])
	var faction := str(e.get("faction_name", ""))
	if faction != "" and t.begins_with(faction + " "):
		t = t.substr(faction.length() + 1)
	if t.length() > 22:
		t = t.substr(0, 21) + "…"
	return t


# ------------------------------------------------------------------ pointer

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
			var reach := 0.75 if cls in ["unit", "worker", "carrier", "animal"] else 0.6
			if cls == "tree":
				centre = pos + Vector2(0.5, -0.45)  # a tree's crown is drawn above the tile it stands on: that is where people click
				reach = 0.75
			hit = centre.distance_to(cell) <= reach
			score = centre.distance_to(cell) + float(PRIORITY[cls]) * 0.2
		if hit and score < best_score:
			best_score = score
			best = e
	return best


## Left click in Wizard Mode. Returns true when the click opened an entity's label.
func try_click(screen_pos: Vector2) -> bool:
	if not _active():
		return false
	var e := pick(screen_pos)
	if e.is_empty():
		for id in _entries:
			var lbl = _entries[id]["lbl"]
			if is_instance_valid(lbl) and lbl.is_expanded():
				lbl.collapse()
		return false
	open(str(e["id"]))
	return true


func open(id: String) -> void:
	var e := entity(id)
	if e.is_empty():
		return
	for other in _entries:
		var o = _entries[other]["lbl"]
		if other != id and is_instance_valid(o) and o.is_expanded():
			o.collapse()
	var lbl = _ensure(e)
	lbl.update_semantic(_semantic(e))
	lbl.collapse()
	lbl.press()  # LABEL -> interact_requested: far observes, near offers fire


func _on_interact(key: String) -> void:
	var id := key.trim_prefix("hybrid:")
	var e := entity(id)
	var lbl = label_for(id)
	if e.is_empty() or lbl == null:
		return
	var resolved: Dictionary = _Resolver.resolve(_semantic(e), null, in_range(e), 1)
	if str(resolved.get("mode", "")) != "interact":
		lbl.open_observation()  # at a distance a click only describes the thing
		return
	var options: Array = [
		{"index": 0, "label": "Burn it with fire magic"},
		{"index": 1, "label": "Leave it alone"},
	]
	var who := str(describe(e).get("person", ""))
	if who != "":
		options.push_front({"index": 2, "label": "Talk to %s" % who})
	lbl.begin_speech([str(resolved.get("observe_near", ""))], options)
	# the description and the choices appear together: advance the one-line speech on the next frame
	await get_tree().process_frame
	await get_tree().process_frame  # the label ignores a second press in the frame counter value of the first
	if is_instance_valid(lbl) and lbl.interaction_state() == "SPEECH":
		lbl.press()


func _on_response(key: String, index: int) -> void:
	var id := key.trim_prefix("hybrid:")
	var lbl = label_for(id)
	if index == 2:  # "Talk to <name>": the story dialogue over the simulation's own body
		if lbl != null:
			lbl.collapse()
		world.story_ui.talk_to(id)
		return
	if index != 0:
		if lbl != null:
			lbl.collapse()
		return
	cast_fire(id)


## The Fire interaction: a simulation command by stable id. The reply decides what is shown.
func cast_fire(id: String) -> Dictionary:
	var e := entity(id)
	last_cast = {"id": id, "class": str(e.get("class", ""))}
	var reply: Dictionary = world._sim.op({"op": "fire", "target": id})
	last_reply = reply
	if reply.has("snapshot"):
		world._apply_snapshot(reply["snapshot"])
	var lbl = label_for(id)
	if str(reply.get("status", "")) == "ok":
		if lbl != null:
			lbl.collapse()
		_remove(id)
		world._hud_area_lbl.text = "Fire!"
	else:
		var why := str(reply.get("reason", "failed"))
		var text: String = {"too_far": "Too far away: walk closer to burn it.", "recharging": "The fire needs a moment to gather.", "already_destroyed": "It is already burning.", "already_dead": "It is already dead.", "no_target": "It is gone."}.get(why, "The spell fizzles (%s)." % why)
		if lbl != null:
			lbl.begin_speech([text], [])
	return reply
