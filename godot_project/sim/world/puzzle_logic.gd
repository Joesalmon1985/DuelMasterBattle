extends RefCounted
class_name DmbPuzzleLogic
## Pure puzzle state machine. `act` takes a puzzle record (DmbPuzzleGen), its
## mutable state dictionary (persisted in the adventure save) and an action, and
## returns what happened. It never touches the inventory or the map directly;
## the caller applies `consume` / `grant` / `spawn_enemy` and re-renders.
## Being data-in, data-out makes every template testable headless.


static func fresh_state(p: Dictionary) -> Dictionary:
	var st := {"solved": false}
	match str(p["type"]):
		"offerings":
			st["filled"] = {}
		"exchange":
			st["key_taken"] = false
			st["placed"] = ""
		"switch_chain", "mosaic":
			st["progress"] = 0
		"plate_hold":
			st["held_by"] = ""
		"timed_gate":
			st["open"] = false
			st["steps_left"] = 0
		"two_levers":
			st["wrong_pulls"] = 0
	return st


## ctx: {"items": Array of item ids, "spells": Array of spell ids}
static func act(p: Dictionary, st: Dictionary, action: Dictionary, ctx: Dictionary) -> Dictionary:
	var r := {"text": "", "solved_now": false, "consume": [], "grant": "", "spawn_enemy": "", "reset": false}
	if bool(st.get("solved", false)):
		r["text"] = "This room has already given what it had."
		return r
	var items: Array = ctx.get("items", [])
	var kind := str(action.get("kind", ""))
	match str(p["type"]):
		"offerings":
			if kind == "place":
				var sid := str(action.get("slot", ""))
				var item := str(action.get("item", ""))
				var slot := _slot(p, sid)
				if slot.is_empty():
					r["text"] = "There is no niche there."
				elif st["filled"].has(sid):
					r["text"] = "That niche is already filled."
				elif not (item in items):
					r["text"] = "You do not have that."
				elif str(slot["item"]) != item:
					r["text"] = "%s does not fit the shape cut here." % DmbItems.name_of(item)
				else:
					st["filled"][sid] = item
					r["consume"] = [item]
					r["text"] = "%s settles into the stone like it was carved for it." % DmbItems.name_of(item)
					if st["filled"].size() == p["slots"].size():
						_solve(st, r, "Both niches full. Somewhere below, a counterweight lets go, and the far door opens.")
			elif kind == "inspect":
				var sid := str(action.get("slot", ""))
				var slot := _slot(p, sid)
				if not slot.is_empty():
					r["text"] = "A niche shaped for %s." % DmbItems.name_of(str(slot["item"])) if not st["filled"].has(sid) else "Filled."
		"exchange":
			if kind == "take":
				if st["key_taken"]:
					r["text"] = "The plate is bare."
				else:
					st["key_taken"] = true
					r["grant"] = str(p["gives"])
					if st["placed"] == "":
						r["text"] = "You lift the key. The plate rises a finger's width and the door drops shut with a boom."
					else:
						_solve(st, r, "You lift the key. The plate holds — %s keeps it down. The door stays open." % DmbItems.name_of(str(st["placed"])))
			elif kind == "place":
				var item := str(action.get("item", ""))
				if not (item in items):
					r["text"] = "You do not have that."
				elif not (item in p["accepts"]):
					r["text"] = "Too light. The plate does not notice."
				elif st["placed"] != "":
					r["text"] = "Something already sits there."
				else:
					st["placed"] = item
					r["consume"] = [item]
					if st["key_taken"]:
						_solve(st, r, "The plate sinks under %s. Chains rattle, and the door lifts again." % DmbItems.name_of(item))
					else:
						r["text"] = "%s rests beside the key. The plate does not move." % DmbItems.name_of(item)
		"switch_chain", "mosaic":
			var step_kind := "pull" if str(p["type"]) == "switch_chain" else "tread"
			if kind == step_kind:
				var i := int(action.get("index", -1))
				var order: Array = p["order"]
				var prog := int(st["progress"])
				if i == int(order[prog]):
					st["progress"] = prog + 1
					if st["progress"] == order.size():
						_solve(st, r, "The last one. Stone slides on stone, and the way is open.")
					else:
						r["text"] = "Something below clicks and holds. %d of %d." % [st["progress"], order.size()]
				else:
					st["progress"] = 0
					r["reset"] = true
					r["text"] = "A dull thud. Everything resets." if step_kind == "pull" else "The stones dim. Start again."
		"plate_hold":
			if kind == "place":
				var item := str(action.get("item", ""))
				if not (item in items):
					r["text"] = "You do not have that."
				elif not (item in p["items"]):
					r["text"] = "Too light. The plate lifts as soon as you let go."
				else:
					st["held_by"] = item
					r["consume"] = [item]
					_solve(st, r, "%s sits on the plate. It sinks. The door grinds open and, this time, stays." % DmbItems.name_of(item))
			elif kind == "step_on":
				r["text"] = "The plate sinks and the door lifts. You step off to go to it — and it slams. Of course it does."
		"timed_gate":
			if kind == "pull":
				st["open"] = true
				st["steps_left"] = int(p["steps"])
				r["text"] = "The gate lifts. It has started counting."
			elif kind == "step":
				if bool(st["open"]):
					st["steps_left"] = int(st["steps_left"]) - 1
					if int(st["steps_left"]) <= 0:
						st["open"] = false
						r["reset"] = true
						r["text"] = "The gate drops."
			elif kind == "pass":
				if bool(st["open"]):
					_solve(st, r, "You are through as it falls. It clips your heel.")
				else:
					r["text"] = "The gate is down."
		"magic_target":
			if kind == "cast":
				var s := int(action.get("spell", -1))
				if not (s in ctx.get("spells", [])):
					r["text"] = "You do not know that magic."
				elif s == int(p["spell"]):
					_solve(st, r, str(p["result"]))
				else:
					r["text"] = "%s does nothing useful to %s." % [DmbColourData.essence_name(s), str(p["desc"])]
		"two_levers":
			if kind == "pull":
				var i := int(action.get("index", -1))
				if i == int(p["correct"]):
					_solve(st, r, "The right one. The door opens without complaint.")
				else:
					st["wrong_pulls"] = int(st["wrong_pulls"]) + 1
					r["spawn_enemy"] = str(p["wrong_enemy"])
					r["text"] = "The wrong one. A grille in the ceiling opens, and something drops through it."
	return r


static func _solve(st: Dictionary, r: Dictionary, text: String) -> void:
	st["solved"] = true
	r["solved_now"] = true
	r["text"] = text


static func _slot(p: Dictionary, sid: String) -> Dictionary:
	for s in p.get("slots", []):
		if str(s["id"]) == sid:
			return s
	return {}


## Convenience for tests and content: the shortest action list that solves `p`
## given a full inventory. Proves every generated template is completable.
static func solution(p: Dictionary) -> Array:
	match str(p["type"]):
		"offerings":
			var out: Array = []
			for s in p["slots"]:
				out.append({"kind": "place", "slot": s["id"], "item": s["item"]})
			return out
		"exchange":
			return [{"kind": "place", "item": p["items"][0]}, {"kind": "take"}]
		"switch_chain":
			var out: Array = []
			for i in p["order"]:
				out.append({"kind": "pull", "index": i})
			return out
		"mosaic":
			var out: Array = []
			for i in p["order"]:
				out.append({"kind": "tread", "index": i})
			return out
		"plate_hold":
			return [{"kind": "place", "item": "grey_stone"}]
		"timed_gate":
			return [{"kind": "pull"}, {"kind": "pass"}]
		"magic_target":
			return [{"kind": "cast", "spell": p["spell"]}]
		"two_levers":
			return [{"kind": "pull", "index": p["correct"]}]
	return []
