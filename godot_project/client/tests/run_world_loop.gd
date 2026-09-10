extends SceneTree
## Next Pass end-to-end: Jane's house → world → settlement (quest with a real
## world effect) → the settlement's tower → four rooms answered through the UI
## interaction layer → reward (a new colour) → save/load keeps all of it.

var _failures: Array = []
var _world
var _adv


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	for pair in [["EncounterSession", "res://client/scripts/encounter_session.gd"], ["Sfx", "res://client/scripts/sfx.gd"], ["Adventure", "res://client/scripts/adventure.gd"]]:
		if root.get_node_or_null(pair[0]) == null:
			var n = load(pair[1]).new()
			n.name = pair[0]
			root.add_child(n)
	_adv = root.get_node("Adventure")
	_adv.delete_save()
	await process_frame
	await _test_loop()
	_report()


func _enter_world() -> void:
	_adv.new_game()
	_adv.set_flag("opening_seen")
	_adv.set_flag("jane_placeholder_seen")
	for ph in ["john_intro", "ashby_training", "pre_trial", "post_trial_recovery"]:
		_adv.advance_phase(ph)
	_adv.learn_spell(1)
	_adv.learn_spell(6)
	_adv.learn_spell(0)
	_adv.grow_weave(3)
	_adv.add_item("jane_letter")
	_adv.state["area"] = "jane_placeholder"
	_adv.state["pos"] = [4, 4]
	await _new_world()
	assert_eq(_world.area_id, "jane_placeholder", "starts at Jane's")
	await _wait_ready()
	_world.set_john_pos(Vector2i(4, 5), "down")
	_world.ui_step(Vector2i(0, 1))
	await _settle("jane_placeholder")
	assert_true(_world.area_id.begins_with("wn_"), "into the world (%s)" % _world.area_id)


func _test_loop() -> void:
	await _enter_world()
	var sim: DmbWorldSim = _world._world_flow.sim
	var home := sim.player_home_node()
	# §2 inventory visible; §4 the home steading is dressed from the sim.
	assert_true(_world.ui_items_button_visible(), "Pockets button shows in the world")
	assert_true(_adv.has_item("jane_letter"), "Jane's letter is in the pockets")
	var prof: Dictionary = _world.area["profile"]
	assert_true(prof["kind"] in ["steading", "town"], "home node is a settlement (%s)" % prof["kind"])
	var workers := 0
	var quest_npc: Dictionary = {}
	var buildings := 0
	for e in _world.area["entities"]:
		if e.has("worker"):
			workers += 1
		if e.has("building"):
			buildings += 1
		if e.has("quest_id") and str(e.get("quest_npc", "")) == str(DmbQuests.build(sim, home)["start"]):
			quest_npc = e
	assert_true(workers >= 1, "workers about the steading")
	assert_true(buildings >= 2, "buildings from the profile (%d)" % buildings)
	assert_true(not quest_npc.is_empty(), "the local quest's first speaker is here")
	# §5: run the quest through the UI, picking the first option every time
	# (a talk-only or fight leaf either way; we drive whichever we get).
	var q := DmbQuests.build(sim, home)
	var pos := Vector2i(int(quest_npc["pos"][0]), int(quest_npc["pos"][1]))
	_world.set_john_pos(pos + Vector2i(0, 1), "up")
	await process_frame
	assert_true(_world.ui_prompt().begins_with("Talk"), "quest npc prompt: %s" % _world.ui_prompt())
	var mood_before := str(sim.settlement_moods.get(home, ""))
	_world.ui_action()
	var guard := 0
	while guard < 400 and _adv.quest_outcome(home) == "" and _adv.pending_battle.is_empty():
		guard += 1
		await process_frame
		if _world.ui_dialogue_waiting_choice():
			_world.ui_dialogue_choose_index(0)
		elif _world.ui_dialogue_open():
			_world.ui_dialogue_advance()
	if not _adv.pending_battle.is_empty():
		# Fight leaf: win it and come back.
		assert_true(_adv.state.has("pending_quest"), "fight leaf records the pending quest")
		_adv.report_battle_result("victory")
		await _reload_world()
		await _drain()
	assert_true(_adv.quest_outcome(home) != "", "quest reached an outcome (%s)" % _adv.quest_outcome(home))
	var out: Dictionary = q["outcomes"].get(_adv.quest_outcome(home), {})
	assert_true(not out.is_empty(), "outcome is one of the template's leaves")
	var sim2: DmbWorldSim = _world._world_flow.sim
	assert_true(str(sim2.settlement_moods.get(home, "")) != mood_before or out.get("effects", []).is_empty(), "outcome left a mood on the settlement")
	await _drain()
	# Persisted: the NPC now says the aftermath line.
	_world.rebuild()
	await process_frame
	var after_lines: Array = _world.ui_npc_lines_for(str(quest_npc["id"]))
	assert_true(after_lines.size() >= 1 and not _world.ui_entity_has_choice_event(str(quest_npc["id"])), "quest npc switched to aftermath")
	# §6: the home settlement's tower. Walk there node by node.
	var d := sim2.dungeons.by_settlement(home)
	assert_true(not d.is_empty(), "home settlement has a dungeon")
	assert_eq(str(d["kind"]), "tower", "founding settlements get towers")
	var path := _path(sim2, home, int(d["node"]))
	assert_true(path.size() >= 2, "route to the tower exists (%d)" % path.size())
	for i in range(1, path.size()):
		await _walk_to_node(int(path[i]))
	assert_eq(_world.area_id, "wn_%d" % int(d["node"]), "arrived at the tower node")
	var door: Dictionary = {}
	for e in _world.area["entities"]:
		if e.has("dungeon_id"):
			door = e
	assert_true(not door.is_empty(), "tower door on the node")
	_world.set_john_pos(Vector2i(int(door["pos"][0]), int(door["pos"][1]) + 1), "up")
	await process_frame
	assert_eq(_world.ui_prompt(), "Enter", "door prompt")
	_world.ui_action()
	await _answer_choice("Enter")
	await _settle("wn_%d" % int(d["node"]))
	assert_true(DmbDungeonMap.is_dungeon_area(_world.area_id), "inside the dungeon (%s)" % _world.area_id)
	# §7/§8: solve the four rooms, importing the dependency item the way a player
	# would have — from the source dungeon (we grant it, standing for that trip).
	var need := str(d["needs"]["item"])
	_adv.add_item(need)
	for room in range(4):
		var p: Dictionary = d["puzzles"][room]
		var key := "%s/%s" % [d["id"], p["id"]]
		await _solve_room(d, p, key, room)
		assert_true(bool(_adv.puzzle_state(key).get("solved", false)), "room %d (%s) solved" % [room, p["type"]])
	assert_true(_world._play.dungeon_solved(str(d["id"])), "dungeon complete")
	# Reward: a colour John does not have.
	_world.rebuild()
	await process_frame
	var known_before: int = _adv.progression.spells_known.size()
	var reward_pos := Vector2i(5, DmbDungeonMap.room_origin_y(3) + 5)
	_world.set_john_pos(reward_pos + Vector2i(0, -1), "down")
	await process_frame
	assert_eq(_world.ui_prompt(), "Take", "reward prompt")
	_world.ui_action()
	await _drain(400)
	assert_eq(_adv.progression.spells_known.size(), known_before + 1, "dungeon grants a new colour")
	# Sigil for the network.
	_world.set_john_pos(reward_pos + Vector2i(2, -1), "down")
	await process_frame
	_world.ui_action()
	await _drain(400)
	assert_true(_adv.has_item(str(d["provides"])), "the tower's sigil is in the pockets")
	# Save/load keeps items, puzzles, quests, moods.
	_adv.save()
	var items_before: Array = _adv.items().duplicate()
	var snap: String = _world._world_flow.sim.snapshot()
	await _free_world()
	assert_true(_adv.load_game(), "reload")
	assert_eq(_adv.items(), items_before, "items persist")
	assert_true(_adv.quest_outcome(home) != "", "quest outcome persists")
	var wf := WorldFlow.new()
	wf.setup(_adv)
	assert_eq(wf.sim.snapshot(), snap, "world (with moods and dungeons) survives save/load")
	assert_true(wf.sim.dungeons.dungeons.size() >= 8, "dungeons survive save/load (%d)" % wf.sim.dungeons.dungeons.size())


func _solve_room(d: Dictionary, p: Dictionary, key: String, room: int) -> void:
	var aid := DmbDungeonMap.area_id(d)
	match str(p["type"]):
		"offerings":
			await _take_item_in_room(p)
			for sl in p["slots"]:
				await _use_at("%s_%s" % [aid, sl["id"]], DmbItems.name_of(str(sl["item"])))
		"exchange":
			await _take_item_in_room(p)
			await _use_at("%s_%s" % [aid, p["pedestal"]], "Place " + DmbItems.name_of(str(p["items"][0])))
			await _use_at("%s_%s" % [aid, p["pedestal"]], "Take the key")
		"switch_chain":
			for i in p["order"]:
				await _use_at("%s_%s" % [aid, p["levers"][int(i)]], "Pull it")
		"plate_hold":
			await _take_item_in_room(p)
			await _use_at("%s_%s" % [aid, p["plate"]], DmbItems.name_of("grey_stone"))
		"timed_gate":
			await _use_at("%s_%s" % [aid, p["lever"]], "Pull it")
			await _use_at("%s_%s_gate" % [aid, p["id"]], "Go through")
		"mosaic":
			for i in p["order"]:
				await _use_at("%s_%s_tile%d" % [aid, p["id"], int(i)], "Step on it")
		"magic_target":
			await _use_at("%s_%s" % [aid, p["target"]], DmbColourData.essence_name(int(p["spell"])))
		"two_levers":
			await _use_at("%s_%s" % [aid, p["levers"][int(p["correct"])]], "Pull it")


func _take_item_in_room(p: Dictionary) -> void:
	for it in p["items"]:
		var e := _entity_with_grant_item(str(it))
		if e.is_empty():
			continue
		_stand_by(e)
		_world.ui_action()
		await _drain(300)
		assert_true(_adv.has_item(str(it)), "picked up %s" % it)


func _entity_with_grant_item(item: String) -> Dictionary:
	for e in _world.area["entities"]:
		if e.get("grant", {}).get("item", "") == item:
			return e
	return {}


func _use_at(eid: String, choice: String) -> void:
	var e: Dictionary = {}
	for x in _world.area["entities"]:
		if str(x.get("id", "")) == eid:
			e = x
	assert_true(not e.is_empty(), "entity %s present" % eid)
	if e.is_empty():
		return
	_stand_by(e)
	_world.ui_action()
	await _answer_choice(choice)
	await _drain(300)


func _stand_by(e: Dictionary) -> void:
	var p := Vector2i(int(e["pos"][0]), int(e["pos"][1]))
	var below := p + Vector2i(0, 1)
	if _world.ui_tile_walkable(below):
		_world.set_john_pos(below, "up")
	elif _world.ui_tile_walkable(p + Vector2i(0, -1)):
		_world.set_john_pos(p + Vector2i(0, -1), "down")
	elif _world.ui_tile_walkable(p + Vector2i(1, 0)):
		_world.set_john_pos(p + Vector2i(1, 0), "left")
	else:
		_world.set_john_pos(p + Vector2i(-1, 0), "right")


func _answer_choice(label: String) -> void:
	for i in range(300):
		await process_frame
		if _world.ui_dialogue_waiting_choice():
			_world.ui_dialogue_choose(label)
			return
		if _world.ui_dialogue_open():
			_world.ui_dialogue_advance()
	_failures.append("choice '%s' never offered" % label)


func _path(sim: DmbWorldSim, from: int, to: int) -> Array:
	var prev := {from: -1}
	var queue := [from]
	while not queue.is_empty():
		var n: int = queue.pop_front()
		if n == to:
			break
		for nb in sim.board.node_neighbors(n):
			if not prev.has(nb):
				prev[nb] = n
				queue.append(nb)
	if not prev.has(to):
		return []
	var out := [to]
	while out[0] != from:
		out.push_front(prev[out[0]])
	return out


func _walk_to_node(nid: int) -> void:
	var target := "wn_%d" % nid
	var prev: String = _world.area_id
	for e in _world.area["entities"]:
		if e["kind"] == "exit" and str(e["to_area"]) == target:
			var p := Vector2i(int(e["pos"][0]), int(e["pos"][1]))
			var dir := Vector2i(0, -1) if p.y == 0 else Vector2i(0, 1)
			_world.set_john_pos(p - dir, "up" if dir.y < 0 else "down")
			_world.ui_step(dir)
			await _settle(prev)
			return
	_failures.append("no exit from %s to %s" % [prev, target])


func _new_world() -> void:
	_world = load("res://client/scenes/overworld.tscn").instantiate()
	_world.test_mode = true
	root.add_child(_world)
	await process_frame
	await process_frame


func _reload_world() -> void:
	var area: String = _world.area_id
	await _free_world()
	await _new_world()
	assert_eq(_world.area_id, area, "reload lands in the same area")


func _free_world() -> void:
	_world.queue_free()
	await process_frame
	await process_frame


func _settle(prev_area: String = "") -> void:
	await process_frame
	await process_frame
	var guard := 0
	while guard < 900:
		guard += 1
		await process_frame
		if _world.ui_dialogue_waiting_choice():
			return
		if _world.ui_dialogue_open():
			_world.ui_dialogue_advance()
			continue
		if prev_area != "" and _world.area_id == prev_area:
			continue
		if not _world.ui_input_locked() and not _world.ui_is_moving():
			await process_frame
			return
	_failures.append("travel did not settle")


func _drain(frames: int = 240) -> void:
	for i in range(frames):
		await process_frame
		if _world.ui_dialogue_waiting_choice():
			return
		if _world.ui_dialogue_open():
			_world.ui_dialogue_advance()
		elif not _world.ui_input_locked():
			return


func _wait_ready() -> void:
	var g := 0
	while (_world.ui_input_locked() or _world.ui_dialogue_open()) and g < 600:
		if _world.ui_dialogue_open():
			_world.ui_dialogue_advance()
		await process_frame
		g += 1


func assert_true(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)
		print("  FAIL: %s" % msg)


func assert_eq(a, b, msg: String) -> void:
	if a != b:
		_failures.append("%s expected %s got %s" % [msg, str(b), str(a)])
		print("  FAIL: %s expected %s got %s" % [msg, str(b), str(a)])


func _report() -> void:
	if _failures.is_empty():
		print("WORLD LOOP: ALL PASSED")
		quit(0)
	else:
		print("WORLD LOOP: %d FAILED" % _failures.size())
		quit(1)
