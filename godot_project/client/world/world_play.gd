extends RefCounted
class_name WorldPlay
## Client bridge for the persistent-world content added in the Next Pass:
## settlement quests (§5), dungeon entry and puzzle interaction (§6–§8) and the
## eight-slot quest inventory (§2). Owns no state — everything persists through
## Adventure (items, puzzles, quests) and the world sim (moods, effects).

var _w: Node        # Overworld
var _adv: Node      # Adventure
var _flow: WorldFlow


func setup(world: Node, adv: Node, flow: WorldFlow) -> void:
	_w = world
	_adv = adv
	_flow = flow


# --- inventory --------------------------------------------------------------------

## Mobile-friendly sheet: one line per item, tap to inspect. Returns after close.
func show_inventory() -> void:
	var items: Array = _adv.items()
	if items.is_empty():
		await _w._dialogue.say_async("Pockets", "Nothing but lint and a woodcutter's callouses.\n\n(Up to %d quest and puzzle objects fit here.)" % DmbItems.MAX_SLOTS)
		return
	var labels: Array = []
	for it in items:
		labels.append(DmbItems.name_of(str(it)))
	labels.append("Close")
	while true:
		var pick: String = await _w._dialogue.choose_async("Pockets (%d/%d)" % [items.size(), DmbItems.MAX_SLOTS], labels)
		if pick == "Close" or pick == "":
			return
		var idx := labels.find(pick)
		if idx >= 0 and idx < items.size():
			await _w._dialogue.say_async(pick, DmbItems.describe(str(items[idx])))


## Grant an item from a pickup/quest/puzzle. Handles the full-pockets case.
func grant_item(id: String) -> bool:
	if _adv.has_item(id):
		return false
	if _adv.inventory_full():
		await _w._dialogue.say_async("", "Your pockets are full. Eight things is the most a man can carry and still walk. Leave something behind first.")
		return false
	_adv.add_item(id)
	await _w._dialogue.say_async("", "Taken: %s." % DmbItems.name_of(id))
	return true


# --- dungeons -----------------------------------------------------------------------

func dungeon_area(id: String) -> Dictionary:
	var d := _flow.sim.dungeons.get_dungeon(DmbDungeonMap.dungeon_of(id))
	if d.is_empty():
		return {}
	var node_area := DmbNodeProjection.area_id(int(d["node"]))
	return DmbDungeonMap.area_for(d, _adv.state.get("puzzles", {}), node_area, DmbNodeProjection.dungeon_arrive(_flow.sim, int(d["node"])))


## The world-node door: offer to go in.
func enter_dungeon(e: Dictionary) -> void:
	var d := _flow.sim.dungeons.get_dungeon(str(e["dungeon_id"]))
	if d.is_empty():
		return
	var choice: String = await _w._dialogue.choose_async("Go in?", ["Enter", "Not now"])
	if choice != "Enter":
		return
	var aid := DmbDungeonMap.area_id(d)
	await _w.fade_out(0.4)
	_w.load_area(aid, Vector2i(DmbDungeonMap.ENTRY[0], DmbDungeonMap.ENTRY[1] - 1), "up")
	_adv.mark_visited(aid)
	_adv.save()
	await _w.fade_in(0.4)


func dungeon_solved(did: String) -> bool:
	var d := _flow.sim.dungeons.get_dungeon(did)
	if d.is_empty():
		return false
	for p in d["puzzles"]:
		if not bool(_adv.puzzle_state("%s/%s" % [did, p["id"]]).get("solved", false)):
			return false
	return true


func puzzle_for(key: String) -> Dictionary:
	var parts := key.split("/")
	var d := _flow.sim.dungeons.get_dungeon(parts[0])
	for p in d.get("puzzles", []):
		if str(p["id"]) == parts[1]:
			return p
	return {}


## An interactable in a dungeon room. Resolves what the player can do here from
## the puzzle template + inventory, asks, and applies the result.
func interact_puzzle(e: Dictionary) -> void:
	var key := str(e["puzzle_key"])
	var p := puzzle_for(key)
	if p.is_empty():
		await _w._dialogue.say_async("", str(e.get("text", "")))
		return
	var st: Dictionary = _adv.puzzle_state(key)
	if st.is_empty():
		st = DmbPuzzleLogic.fresh_state(p)
	var action: Dictionary = e.get("puzzle_action", {}).duplicate()
	await _w._dialogue.say_async("", str(e.get("text", "")))
	if bool(st.get("solved", false)):
		return
	var ctx := {"items": _adv.items(), "spells": _adv.progression.spells_known}
	match str(action.get("kind", "")):
		"place":
			var opts: Array = []
			for it in _adv.items():
				opts.append(DmbItems.name_of(str(it)))
			opts.append("Leave it")
			var pick: String = await _w._dialogue.choose_async("Place what?", opts)
			var idx := opts.find(pick)
			if idx < 0 or idx >= _adv.items().size():
				return
			action["item"] = str(_adv.items()[idx])
		"exchange":
			var opts: Array = ["Take the key"]
			for it in _adv.items():
				opts.append("Place " + DmbItems.name_of(str(it)))
			opts.append("Leave it")
			var pick: String = await _w._dialogue.choose_async("The plate.", opts)
			if pick == "Take the key":
				action = {"kind": "take"}
			elif pick.begins_with("Place "):
				action = {"kind": "place", "item": str(_adv.items()[opts.find(pick) - 1])}
			else:
				return
		"cast":
			var opts: Array = []
			for s in _adv.progression.spells_known:
				opts.append(DmbColourData.essence_name(int(s)))
			opts.append("Leave it")
			var pick: String = await _w._dialogue.choose_async(str(p.get("prompt", "Cast what?")), opts)
			var idx := opts.find(pick)
			if idx < 0 or idx >= _adv.progression.spells_known.size():
				return
			action["spell"] = int(_adv.progression.spells_known[idx])
		"pull", "tread", "pass":
			var verb: String = str({"pull": "Pull it", "tread": "Step on it", "pass": "Go through"}[str(action["kind"])])
			var pick: String = await _w._dialogue.choose_async("", [verb, "Leave it"])
			if pick != verb:
				return
	var r := DmbPuzzleLogic.act(p, st, action, ctx)
	for it in r["consume"]:
		_adv.remove_item(str(it))
	if str(r["grant"]) != "":
		await grant_item(str(r["grant"]))
	_adv.set_puzzle_state(key, st)
	_adv.save()
	if str(r["text"]) != "":
		await _w._dialogue.say_async("", str(r["text"]))
	if str(r["spawn_enemy"]) != "":
		await _w.start_battle_request({"id": "%s_wrong%d" % [key.replace("/", "_"), int(st.get("wrong_pulls", 0))], "enemy_id": str(r["spawn_enemy"]), "kind": "creature",
			"intro": "It lands between you and the levers, and it is not pleased to have been dropped."})
		return
	if bool(r["solved_now"]):
		_w.rebuild()
		if dungeon_solved(key.split("/")[0]):
			await _w._dialogue.say_async("", "That was the last room. Above — or below — something heavy unlocks.")
	else:
		_w.rebuild()


## Timed gate: every step in a dungeon area ticks any open gate in that dungeon.
func on_step(area: Dictionary) -> void:
	var d: Dictionary = area.get("dungeon", {})
	if d.is_empty():
		return
	for p in d["puzzles"]:
		if str(p["type"]) != "timed_gate":
			continue
		var key := "%s/%s" % [d["id"], p["id"]]
		var st: Dictionary = _adv.puzzle_state(key)
		if st.is_empty() or not bool(st.get("open", false)):
			continue
		var r := DmbPuzzleLogic.act(p, st, {"kind": "step"}, {})
		_adv.set_puzzle_state(key, st)
		if bool(r["reset"]):
			_w._dialogue.say("", str(r["text"]))
			_w.rebuild()


## Reward plinth in the top room.
func take_reward(e: Dictionary) -> void:
	var did := str(e["dungeon_reward"])
	var d := _flow.sim.dungeons.get_dungeon(did)
	var reward := DmbDungeons.reward_for(d, _adv.progression.spells_known)
	_adv.mark("picked", str(e["id"]))
	if reward.has("spell"):
		_adv.learn_spell(int(reward["spell"]))
		await _w._dialogue.say_async("", "At the top of %s, a colour you did not have. It was always going to be here. That is what these places are for." % str(DmbNodeProjection.node_name(_flow.sim, int(d["node"]))))
		await _w._show_progression_card({"spell": int(reward["spell"])})
	else:
		await grant_item(str(reward["item"]))
		await _w._dialogue.say_async("", "Not magic. Something older, and pointed at a sickness that has not started yet.")
	_adv.save()
	_w.rebuild()


# --- settlement quests ---------------------------------------------------------------

## Dialogue-driven binary tree; a leaf applies effects to the world.
func run_quest(e: Dictionary) -> void:
	var nid := int(e["quest_node"])
	var q := DmbQuests.build(_flow.sim, nid)
	if q.is_empty() or _adv.quest_outcome(nid) != "":
		return
	if str(e.get("quest_npc", "")) != str(q["start"]):
		var who := _npc(q, str(e.get("quest_npc", "")))
		await _w._dialogue.say_async(str(who.get("name", "")), "Talk to %s first. This is their trouble to tell." % _npc(q, str(q["start"]))["name"])
		return
	var node_id := "root"
	var guard := 0
	while guard < 8:
		guard += 1
		if q["outcomes"].has(node_id):
			await _resolve_outcome(nid, q, node_id)
			return
		var n: Dictionary = q["nodes"][node_id]
		var speaker := _npc(q, str(n["speaker"]))
		await _w._dialogue.say_async(str(speaker["name"]), str(n["text"]))
		var labels: Array = []
		for c in n["choices"]:
			labels.append(str(c["label"]))
		var pick: String = await _w._dialogue.choose_async(str(q["title"]), labels)
		var idx := labels.find(pick)
		if idx < 0:
			return
		node_id = str(n["choices"][idx]["next"])


func _npc(q: Dictionary, id: String) -> Dictionary:
	for n in q["npcs"]:
		if str(n["id"]) == id:
			return n
	return {"name": ""}


func _resolve_outcome(nid: int, q: Dictionary, outcome_id: String) -> void:
	var fight := DmbQuests.fight_for(q, outcome_id)
	if fight != "":
		_adv.state["pending_quest"] = {"node": nid, "outcome": outcome_id}
		_adv.save()
		await _w.start_battle_request({"id": "quest_%s_%d" % [q["template"], nid], "enemy_id": fight, "kind": "creature",
			"intro": "It was never wolves."})
		return
	await finish_outcome(nid, q, outcome_id)


## Apply a chosen (or fought-for) outcome. Called directly for talk-only leaves,
## and from the battle return path for fight leaves.
func finish_outcome(nid: int, q: Dictionary, outcome_id: String) -> void:
	var out: Dictionary = q["outcomes"][outcome_id]
	_adv.set_quest_outcome(nid, outcome_id)
	var notes := DmbQuests.apply_effects(_flow.sim, q, outcome_id)
	for eff in out.get("effects", []):
		if eff.has("item"):
			await grant_item(str(eff["item"]))
	_flow._store()
	_adv.save()
	await _w._dialogue.say_async("", str(out["text"]))
	if not notes.is_empty():
		await _w._dialogue.say_async("", "\n".join(PackedStringArray(notes)))
	_w.rebuild()


## Battle returned in a world area: a pending quest fight resolves on victory.
func after_battle(outcome: String) -> void:
	var pend: Dictionary = _adv.state.get("pending_quest", {})
	if pend.is_empty():
		return
	_adv.state.erase("pending_quest")
	if outcome != "victory":
		await _w._dialogue.say_async("", "You come back down without an answer. The trouble is still there, and so are you — which is something.")
		_adv.save()
		return
	var nid := int(pend["node"])
	var q := DmbQuests.build(_flow.sim, nid)
	if not q.is_empty():
		await finish_outcome(nid, q, str(pend["outcome"]))


# ---------------------------------------------------------------------------------
# Catalogue puzzle areas (disposable puzzle-test sessions).
# Adapter/controller only: DmbPuzzleKit is authoritative for rules and state.
# ---------------------------------------------------------------------------------

const _Runner = preload("res://client/scripts/puzzle_test_runner.gd")


## Production area dict for the active test puzzle, via DmbPuzzleProjection.
## Explicit dungeon theme so _is_dungeon() needs no ID-prefix knowledge.
func puzzle_area() -> Dictionary:
	var room: Dictionary = _Runner.kit_room()
	var st: Dictionary = _Runner.kit_state()
	var area: Dictionary = DmbPuzzleProjection.area_for(room, st)
	area["theme"] = "dungeon"
	area["puzzle_test"] = true
	return area


func is_kit_puzzle_area(a: Dictionary) -> bool:
	return bool(a.get("puzzle_test", false))


func kit_ctx(adv: Node) -> Dictionary:
	return {"items": adv.items(), "spells": adv.progression.spells_known}


## Sync the single player inventory (Adventure) into the kit simulation
## mirror before any condition evaluation / projection / action / step.
func kit_sync(adv: Node) -> void:
	DmbPuzzleKit.sync_inventory(_Runner.kit_state(), adv.items())


## Resolve the kit entity dict behind a projected production entity.
## Static room entities resolve via DmbPuzzleKit.entity(); dynamic loose
## world items (projected "pickup" with a "wi:<src>" eid) become a synthetic
## {"kind": "world_item", ...} dict, which Kit.act() resolves by position
## through world_item_at() — never passed to Kit.entity().
func kit_resolve(e: Dictionary) -> Dictionary:
	var room: Dictionary = _Runner.kit_room()
	var eid := str(e.get("puzzle_eid", ""))
	if eid.begins_with("wi:"):
		var pos: Array = (e.get("pos", [0, 0]) as Array).duplicate()
		return {"kind": "world_item", "id": eid, "pos": pos}
	return DmbPuzzleKit.entity(room, eid)


## UI-free application of one kit action. kit_e MUST be an entity Dictionary
## (see kit_resolve) — Kit.act() operates on dicts, never on id strings.
## Applies the domain result to Adventure (single consistent transaction),
## then mirrors inventory back into kit state.
## Returns {"result": r, "solved": bool}.
func kit_apply(adv: Node, kit_e: Dictionary, action: Dictionary) -> Dictionary:
	kit_sync(adv)
	var room: Dictionary = _Runner.kit_room()
	var st: Dictionary = _Runner.kit_state()
	var r: Dictionary = DmbPuzzleKit.act(room, st, kit_e, action, kit_ctx(adv))
	_apply_kit_result(adv, r)
	kit_sync(adv)
	return {"result": r, "solved": bool(st.get("solved", false))}


func _apply_kit_result(adv: Node, r: Dictionary) -> void:
	for item_id in r.get("consume", []):
		adv.remove_item(str(item_id))
	for item_id in r.get("grant", []):
		adv.add_item(str(item_id))
	if int(r.get("learn", -1)) >= 0:
		adv.learn_spell(int(r["learn"]))


## Full production interaction for a projected kit entity: real dialogue/choice
## UI → authoritative Kit.act → Adventure transaction. Returns a summary the
## overworld uses to rebuild/relocate/battle/announce.
func interact_kit_puzzle(e: Dictionary) -> Dictionary:
	var adv := _adv
	kit_sync(adv)
	var st: Dictionary = _Runner.kit_state()
	var ke := kit_resolve(e)
	var ctx := kit_ctx(adv)
	var options: Array = DmbPuzzleKit.actions_for(_Runner.kit_room(), st, ke, ctx)
	if options.is_empty():
		await _w._dialogue.say_async("", str(e.get("text", "Nothing happens.")))
		return {"changed": false, "solved": bool(st.get("solved", false))}
	var action: Dictionary
	if str(ke.get("kind", "")) == "receptacle" and str(st["rec"].get(str(ke.get("id", "")), "")) == "":
		# Riddle receptacle, still empty: always read the inscription first,
		# then offer each carried object as a conscious choice plus Leave.
		# Never auto-insert, even carrying exactly one object.
		action = await _choose_offering(e, ke, options)
		if action.is_empty():
			return {"changed": false, "solved": bool(st.get("solved", false))}
	elif options.size() == 1:
		action = options[0]["action"]
	else:
		var labels: Array = []
		for o in options:
			labels.append(str(o["label"]))
		var picked: String = await _w._dialogue.choose_async(str(e.get("text", "What do you do?")), labels)
		action = {}
		for o in options:
			if str(o["label"]) == picked:
				action = o["action"]
				break
		if action.is_empty():
			return {"changed": false, "solved": bool(st.get("solved", false))}
	var applied := kit_apply(adv, ke, action)
	var r: Dictionary = applied["result"]
	for line in r.get("text", []):
		await _w._dialogue.say_async("", str(line))
	return {
		"changed": bool(r.get("changed", false)),
		"relocate": r.get("relocate"),
		"battle": str(r.get("battle", "")),
		"solved": bool(applied["solved"]),
		"solved_now": bool(r.get("solved_now", false)),
	}


## Riddle-first offering choice for an empty receptacle: the inscription is
## always read aloud, then every carried object is offered plus Leave.
## Returns the chosen install action, or {} when the player walks away.
## Generic — the room data owns the riddle text; no per-room code.
func _choose_offering(e: Dictionary, ke: Dictionary, options: Array) -> Dictionary:
	var riddle := str(e.get("text", ke.get("text", "")))
	if riddle != "":
		await _w._dialogue.say_async("", riddle)
	var place: Array = []
	for o in options:
		if str((o.get("action", {}) as Dictionary).get("kind", "")) == "install":
			place.append(o)
	if place.is_empty():
		return {}
	var labels: Array = []
	for o in place:
		labels.append(str(o["label"]))
	labels.append("Leave")
	var picked: String = await _w._dialogue.choose_async("Give what?", labels)
	for o in place:
		if str(o["label"]) == picked:
			return o["action"]
	return {}


## Kit on-step rules after John enters a tile. Returns the raw kit result
## (relocate/pits/plates/crumble/teleport/hazard hits) with adv applied.
func kit_on_step(adv: Node, pos: Vector2i) -> Dictionary:
	kit_sync(adv)
	var room: Dictionary = _Runner.kit_room()
	var st: Dictionary = _Runner.kit_state()
	var r: Dictionary = DmbPuzzleKit.on_step(room, st, pos, kit_ctx(adv))
	_apply_kit_result(adv, r)
	kit_sync(adv)
	return r


## Kit time rules at a fixed deterministic quantum. Returns raw kit result.
func kit_tick(adv: Node, dt: float) -> Dictionary:
	kit_sync(adv)
	var room: Dictionary = _Runner.kit_room()
	var st: Dictionary = _Runner.kit_state()
	var r: Dictionary = DmbPuzzleKit.tick(room, st, dt)
	_apply_kit_result(adv, r)
	kit_sync(adv)
	return r


## Kit blocking for a tile: the simulation determines reality.
func kit_blocks(pos: Vector2i) -> bool:
	kit_sync(_adv)
	return DmbPuzzleKit.blocks(_Runner.kit_room(), _Runner.kit_state(), pos)


## After a victorious kit-guardian battle: set the guardian's defeated flag
## (the flag named on its own entity dict) so projection hides it and its
## tile stops blocking. Generic — reads the entity, no per-room code.
## Returns true when kit state changed.
func kit_on_battle_result(eid: String, victory: bool) -> bool:
	if not victory or eid == "":
		return false
	var room: Dictionary = _Runner.kit_room()
	var st: Dictionary = _Runner.kit_state()
	var ke := DmbPuzzleKit.entity(room, eid)
	if ke.is_empty():
		return false
	var flag := str(ke.get("defeated_flag", ""))
	if flag == "":
		return false
	st["flags"][flag] = true
	return true


## Production battle-request entity for a kit guardian: real battle scene via
## the normal path, with an explicit puzzle-test policy so story-defeat
## progression can never trigger.
func kit_battle_entity(e: Dictionary, enemy_id: String) -> Dictionary:
	return {
		"id": str(e.get("id", "kit_guardian")),
		"kind": "creature",
		"enemy_id": enemy_id,
		"pos": (e.get("pos", [0, 0]) as Array).duplicate(),
		"policy": "PUZZLE_TEST",
	}
