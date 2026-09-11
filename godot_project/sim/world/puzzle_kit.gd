extends RefCounted
class_name DmbPuzzleKit
## Generic grid puzzle toolkit (docs/Duel_Master_Battle_Puzzle_Mechanics.txt).
## A SMALL SET OF GENERIC GRID SYSTEMS -> MANY DISTINCT PUZZLES.
##
## Pure and deterministic: a room definition (DmbPuzzleRooms) plus a mutable
## state dictionary (persisted under Adventure.puzzle_state("pz_NN")) go in,
## results come out. The client (client/world/puzzle_controller.gd) applies
## results to the inventory and the screen and draws *only* from `visual()`,
## so what the player sees and what the engine believes cannot drift apart.
##
## Entity kinds (all data, none bespoke):
##   plaque, lever, button, plate, gate, pit, marker, sequence, receptacle,
##   item, magic_target, rotator, emitter, receiver, hazard, teleporter,
##   crumble, npc, critter, guardian, board, container, choice, goal
## Conditions: "flag", "!flag", {"all": [...]}, {"any": [...]}, null = always.
## Effects: {"set"}, {"clear"}, {"toggle"}, {"text"}, {"relocate"}, {"wound"},
##   {"timer": {"flag", "steps"}}, {"give"}, {"take"}, {"spawn_item"}, {"flash"}

const SPELL_FIRE := 0
const SPELL_WATER := 1
const SPELL_STONE := 3
const SPELL_LIGHT := 4
const SPELL_NAMES := {0: "Fire", 1: "Water", 3: "Stone", 4: "Light", 6: "Vine"}

const SOLID_CHARS := ["T", "#", " ", "X", "r"]
const THROW_RANGE := 6

## Kinds the player cannot walk through when present.
const BLOCKING_KINDS := ["plaque", "lever", "button", "receptacle", "rotator", "emitter", "receiver", "npc", "critter", "guardian", "board", "container", "choice"]


static func is_puzzle_area(id: String) -> bool:
	return id.begins_with("pz_")


static func spell_name(s: int) -> String:
	if SPELL_NAMES.has(s):
		return str(SPELL_NAMES[s])
	return DmbColourData.essence_name(s)


# ---------------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------------

static func fresh_state(room: Dictionary) -> Dictionary:
	var st := {
		"solved": false, "flags": {}, "player": room["start"].duplicate(), "steps": 0, "wounds": 0,
		"levers": {}, "rec": {}, "seq": {}, "rot": {}, "hazards": {}, "tele": {}, "crumble": {},
		"npcs": {}, "critters": {}, "world_items": [], "opened": {}, "tripped": {}, "timers": {}, "last_press": {}, "inv": [],
	}
	for e in room["entities"]:
		var id := str(e.get("id", ""))
		if bool(e.get("scorched", false)):
			st["tripped"][id] = true
		match str(e["kind"]):
			"lever":
				st["levers"][id] = bool(e.get("on", false))
			"receptacle":
				st["rec"][id] = str(e.get("installed", ""))
			"sequence":
				st["seq"][id] = 0
			"rotator":
				st["rot"][id] = int(e.get("orientation", 0))
			"hazard":
				st["hazards"][id] = {"i": int(e.get("phase", 0)), "t": 0.0, "dir": 1}
			"teleporter":
				st["tele"][id] = {"i": 0, "t": 0.0}
			"crumble":
				st["crumble"][id] = {"state": "intact", "n": 0}
			"npc":
				st["npcs"][id] = {"pos": e["pos"].duplicate(), "i": 0, "go": false, "talked": false}
			"critter":
				st["critters"][id] = {"pos": e["pos"].duplicate()}
			"item":
				var w := {"item": str(e["item"]), "pos": e["pos"].duplicate(), "src": id}
				if e.has("requires"):
					w["requires"] = e["requires"]
				if e.has("on_pickup"):
					w["on_pickup"] = e["on_pickup"]
				st["world_items"].append(w)
	for f in room.get("flags", []):
		st["flags"][str(f)] = true
	return st


## Mirror the inventory into state so flags can ask "has_<item>".
static func sync_inventory(st: Dictionary, items: Array) -> void:
	st["inv"] = items.duplicate()


static func is_solved(st: Dictionary) -> bool:
	return bool(st.get("solved", false))


static func entity(room: Dictionary, id: String) -> Dictionary:
	for e in room["entities"]:
		if str(e.get("id", "")) == id:
			return e
	return {}


static func _pos(a: Array) -> Vector2i:
	return Vector2i(int(a[0]), int(a[1]))


static func _same(a: Array, b: Array) -> bool:
	return int(a[0]) == int(b[0]) and int(a[1]) == int(b[1])


static func tile_char(room: Dictionary, p: Vector2i) -> String:
	var rows: Array = room["rows"]
	if p.y < 0 or p.y >= rows.size() or p.x < 0 or p.x >= str(rows[p.y]).length():
		return " "
	return str(rows[p.y])[p.x]


# ---------------------------------------------------------------------------------
# Conditions and derived flags
# ---------------------------------------------------------------------------------

static func cond(c, flags: Dictionary) -> bool:
	if c == null:
		return true
	if c is bool:
		return c
	if c is String:
		var s := str(c)
		if s.begins_with("!"):
			return not bool(flags.get(s.substr(1), false))
		return bool(flags.get(s, false))
	if c is Dictionary:
		if c.has("all"):
			for x in c["all"]:
				if not cond(x, flags):
					return false
			return true
		if c.has("any"):
			for x in c["any"]:
				if cond(x, flags):
					return true
			return false
	return false


## [satisfied, total] for an "all" condition — lets a gate look ajar.
static func cond_progress(c, flags: Dictionary) -> Array:
	if c is Dictionary and c.has("all"):
		var n := 0
		for x in c["all"]:
			if cond(x, flags):
				n += 1
		return [n, c["all"].size()]
	return [1 if cond(c, flags) else 0, 1]


## Base flags plus everything derived from occupancy: plates, receptacles,
## rotator orientations, beam receivers. Evaluated fresh each time so nothing
## can go stale.
static func flags_now(room: Dictionary, st: Dictionary) -> Dictionary:
	var f: Dictionary = st["flags"].duplicate()
	f["solved"] = bool(st["solved"])
	for it in st.get("inv", []):
		f["has_" + str(it)] = true
	for e in room["entities"]:
		match str(e["kind"]):
			"lever":
				if e.has("flag") and bool(st["levers"].get(str(e["id"]), false)):
					f[str(e["flag"])] = true
			"receptacle":
				if e.has("flag") and str(st["rec"].get(str(e["id"]), "")) != "" and _accepts(e, str(st["rec"][str(e["id"])])):
					f[str(e["flag"])] = true
			"rotator":
				if e.has("flag_at"):
					var o := int(st["rot"].get(str(e["id"]), 0))
					if e["flag_at"].has(str(o)):
						f[str(e["flag_at"][str(o)])] = true
	for e in room["entities"]:
		if str(e["kind"]) == "plate" and e.has("flag") and plate_active(room, st, e):
			f[str(e["flag"])] = true
	# Beams last: emitters may depend on plate/lever flags.
	for e in room["entities"]:
		if str(e["kind"]) == "emitter" and cond(e.get("active_when"), f):
			for hit in beam_hits(room, st, e, f):
				var rec := entity(room, str(hit))
				if rec.has("flag"):
					f[str(rec["flag"])] = true
	return f


static func plate_active(room: Dictionary, st: Dictionary, e: Dictionary) -> bool:
	var acc: Array = e.get("accepts", ["player", "item"])
	var pos: Array = e["pos"]
	if "player" in acc and _same(st["player"], pos):
		return true
	if "item" in acc:
		var tags: Array = e.get("item_tags", [])
		for w in world_items(room, st):
			if _same(w["pos"], pos) and (tags.is_empty() or _has_any_tag(str(w["item"]), tags)):
				return true
	if "npc" in acc:
		for id in st["npcs"]:
			if _same(st["npcs"][id]["pos"], pos):
				return true
	if "critter" in acc:
		for id in st["critters"]:
			if _same(st["critters"][id]["pos"], pos):
				return true
	return false


static func _has_any_tag(item: String, tags: Array) -> bool:
	for t in DmbItems.tags_of(item):
		if t in tags:
			return true
	return false


static func _accepts(e: Dictionary, item: String) -> bool:
	if item in e.get("accepts_items", []):
		return true
	return _has_any_tag(item, e.get("accepts_tags", []))


## World items whose `requires` condition currently holds.
static func world_items(room: Dictionary, st: Dictionary) -> Array:
	var out: Array = []
	var base: Dictionary = st["flags"].duplicate()
	base["solved"] = bool(st["solved"])
	for w in st["world_items"]:
		if w.has("requires") and not cond(w["requires"], base):
			continue
		out.append(w)
	return out


static func world_item_at(room: Dictionary, st: Dictionary, pos: Vector2i) -> Dictionary:
	for w in world_items(room, st):
		if _pos(w["pos"]) == pos:
			return w
	return {}


# ---------------------------------------------------------------------------------
# Beams (M10): emitter -> mirrors -> receiver, traced on the grid.
# ---------------------------------------------------------------------------------

## Tiles the beam passes through, ending at the tile of whatever stops it.
static func beam_path(room: Dictionary, st: Dictionary, em: Dictionary, flags: Dictionary) -> Array:
	var out: Array = []
	var p := _pos(em["pos"])
	var d := Vector2i(int(em["dir"][0]), int(em["dir"][1]))
	for i in range(64):
		p += d
		if tile_char(room, p) in SOLID_CHARS:
			break
		out.append(p)
		var hit := _beam_obstacle(room, st, p, flags)
		if hit.is_empty():
			continue
		if str(hit["kind"]) == "rotator" and bool(hit.get("mirror", false)):
			var o := int(st["rot"].get(str(hit["id"]), 0))
			d = Vector2i(-d.y, -d.x) if o == 0 else Vector2i(d.y, d.x)
			continue
		break
	return out


static func beam_hits(room: Dictionary, st: Dictionary, em: Dictionary, flags: Dictionary) -> Array:
	var hits: Array = []
	for p in beam_path(room, st, em, flags):
		var hit := _beam_obstacle(room, st, p, flags)
		if not hit.is_empty() and str(hit["kind"]) == "receiver":
			hits.append(str(hit["id"]))
	return hits


static func _beam_obstacle(room: Dictionary, st: Dictionary, p: Vector2i, flags: Dictionary) -> Dictionary:
	for e in room["entities"]:
		if not e.has("pos") or _pos(e["pos"]) != p:
			continue
		match str(e["kind"]):
			"rotator", "receiver", "emitter", "receptacle", "lever", "npc", "board", "container", "critter":
				return e
			"gate":
				if not gate_open(e, flags):
					return e
	return {}


static func gate_open(e: Dictionary, flags: Dictionary) -> bool:
	return cond(e.get("open_when"), flags)


# ---------------------------------------------------------------------------------
# Occupancy / walkability
# ---------------------------------------------------------------------------------

## The thing at `pos` the player would face: a present entity or a world item.
static func entity_at(room: Dictionary, st: Dictionary, pos: Vector2i) -> Dictionary:
	var flags := flags_now(room, st)
	for e in room["entities"]:
		if not e.has("pos"):
			continue
		if _pos(e["pos"]) != pos:
			continue
		if not present(room, st, e, flags):
			continue
		if str(e["kind"]) in ["sequence"]:
			continue
		return e
	for id in st["npcs"]:
		if _pos(st["npcs"][id]["pos"]) == pos:
			return entity(room, str(id))
	for id in st["critters"]:
		if _pos(st["critters"][id]["pos"]) == pos:
			return entity(room, str(id))
	var w := world_item_at(room, st, pos)
	if not w.is_empty():
		return {"kind": "world_item", "id": "wi_" + str(w["item"]), "item": str(w["item"]), "pos": w["pos"]}
	return {}


## Whether an entity exists in the room right now (guardians appear, items
## drop through floors, secret switches get revealed).
static func present(room: Dictionary, st: Dictionary, e: Dictionary, flags: Dictionary) -> bool:
	if e.has("requires") and not cond(e["requires"], flags):
		return false
	match str(e["kind"]):
		"guardian":
			return not bool(flags.get(str(e.get("defeated_flag", "")), false))
		"npc", "critter":
			# Their live position is in state; the definition's pos is only a start.
			return false
		"item":
			return false
	return true


static func blocks(room: Dictionary, st: Dictionary, pos: Vector2i) -> bool:
	if tile_char(room, pos) in SOLID_CHARS:
		return true
	var flags := flags_now(room, st)
	for e in room["entities"]:
		if not e.has("pos") or _pos(e["pos"]) != pos or not present(room, st, e, flags):
			continue
		var k := str(e["kind"])
		if k in BLOCKING_KINDS:
			return true
		if k == "gate" and not gate_open(e, flags):
			return true
		if k == "magic_target" and cond(e.get("solid_when", true), flags):
			return true
	for id in st["npcs"]:
		if _pos(st["npcs"][id]["pos"]) == pos:
			return true
	for id in st["critters"]:
		if _pos(st["critters"][id]["pos"]) == pos:
			return true
	if not world_item_at(room, st, pos).is_empty():
		return true
	return false


## Path planning for tests/companions: avoid anything that would move or hurt
## the player unless it is the destination.
static func path_safe(room: Dictionary, st: Dictionary, pos: Vector2i) -> bool:
	if blocks(room, st, pos):
		return false
	var flags := flags_now(room, st)
	for e in room["entities"]:
		if not e.has("pos") or _pos(e["pos"]) != pos:
			continue
		match str(e["kind"]):
			"pit":
				if not cond(e.get("bridge_when", false), flags):
					return false
			"teleporter", "goal":
				return false
			"marker":
				if e.has("unsafe_when") and cond(e["unsafe_when"], flags):
					return false
				if e.has("seq") or e.has("on_enter"):
					return false
			"crumble":
				return false
		if str(e["kind"]) == "hazard":
			for hp in e["path"]:
				if _pos(hp) == pos:
					return false
	return true


static func hazard_pos(e: Dictionary, st: Dictionary) -> Vector2i:
	var h: Dictionary = st["hazards"][str(e["id"])]
	return _pos(e["path"][int(h["i"])])


# ---------------------------------------------------------------------------------
# Results and effects
# ---------------------------------------------------------------------------------

static func _result() -> Dictionary:
	return {"text": [], "consume": [], "grant": [], "relocate": null, "changed": false, "solved_now": false, "flash": false, "battle": "", "rejected": false, "learn": -1}


static func _say(r: Dictionary, t: String) -> void:
	if t != "":
		r["text"].append(t)


static func _apply(room: Dictionary, st: Dictionary, effects, r: Dictionary) -> void:
	if effects == null:
		return
	for ef in effects:
		r["changed"] = true
		if ef.has("set"):
			st["flags"][str(ef["set"])] = true
		if ef.has("clear"):
			st["flags"][str(ef["clear"])] = false
			st["timers"].erase(str(ef["clear"]))
		if ef.has("toggle"):
			var k := str(ef["toggle"])
			st["flags"][k] = not bool(st["flags"].get(k, false))
		if ef.has("timer"):
			var tm: Dictionary = ef["timer"]
			st["flags"][str(tm["flag"])] = true
			st["timers"][str(tm["flag"])] = int(tm["steps"])
		if ef.has("text"):
			_say(r, str(ef["text"]))
		if ef.has("relocate"):
			r["relocate"] = ef["relocate"].duplicate()
			st["player"] = ef["relocate"].duplicate()
		if ef.has("wound"):
			st["wounds"] = int(st["wounds"]) + int(ef["wound"])
			r["flash"] = true
			var back: Array = ef.get("reset_to", room["start"])
			r["relocate"] = back.duplicate()
			st["player"] = back.duplicate()
		if ef.has("flash"):
			r["flash"] = true
		if ef.has("give"):
			r["grant"].append(str(ef["give"]))
		if ef.has("take"):
			r["consume"].append(str(ef["take"]))
		if ef.has("spawn_item"):
			var sp: Dictionary = ef["spawn_item"]
			st["world_items"].append({"item": str(sp["item"]), "pos": sp["pos"].duplicate(), "src": "spawn"})
		if ef.has("remove_item_at"):
			var at: Array = ef["remove_item_at"]
			for w in st["world_items"].duplicate():
				if _same(w["pos"], at):
					st["world_items"].erase(w)
		if ef.has("reset_seq"):
			st["seq"][str(ef["reset_seq"])] = 0
		if ef.has("npc_go"):
			var id := str(ef["npc_go"])
			if st["npcs"].has(id):
				st["npcs"][id]["go"] = true


# ---------------------------------------------------------------------------------
# Interaction
# ---------------------------------------------------------------------------------

## What the player can do to `e` right now, given inventory/spells in ctx.
static func actions_for(room: Dictionary, st: Dictionary, e: Dictionary, ctx: Dictionary) -> Array:
	var out: Array = []
	var items: Array = ctx.get("items", [])
	match str(e["kind"]):
		"lever":
			out.append({"label": "Pull", "action": {"kind": "pull"}})
		"button":
			out.append({"label": str(e.get("verb", "Press")), "action": {"kind": "press"}})
		"rotator":
			out.append({"label": "Rotate", "action": {"kind": "rotate"}})
		"container":
			if not bool(st["opened"].get(str(e["id"]), false)):
				out.append({"label": str(e.get("verb", "Open")), "action": {"kind": "open"}})
		"receptacle":
			var inst := str(st["rec"].get(str(e["id"]), ""))
			if inst != "" and bool(e.get("removable", true)):
				out.append({"label": "Take %s" % DmbItems.name_of(inst), "action": {"kind": "remove"}})
			for it in items:
				out.append({"label": "Place %s" % DmbItems.name_of(str(it)), "action": {"kind": "install", "item": str(it)}})
		"magic_target":
			for s in ctx.get("spells", []):
				out.append({"label": "Cast %s" % spell_name(int(s)), "action": {"kind": "cast", "spell": int(s)}})
		"guardian":
			out.append({"label": "Fight", "action": {"kind": "fight"}})
		"world_item":
			out.append({"label": "Take", "action": {"kind": "take"}})
		"choice":
			if not bool(st["flags"].get(str(e.get("once_flag", e["id"] + "_answered")), false)):
				for o in e["options"]:
					out.append({"label": str(o["label"]), "action": {"kind": "answer", "label": str(o["label"])}})
		"npc":
			out.append({"label": "Talk", "action": {"kind": "talk"}})
		"critter", "plaque", "board", "emitter", "receiver":
			out.append({"label": "Look", "action": {"kind": "look"}})
	return out


static func act(room: Dictionary, st: Dictionary, e: Dictionary, action: Dictionary, ctx: Dictionary) -> Dictionary:
	var r := _result()
	var id := str(e.get("id", ""))
	var kind := str(action.get("kind", ""))
	var items: Array = ctx.get("items", [])
	match str(e["kind"]):
		"lever":
			if kind == "pull":
				var on := bool(st["levers"].get(id, false))
				if on and bool(e.get("once", false)):
					_say(r, str(e.get("stuck_text", "It is already down, and it stays down.")))
				else:
					st["levers"][id] = not on
					r["changed"] = true
					_say(r, str(e.get("on_text" if not on else "off_text", "The lever moves with a clunk." if not on else "The lever eases back up.")))
					_apply(room, st, e.get("on_pull" if not on else "on_release"), r)
					if e.has("timed_steps") and not on:
						st["timers"][str(e["flag"])] = int(e["timed_steps"])
						st["flags"][str(e["flag"])] = true
		"button":
			if kind == "press":
				r["changed"] = true
				st["last_press"][id] = int(st["steps"])
				_say(r, str(e.get("text", "")))
				_apply(room, st, e.get("on_press"), r)
				for sq in _seqs_of(e):
					_sequence_input(room, st, str(sq), id, r)
		"rotator":
			if kind == "rotate":
				var n := int(e.get("states", 2))
				st["rot"][id] = (int(st["rot"].get(id, 0)) + 1) % n
				r["changed"] = true
				_say(r, str(e.get("text", "It turns one notch.")))
		"container":
			if kind == "open" and not bool(st["opened"].get(id, false)):
				st["opened"][id] = true
				r["changed"] = true
				_say(r, str(e.get("text", "")))
				if str(e.get("contains", "")) != "":
					r["grant"].append(str(e["contains"]))
				if e.has("teaches_spell"):
					r["learn"] = int(e["teaches_spell"])
				_apply(room, st, e.get("on_open"), r)
		"receptacle":
			_act_receptacle(room, st, e, action, items, r)
		"magic_target":
			if kind == "cast":
				var s := int(action.get("spell", -1))
				var flags := flags_now(room, st)
				if not (s in ctx.get("spells", [])):
					_say(r, "You do not know that magic.")
				elif e.has("responses") and e["responses"].has(str(s)) and cond(e["responses"][str(s)].get("when"), flags):
					var resp: Dictionary = e["responses"][str(s)]
					r["changed"] = true
					_say(r, str(resp.get("text", "")))
					_apply(room, st, resp.get("effects"), r)
				elif bool(e.get("rebound", false)) and cond(e.get("rebound_when", true), flags):
					r["rejected"] = true
					r["changed"] = true
					_say(r, str(e.get("rebound_text", "The magic comes straight back at you.")))
					_apply(room, st, [{"wound": int(e.get("rebound_wound", 1)), "reset_to": e.get("reset_to", room["start"])}], r)
				else:
					r["rejected"] = true
					_say(r, str(e.get("wrong_text", "%s does nothing useful here." % spell_name(s))))
		"guardian":
			if kind == "fight":
				r["battle"] = str(e["enemy_id"])
		"world_item":
			if kind == "take":
				var w := world_item_at(room, st, _pos(e["pos"]))
				if not w.is_empty():
					if int(items.size()) >= DmbItems.MAX_SLOTS:
						_say(r, "Your pockets are full.")
					else:
						st["world_items"].erase(w)
						r["grant"].append(str(w["item"]))
						r["changed"] = true
						_say(r, "Taken: %s." % DmbItems.name_of(str(w["item"])))
						if w.has("on_pickup"):
							_apply(room, st, w["on_pickup"], r)
		"choice":
			if kind == "answer":
				for o in e["options"]:
					if str(o["label"]) == str(action.get("label", "")):
						st["flags"][str(e.get("once_flag", id + "_answered"))] = true
						r["changed"] = true
						_say(r, str(o.get("text", "")))
						_apply(room, st, o.get("effects"), r)
		"npc":
			if kind == "talk":
				var n: Dictionary = st["npcs"][id]
				var lines: Array = e.get("lines", [])
				if bool(n["talked"]) and e.has("lines_after"):
					lines = e["lines_after"]
				for l in lines:
					_say(r, str(l))
				if not bool(n["talked"]):
					n["talked"] = true
					r["changed"] = true
					_apply(room, st, e.get("on_talk"), r)
					if e.has("walk"):
						n["go"] = true
		"critter", "plaque", "board", "emitter", "receiver":
			if str(e["kind"]) == "board":
				var flags := flags_now(room, st)
				var lines: Array = []
				for s in e["systems"]:
					lines.append("%s — %s" % [str(s["label"]), "ONLINE" if cond(str(s["flag"]), flags) else "offline"])
				_say(r, str(e.get("text", "A status board.")) + "\n" + "\n".join(PackedStringArray(lines)))
			else:
				_say(r, str(e.get("text", "")))
	if r["changed"]:
		_after_change(room, st, r)
	return r


static func _act_receptacle(room: Dictionary, st: Dictionary, e: Dictionary, action: Dictionary, items: Array, r: Dictionary) -> void:
	var id := str(e["id"])
	var kind := str(action.get("kind", ""))
	var inst := str(st["rec"].get(id, ""))
	if kind == "remove":
		if inst == "":
			_say(r, "There is nothing to take.")
		elif not bool(e.get("removable", true)):
			_say(r, "It will not come loose.")
		elif items.size() >= DmbItems.MAX_SLOTS:
			_say(r, "Your pockets are full.")
		else:
			st["rec"][id] = ""
			r["grant"].append(inst)
			r["changed"] = true
			_say(r, str(e.get("remove_text", "You take %s." % DmbItems.name_of(inst))))
			_apply(room, st, e.get("on_remove"), r)
	elif kind == "install":
		var item := str(action.get("item", ""))
		if not (item in items):
			_say(r, "You do not have that.")
		elif inst != "":
			_say(r, str(e.get("occupied_text", "Something already sits there.")))
		elif not _accepts(e, item):
			r["rejected"] = true
			_say(r, str(e.get("reject_text", "%s does not fit." % DmbItems.name_of(item))))
			r["changed"] = true
			_apply(room, st, e.get("reject_effects"), r)
		else:
			r["changed"] = true
			if bool(e.get("consume", false)):
				r["consume"].append(item)
				st["rec"][id] = item
				_say(r, str(e.get("install_text", "%s is taken in and does not come back." % DmbItems.name_of(item))))
			else:
				r["consume"].append(item)
				st["rec"][id] = item
				_say(r, str(e.get("install_text", "%s settles into place." % DmbItems.name_of(item))))
			_apply(room, st, e.get("on_install"), r)
			if e.has("install_effects_by_item") and e["install_effects_by_item"].has(item):
				_apply(room, st, e["install_effects_by_item"][item], r)


## An input (marker/button) may feed one sequence or several ("seq": id | [ids]).
static func _seqs_of(e: Dictionary) -> Array:
	if not e.has("seq"):
		return []
	if e["seq"] is Array:
		return e["seq"]
	return [e["seq"]]


static func _sequence_input(room: Dictionary, st: Dictionary, seq_id: String, marker_id: String, r: Dictionary) -> void:
	var sq := entity(room, seq_id)
	if sq.is_empty():
		return
	var flags := flags_now(room, st)
	if not cond(sq.get("active_when"), flags):
		return
	if bool(flags.get(str(sq["flag"]), false)):
		return
	var steps: Array = sq["steps"].duplicate()
	if cond(sq.get("reverse_when", false), flags):
		steps.reverse()
	var prog := int(st["seq"].get(seq_id, 0))
	if not (marker_id in steps):
		return
	if prog > 0 and str(steps[prog - 1]) == marker_id:
		return  # standing on / re-pressing the last accepted one is neutral
	if str(steps[prog]) == marker_id:
		prog += 1
		st["seq"][seq_id] = prog
		r["changed"] = true
		if prog >= steps.size():
			st["flags"][str(sq["flag"])] = true
			_say(r, str(sq.get("done_text", "Something heavy shifts. The order was right.")))
			_apply(room, st, sq.get("on_complete"), r)
		else:
			_say(r, str(sq.get("step_text", "A soft click. %d of %d." % [prog, steps.size()])))
	elif bool(sq.get("reset_on_wrong", true)):
		st["seq"][seq_id] = 0
		r["changed"] = true
		r["flash"] = true
		_say(r, str(sq.get("wrong_text", "A dull thud. Whatever was counting has started again.")))


# ---------------------------------------------------------------------------------
# Movement: what happens when the player arrives on a tile
# ---------------------------------------------------------------------------------

static func on_step(room: Dictionary, st: Dictionary, pos: Vector2i, ctx: Dictionary) -> Dictionary:
	var r := _result()
	st["player"] = [pos.x, pos.y]
	st["steps"] = int(st["steps"]) + 1
	# Timers count player steps (deterministic, like the existing timed gate).
	for k in st["timers"].keys():
		st["timers"][k] = int(st["timers"][k]) - 1
		if int(st["timers"][k]) <= 0:
			st["timers"].erase(k)
			st["flags"][k] = false
			r["changed"] = true
			_say(r, "Somewhere, a clunk: something has closed again.")
	# Crumbling tiles count down.
	for id in st["crumble"]:
		var c: Dictionary = st["crumble"][id]
		if str(c["state"]) == "cracked":
			c["n"] = int(c["n"]) - 1
			if int(c["n"]) <= 0:
				c["state"] = "gone"
				r["changed"] = true
	_move_npcs(room, st, r)
	_move_critters(room, st, r)
	_enter_tile(room, st, pos, r)
	if r["changed"]:
		_after_change(room, st, r)
	return r


static func _enter_tile(room: Dictionary, st: Dictionary, pos: Vector2i, r: Dictionary) -> void:
	var flags := flags_now(room, st)
	for e in room["entities"]:
		if not e.has("pos") or _pos(e["pos"]) != pos or not present(room, st, e, flags):
			continue
		match str(e["kind"]):
			"pit":
				if cond(e.get("bridge_when", false), flags):
					continue
				_fall(room, st, e, r)
				return
			"crumble":
				var c: Dictionary = st["crumble"][str(e["id"])]
				if str(c["state"]) == "gone":
					_fall(room, st, e, r)
					return
				if str(c["state"]) == "intact":
					c["state"] = "cracked"
					c["n"] = int(e.get("steps", 2))
					r["changed"] = true
					_say(r, str(e.get("crack_text", "The tile cracks under you. It will not hold long.")))
			"marker":
				r["changed"] = true
				if e.has("unsafe_when") and cond(e["unsafe_when"], flags):
					st["tripped"][str(e["id"])] = true
					_say(r, str(e.get("unsafe_text", "Wrong stone. Light flares and the room throws you back.")))
					_apply(room, st, [{"wound": 0, "reset_to": e.get("reset_to", room["start"])}], r)
					r["flash"] = true
					if e.has("reset_seq"):
						st["seq"][str(e["reset_seq"])] = 0
					return
				_apply(room, st, e.get("on_enter"), r)
				for sq in _seqs_of(e):
					_sequence_input(room, st, str(sq), str(e["id"]), r)
			"teleporter":
				if bool(e.get("items_only", false)):
					_say(r, str(e.get("items_only_text", "The field hums and ignores you. It only takes what is thrown.")))
					continue
				var t: Dictionary = st["tele"][str(e["id"])]
				var target: Array = e["targets"][int(t["i"])]
				r["relocate"] = target.duplicate()
				st["player"] = target.duplicate()
				r["changed"] = true
				r["flash"] = true
				_say(r, str(e.get("text", "The world folds, and you are somewhere else.")))
				return
			"hazard":
				if hazard_pos(e, st) == pos and not cond(e.get("jammed_when", false), flags):
					_hazard_hit(room, st, e, r)
					return
			"goal":
				if cond(e.get("requires"), flags) and not bool(st["solved"]):
					st["solved"] = true
					r["solved_now"] = true
					r["changed"] = true
					_say(r, str(e.get("text", "You made it through. The puzzle is done.")))


static func _fall(room: Dictionary, st: Dictionary, e: Dictionary, r: Dictionary) -> void:
	var to: Array = e.get("fall_to", room["start"])
	r["relocate"] = to.duplicate()
	st["player"] = to.duplicate()
	r["changed"] = true
	r["flash"] = true
	_say(r, str(e.get("fall_text", "The floor is not there. You drop, land badly, and are somewhere else.")))
	if e.has("flag_on_fall"):
		st["flags"][str(e["flag_on_fall"])] = true
	st["tripped"][str(e["id"])] = true


static func _hazard_hit(room: Dictionary, st: Dictionary, e: Dictionary, r: Dictionary) -> void:
	var back: Array = e.get("reset_to", room["start"])
	_say(r, str(e.get("hit_text", "It catches you square and throws you back.")))
	_apply(room, st, [{"wound": 1, "reset_to": back}], r)


static func _move_npcs(room: Dictionary, st: Dictionary, r: Dictionary) -> void:
	for id in st["npcs"]:
		var n: Dictionary = st["npcs"][id]
		if not bool(n["go"]):
			continue
		var e := entity(room, str(id))
		var walk: Array = e.get("walk", [])
		if int(n["i"]) >= walk.size():
			continue
		var next: Array = walk[int(n["i"])]
		if _same(next, st["player"]):
			continue  # waits for the player to move
		n["pos"] = next.duplicate()
		n["i"] = int(n["i"]) + 1
		r["changed"] = true
		var reach: Dictionary = e.get("on_reach", {})
		if reach.has(str(int(n["i"]) - 1)):
			_apply(room, st, reach[str(int(n["i"]) - 1)], r)
		if int(n["i"]) >= walk.size():
			_say(r, str(e.get("arrive_text", "")))
			_apply(room, st, e.get("on_arrive"), r)


## Critters take one grid step toward the nearest lure item they can smell.
static func _move_critters(room: Dictionary, st: Dictionary, r: Dictionary) -> void:
	for id in st["critters"]:
		var c: Dictionary = st["critters"][id]
		var e := entity(room, str(id))
		var here := _pos(c["pos"])
		var best: Vector2i = Vector2i(-1, -1)
		var bestd := 999
		for w in world_items(room, st):
			if not _has_any_tag(str(w["item"]), [str(e.get("lure_tag", "bait"))]):
				continue
			var wp := _pos(w["pos"])
			var d: int = absi(wp.x - here.x) + absi(wp.y - here.y)
			if d < bestd:
				bestd = d
				best = wp
		if bestd == 999 or bestd == 0:
			continue
		var d := best - here
		var options: Array = []
		if absi(d.x) >= absi(d.y):
			options = [Vector2i(signi(d.x), 0), Vector2i(0, signi(d.y))]
		else:
			options = [Vector2i(0, signi(d.y)), Vector2i(signi(d.x), 0)]
		for stp in options:
			if stp == Vector2i.ZERO:
				continue
			var nxt: Vector2i = here + stp
			if nxt == _pos(st["player"]):
				continue
			if nxt == best or not _critter_blocked(room, st, nxt):
				c["pos"] = [nxt.x, nxt.y]
				r["changed"] = true
				break


static func _critter_blocked(room: Dictionary, st: Dictionary, p: Vector2i) -> bool:
	if tile_char(room, p) in SOLID_CHARS:
		return true
	var flags := flags_now(room, st)
	for e in room["entities"]:
		if not e.has("pos") or _pos(e["pos"]) != p or not present(room, st, e, flags):
			continue
		var k := str(e["kind"])
		if k in BLOCKING_KINDS or k == "pit" or (k == "gate" and not gate_open(e, flags)):
			return true
	for id in st["critters"]:
		if _pos(st["critters"][id]["pos"]) == p:
			return true
	for id in st["npcs"]:
		if _pos(st["npcs"][id]["pos"]) == p:
			return true
	return false


## Consequences that follow *any* state change: pits opening under the
## player, hazards released onto him, guardians appearing.
static func _after_change(room: Dictionary, st: Dictionary, r: Dictionary) -> void:
	if r["relocate"] != null:
		return
	var flags := flags_now(room, st)
	var pp := _pos(st["player"])
	for e in room["entities"]:
		if not e.has("pos") or _pos(e["pos"]) != pp:
			continue
		if str(e["kind"]) == "pit" and present(room, st, e, flags) and not cond(e.get("bridge_when", false), flags):
			_fall(room, st, e, r)
			return


# ---------------------------------------------------------------------------------
# Time: hazards and teleporter cycles
# ---------------------------------------------------------------------------------

static func tick(room: Dictionary, st: Dictionary, dt: float) -> Dictionary:
	var r := _result()
	var flags := flags_now(room, st)
	var pp := _pos(st["player"])
	for e in room["entities"]:
		match str(e["kind"]):
			"hazard":
				if cond(e.get("jammed_when", false), flags):
					continue
				if e.has("active_when") and not cond(e["active_when"], flags):
					continue
				var h: Dictionary = st["hazards"][str(e["id"])]
				h["t"] = float(h["t"]) + dt
				var step := float(e.get("step_seconds", 0.6))
				while float(h["t"]) >= step:
					h["t"] = float(h["t"]) - step
					_advance_hazard(e, h)
					r["changed"] = true
					if hazard_pos(e, st) == pp:
						_hazard_hit(room, st, e, r)
						return r
			"teleporter":
				if cond(e.get("hold_when", false), flags):
					continue
				var t: Dictionary = st["tele"][str(e["id"])]
				t["t"] = float(t["t"]) + dt
				var cyc := float(e.get("cycle_seconds", 2.0))
				while float(t["t"]) >= cyc:
					t["t"] = float(t["t"]) - cyc
					t["i"] = (int(t["i"]) + 1) % e["targets"].size()
					r["changed"] = true
	return r


static func _advance_hazard(e: Dictionary, h: Dictionary) -> void:
	var n: int = e["path"].size()
	if n <= 1:
		return
	if str(e.get("mode", "loop")) == "pingpong":
		var i := int(h["i"]) + int(h["dir"])
		if i >= n:
			h["dir"] = -1
			i = n - 2
		elif i < 0:
			h["dir"] = 1
			i = 1
		h["i"] = i
	else:
		h["i"] = (int(h["i"]) + 1) % n


# ---------------------------------------------------------------------------------
# Inventory in the world: drop and throw (M2, M3)
# ---------------------------------------------------------------------------------

static func drop(room: Dictionary, st: Dictionary, item: String, ctx: Dictionary) -> Dictionary:
	var r := _result()
	if not (item in ctx.get("items", [])):
		_say(r, "You do not have that.")
		return r
	var pp := _pos(st["player"])
	if not world_item_at(room, st, pp).is_empty():
		_say(r, "Something already lies here.")
		return r
	st["world_items"].append({"item": item, "pos": [pp.x, pp.y], "src": "drop"})
	r["consume"].append(item)
	r["changed"] = true
	_say(r, "You set %s down at your feet." % DmbItems.name_of(item))
	_after_change(room, st, r)
	return r


## The item flies tile by tile in `dir`, over pits and plates, until it meets
## a wall, a solid entity or the range limit, then lands as a world item.
## Landing on a teleporter sends it on to the portal's current target.
static func throw(room: Dictionary, st: Dictionary, item: String, dir: Vector2i, ctx: Dictionary) -> Dictionary:
	var r := _result()
	if not (item in ctx.get("items", [])):
		_say(r, "You do not have that.")
		return r
	var flags := flags_now(room, st)
	var p := _pos(st["player"])
	var last := p
	for i in range(THROW_RANGE):
		var nxt := p + dir
		if _throw_blocked(room, st, nxt, flags):
			break
		p = nxt
		last = p
		# A thrown thing drops onto the first pressure plate it crosses (M3+M4).
		if not _entity_kind_at(room, st, p, "plate", flags).is_empty() and world_item_at(room, st, p).is_empty():
			break
		var tele := _entity_kind_at(room, st, p, "teleporter", flags)
		if not tele.is_empty():
			var t: Dictionary = st["tele"][str(tele["id"])]
			last = _pos(tele["targets"][int(t["i"])])
			_say(r, "It vanishes into the portal —")
			break
	if last == _pos(st["player"]):
		_say(r, "There is no room to throw it.")
		return r
	if not world_item_at(room, st, last).is_empty():
		last = _land_nearby(room, st, last, flags)
	st["world_items"].append({"item": item, "pos": [last.x, last.y], "src": "throw"})
	r["consume"].append(item)
	r["changed"] = true
	r["thrown_to"] = [last.x, last.y]
	_say(r, "%s lands with a clatter." % DmbItems.name_of(item))
	_after_change(room, st, r)
	return r


static func _throw_blocked(room: Dictionary, st: Dictionary, p: Vector2i, flags: Dictionary) -> bool:
	if tile_char(room, p) in SOLID_CHARS:
		return true
	for e in room["entities"]:
		if not e.has("pos") or _pos(e["pos"]) != p or not present(room, st, e, flags):
			continue
		var k := str(e["kind"])
		if k in BLOCKING_KINDS or (k == "gate" and not gate_open(e, flags)) or (k == "magic_target" and cond(e.get("solid_when", true), flags)):
			return true
	for id in st["npcs"]:
		if _pos(st["npcs"][id]["pos"]) == p:
			return true
	for id in st["critters"]:
		if _pos(st["critters"][id]["pos"]) == p:
			return true
	return false


static func _land_nearby(room: Dictionary, st: Dictionary, p: Vector2i, flags: Dictionary) -> Vector2i:
	for d in [Vector2i(0, 1), Vector2i(1, 0), Vector2i(0, -1), Vector2i(-1, 0)]:
		var q: Vector2i = p + d
		if not _throw_blocked(room, st, q, flags) and world_item_at(room, st, q).is_empty():
			return q
	return p


static func _entity_kind_at(room: Dictionary, st: Dictionary, p: Vector2i, kind: String, flags: Dictionary) -> Dictionary:
	for e in room["entities"]:
		if str(e["kind"]) == kind and e.has("pos") and _pos(e["pos"]) == p and present(room, st, e, flags):
			return e
	return {}


# ---------------------------------------------------------------------------------
# Visual state: the single source the renderer draws from
# ---------------------------------------------------------------------------------

const C_OFF := Color(0.45, 0.45, 0.5)
const C_ON := Color(0.25, 0.85, 0.35)
const C_CLOSED := Color(0.8, 0.2, 0.2)
const C_AJAR := Color(0.9, 0.6, 0.15)
const C_OPEN := Color(0.3, 0.9, 0.4)
const C_PLATE := Color(0.55, 0.55, 0.6)
const C_PRESSED := Color(0.2, 0.7, 0.9)
const C_HOLE := Color(0.05, 0.05, 0.08)
const C_BRIDGE := Color(0.6, 0.45, 0.25)
const C_GOLD := Color(0.95, 0.8, 0.2)
const C_MAGIC := Color(0.6, 0.3, 0.9)
const C_HAZARD := Color(0.95, 0.25, 0.1)
const C_JAMMED := Color(0.5, 0.6, 0.75)
const C_NPC := Color(0.9, 0.75, 0.55)
const C_CRITTER := Color(0.55, 0.8, 0.3)
const C_GUARD := Color(0.75, 0.1, 0.3)
const C_WALL := Color(0.35, 0.3, 0.4)
const C_FIRE := Color(1.0, 0.5, 0.1)
const C_WATER := Color(0.2, 0.5, 0.95)
const C_BEAM := Color(1.0, 0.95, 0.3)
const C_TELE := [Color(0.3, 0.8, 1.0), Color(1.0, 0.4, 0.8), Color(0.6, 1.0, 0.4), Color(1.0, 0.8, 0.3)]
const SYMBOL_COLORS := {"red": Color(0.85, 0.2, 0.2), "blue": Color(0.2, 0.4, 0.9), "green": Color(0.2, 0.75, 0.3), "grey": Color(0.5, 0.5, 0.5), "gold": Color(0.9, 0.75, 0.2), "white": Color(0.9, 0.9, 0.9), "purple": Color(0.6, 0.3, 0.8)}


static func _v(state: String, color: Color, label: String, alpha: float = 1.0) -> Dictionary:
	return {"state": state, "color": color, "label": label, "alpha": alpha, "visible": true, "shape": "block"}


## Visual description of one entity: a state name (what tests assert on), a
## colour, a short label and a shape. Every meaningful state change in the
## engine must produce a different `state` here.
static func visual(room: Dictionary, st: Dictionary, e: Dictionary) -> Dictionary:
	var flags := flags_now(room, st)
	var id := str(e.get("id", ""))
	var k := str(e["kind"])
	if not present(room, st, e, flags) and not (k in ["npc", "critter", "item"]):
		var hidden := _v("hidden", Color.TRANSPARENT, "", 0.0)
		hidden["visible"] = false
		return hidden
	match k:
		"plaque":
			var v := _v("plaque", Color(0.75, 0.7, 0.55), "?")
			v["shape"] = "frame"
			return v
		"lever":
			var on := bool(st["levers"].get(id, false))
			var v := _v("on" if on else "off", C_ON if on else C_OFF, "▼" if on else "▲")
			return v
		"button":
			var recent: bool = st["last_press"].has(id) and int(st["last_press"][id]) == int(st["steps"])
			var col: Color = SYMBOL_COLORS.get(str(e.get("symbol", "grey")), C_OFF)
			var v := _v("pressed" if recent else "idle", col.lightened(0.4) if recent else col, str(e.get("label", "●")))
			return v
		"plate":
			var active := plate_active(room, st, e)
			var v := _v("pressed" if active else "raised", C_PRESSED if active else C_PLATE, "▬" if active else "▭")
			v["shape"] = "pad"
			return v
		"gate":
			var open := gate_open(e, flags)
			var prog := cond_progress(e.get("open_when"), flags)
			var look := str(e.get("look", "gate"))
			var tint: Color = SYMBOL_COLORS.get(str(e.get("symbol", "")), Color.TRANSPARENT)
			if open:
				var v := _v("open", C_OPEN if tint.a == 0.0 else tint.lightened(0.3), str(e.get("label", "" if look != "wall" else "·")), 0.55)
				v["shape"] = "frame"
				return v
			if int(prog[1]) > 1 and int(prog[0]) > 0:
				return _v("ajar", C_AJAR, "≡" if look != "wall" else "")
			var col := C_CLOSED
			var lab := "≡"
			if look == "wall":
				col = C_WALL
				lab = ""
			elif look == "water":
				col = C_WATER
				lab = "~"
			elif look == "door":
				lab = "▮"
			if tint.a > 0.0:
				col = tint
			return _v("closed", col, str(e.get("label", lab)))
		"pit":
			var revealed := cond(e.get("revealed_when", true), flags) or bool(st["tripped"].get(id, false))
			if cond(e.get("bridge_when", false), flags):
				var v := _v("bridged", C_BRIDGE, "═")
				v["shape"] = "pad"
				return v
			if not revealed:
				var v := _v("hidden", Color.TRANSPARENT, "", 0.0)
				v["shape"] = "pad"
				return v
			var v := _v("open", C_HOLE, "▼")
			v["shape"] = "pad"
			return v
		"crumble":
			var c: Dictionary = st["crumble"][id]
			var state := str(c["state"])
			var v := _v(state, C_BRIDGE if state == "intact" else (C_AJAR if state == "cracked" else C_HOLE), "" if state == "intact" else ("✕" if state == "cracked" else "▼"))
			v["shape"] = "pad"
			return v
		"marker":
			var sym := str(e.get("symbol", "grey"))
			var col: Color = SYMBOL_COLORS.get(sym, C_OFF)
			var state := "idle"
			if bool(st["tripped"].get(id, false)):
				state = "scorched"
				col = Color(0.15, 0.1, 0.1)
			elif e.has("seq"):
				for sid in _seqs_of(e):
					var sq := entity(room, str(sid))
					if not cond(sq.get("active_when"), flags):
						continue
					var steps: Array = sq.get("steps", []).duplicate()
					if cond(sq.get("reverse_when", false), flags):
						steps.reverse()
					var prog := int(st["seq"].get(str(sid), 0))
					var done := bool(flags.get(str(sq.get("flag", "")), false))
					var idx := steps.find(id)
					if done or (idx >= 0 and idx < prog):
						state = "lit"
						col = col.lightened(0.45)
						break
			var v := _v(state, col, str(e.get("label", "")), 0.9 if state == "lit" else 0.6)
			v["shape"] = "pad"
			return v
		"receptacle":
			var inst := str(st["rec"].get(id, ""))
			if inst == "":
				var v := _v("empty", Color(0.3, 0.28, 0.35), "◌")
				v["shape"] = "frame"
				return v
			var ok := _accepts(e, inst)
			return _v("filled" if ok else "wrong", DmbItems.color_of(inst) if ok else C_CLOSED, DmbItems.glyph_of(inst))
		"magic_target":
			var solid := cond(e.get("solid_when", true), flags)
			var look := str(e.get("look", "magic"))
			var col := C_MAGIC
			var lab := "✦"
			if look == "fire":
				col = C_FIRE
				lab = "▲"
			elif look == "ice":
				col = Color(0.7, 0.9, 1.0)
				lab = "❄"
			elif look == "vines":
				col = Color(0.2, 0.6, 0.2)
				lab = "♣"
			elif look == "basin":
				col = Color(0.5, 0.5, 0.55)
				lab = "◡"
			elif look == "wall":
				col = C_WALL
				lab = ""
			if e.has("states"):
				for sname in e["states"]:
					if cond(e["states"][sname], flags):
						return _v(str(sname), SYMBOL_COLORS.get(str(e.get("state_colors", {}).get(sname, "purple")), C_MAGIC), lab)
			if not solid:
				var v := _v("cleared", col, lab, 0.35)
				v["shape"] = "frame"
				return v
			return _v("intact", col, lab)
		"rotator":
			var o := int(st["rot"].get(id, 0))
			var labels: Array = e.get("labels", ["/", "\\"] if int(e.get("states", 2)) == 2 else ["↑", "→", "↓", "←"])
			return _v("o%d" % o, Color(0.8, 0.85, 0.95), str(labels[o % labels.size()]))
		"emitter":
			var on := cond(e.get("active_when"), flags)
			return _v("on" if on else "off", C_BEAM if on else C_OFF, "◉")
		"receiver":
			var lit := bool(flags.get(str(e.get("flag", "")), false))
			return _v("lit" if lit else "dark", C_ON if lit else C_OFF, "◎")
		"hazard":
			var jam := cond(e.get("jammed_when", false), flags)
			var inactive: bool = e.has("active_when") and not cond(e["active_when"], flags)
			var v := _v("jammed" if jam else ("inactive" if inactive else "moving"), C_JAMMED if (jam or inactive) else C_HAZARD, str(e.get("label", "▣")))
			var hp := hazard_pos(e, st)
			v["pos"] = [hp.x, hp.y]
			v["phase"] = int(st["hazards"][id]["i"])
			return v
		"teleporter":
			var t: Dictionary = st["tele"][id]
			var i := int(t["i"])
			var v := _v("target%d" % i, C_TELE[i % C_TELE.size()], str(char(65 + i)))
			v["shape"] = "pad"
			return v
		"npc":
			var n: Dictionary = st["npcs"][id]
			var v := _v("arrived" if int(n["i"]) >= e.get("walk", []).size() and bool(n["go"]) else ("walking" if bool(n["go"]) else "waiting"), C_NPC, str(e.get("label", "N")))
			v["pos"] = n["pos"].duplicate()
			return v
		"critter":
			var c: Dictionary = st["critters"][id]
			var v := _v("critter", C_CRITTER, str(e.get("label", "c")))
			v["pos"] = c["pos"].duplicate()
			return v
		"guardian":
			return _v("present", C_GUARD, "!")
		"board":
			var n := 0
			for s in e["systems"]:
				if cond(str(s["flag"]), flags):
					n += 1
			var lamps := ""
			for s in e["systems"]:
				lamps += "●" if cond(str(s["flag"]), flags) else "○"
			return _v("%d/%d" % [n, e["systems"].size()], C_ON if n == e["systems"].size() else Color(0.3, 0.3, 0.4), lamps)
		"container":
			var opened := bool(st["opened"].get(id, false))
			var col: Color = C_GOLD if bool(e.get("ornate", false)) else Color(0.55, 0.4, 0.25)
			return _v("opened" if opened else "closed", col.darkened(0.4) if opened else col, "▢" if opened else "▣")
		"choice":
			var done := bool(st["flags"].get(str(e.get("once_flag", id + "_answered")), false))
			var v := _v("answered" if done else "open", Color(0.75, 0.7, 0.55), "?")
			v["shape"] = "frame"
			return v
		"goal":
			var can := cond(e.get("requires"), flags)
			if bool(st["solved"]):
				return _v("solved", C_GOLD, "✓")
			var v := _v("ready" if can else "locked", C_GOLD if can else C_OFF, "★", 0.8)
			v["shape"] = "pad"
			return v
	return _v(k, C_OFF, "")


## Visuals for every entity plus world items and beams, keyed by id.
static func visual_map(room: Dictionary, st: Dictionary) -> Dictionary:
	var out := {}
	for e in room["entities"]:
		if str(e["kind"]) in ["sequence", "item"]:
			continue
		out[str(e["id"])] = visual(room, st, e)
	for w in world_items(room, st):
		var v := _v("on_floor", DmbItems.color_of(str(w["item"])), DmbItems.glyph_of(str(w["item"])))
		v["pos"] = w["pos"].duplicate()
		out["wi_%d_%d" % [int(w["pos"][0]), int(w["pos"][1])]] = v
	var flags := flags_now(room, st)
	for e in room["entities"]:
		if str(e["kind"]) == "emitter" and cond(e.get("active_when"), flags):
			var i := 0
			for p in beam_path(room, st, e, flags):
				var v := _v("beam", C_BEAM, "", 0.5)
				v["pos"] = [p.x, p.y]
				v["shape"] = "beam"
				out["beam_%s_%d" % [e["id"], i]] = v
				i += 1
	return out
