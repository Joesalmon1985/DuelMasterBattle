extends SceneTree

## WU-08: non-combat Overworld interaction is semantic, not the Action button.
## Geometry checks are placement only. They do not establish visual quality.
## godot --headless --path godot_project --script res://client/tests/run_semantic_migration.gd

const _VRunner = preload("res://client/scripts/village_test_runner.gd")
const _PRunner = preload("res://client/scripts/puzzle_test_runner.gd")
const _Label = preload("res://client/world/world_interaction_label.gd")

var _failures: Array = []
var _world
var _adv
var _report: Array = []


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
	_test_geometry()
	await _test_e17a()
	await _test_campaign()
	await _test_generated()
	await _test_puzzle()
	_print_report()
	_finish()


func _test_geometry() -> void:
	var view := Rect2(0, 0, 720, 1280)
	var size := Vector2(280, 96)
	var top := _Label.placed_origin(Vector2(40, 10), size, view)
	var edge := _Label.placed_origin(Vector2(710, 400), size, view)
	assert_true(_inside(Rect2(top, size), view), "speech near the top stays in the viewport")
	assert_true(_inside(Rect2(edge, size), view), "speech near the right edge stays in the viewport")
	var label_size := Vector2(120, 48)
	var edge_label := _Label.placed_origin(Vector2(4, 640), label_size, view)
	assert_true(_inside(Rect2(edge_label, label_size), view), "a label whose anchor is on the edge stays in view")


func _test_e17a() -> void:
	await _boot_e17a()
	var npcs := _entities_of("npc")
	assert_true(npcs.size() >= 3, "E17A has more than Miner and Miller")
	var labeled := 0
	for e in npcs:
		if _key_for(str(e.get("id", ""))) != "":
			labeled += 1
	var npc_ok: bool = labeled == npcs.size() and labeled >= 3
	assert_true(npc_ok, "every loaded E17A NPC has a semantic label (%d/%d)" % [labeled, npcs.size()])
	var miner := _key_for("a")
	var far_ok := await _distant_observes(miner, "a")
	var near_ok := await _near_npc_speaks(miner, "a")
	_row("NPC", npc_ok and miner != "", far_ok, near_ok)
	var building_key := ""
	var building_id := ""
	for e in _entities_of("sign"):
		var key := _key_for(str(e.get("id", "")))
		if _label_text(key) in ["Forge", "Mill", "Village Hall", "Farmstead", "General Store"]:
			building_key = key
			building_id = str(e.get("id", ""))
			break
	var building_ok: bool = building_key != ""
	assert_true(building_ok, "a village building sign has a semantic label")
	var b_far := await _distant_observes(building_key, building_id)
	var b_near := await _near_inspects(building_key, building_id)
	_row("BUILDING", building_ok, b_far, b_near)
	await _test_inquiry(miner)
	await _free()
	_VRunner.end(_adv)


func _test_inquiry(miner_key: String) -> void:
	_collapse(miner_key)
	_stand_near("a")
	_world.ui_tap_semantic(miner_key)
	await process_frame
	_world.ui_tap_semantic(miner_key)
	await process_frame
	var choices: Array = _world.ui_semantic_responses(miner_key)
	assert_true(choices.size() >= 3, "Miner decision offers at least three responses (got %d)" % choices.size())
	_world.ui_tap_semantic_response(miner_key, choices.size() - 1)
	await process_frame
	assert_eq(str(_VRunner.quest_state().get("current_node", "")), "scene_01_a", "inquiry does not leave the decision")
	assert_true(not _VRunner.quest_state().get("flags", {}).has("scene_01_branch_a"), "inquiry does not set branch A")
	assert_true(not _VRunner.quest_state().get("flags", {}).has("scene_01_branch_b"), "inquiry does not set branch B")
	await create_timer(0.45).timeout
	_world.ui_tap_semantic(miner_key)
	await process_frame
	assert_eq(str(_entry(miner_key).get("state", "")), "RESPONSES", "inquiry returns to the unresolved decision")
	assert_eq(_world.ui_semantic_selected(miner_key), -1, "returning to the decision selects nothing")


func _test_campaign() -> void:
	await _boot_campaign("village", Vector2i(11, 6))
	await _object_row("DOOR", "door", "v_door1")
	await _object_row("SIGN", "sign", "village_sign")
	await _object_row("OBJECT", "logs", "v_logs")
	var npc_key := _key_for("elder")
	var npc_far := await _distant_observes(npc_key, "elder")
	var npc_near := await _campaign_npc("elder")
	assert_true(npc_key != "" and npc_far and npc_near, "legacy village NPC uses the semantic path")
	await _load("forest_deep", Vector2i(4, 11))
	await _object_row("PICKUP", "pickup", "fire_pendant")
	await _load("forest_deep", Vector2i(9, 13))
	await _object_row("FIRE", "fire", "fire_d5")
	assert_true(_world.ui_entity_exists("fire_d5"), "blocked fire interaction does not douse")
	await _load("trial_road", Vector2i(13, 10))
	_adv.learn_spell(0)
	await _enemy_row()
	await _free()


func _test_generated() -> void:
	await _boot_generated(5, 8)
	var npc := _first_of("npc")
	var building := _first_building()
	var g_npc := npc != ""
	var g_far := await _distant_observes(_key_for(npc), npc) if g_npc else false
	var g_near := await _campaign_npc(npc) if g_npc else false
	_row("GENERATED NPC", g_npc, g_far, g_near)
	var b_ok: bool = building != "" and _key_for(building) != ""
	var b_far := await _distant_observes(_key_for(building), building) if b_ok else false
	var b_near := await _near_inspects(_key_for(building), building) if b_ok else false
	_row("GENERATED BUILDING", b_ok, b_far, b_near)
	var dungeon_node := int(_dungeon_node())
	await _free()
	if dungeon_node >= 0:
		await _boot_generated(5, dungeon_node)
	var entrance := _first_entrance()
	var e_ok: bool = entrance != "" and _key_for(entrance) != ""
	var before := str(_world.area_id) if _world != null else ""
	var e_far := await _distant_observes(_key_for(entrance), entrance) if e_ok else false
	if e_ok:
		assert_eq(_world.area_id, before, "distant entrance observation does not travel")
	var e_near := false
	if e_ok:
		_collapse(_key_for(entrance))
		_stand_near(entrance)
		_world.ui_tap_semantic(_key_for(entrance))
		e_near = await _choose_when_ready("Enter")
		var frames := 0
		while frames < 180 and _world.area_id == before:
			await process_frame
			frames += 1
		e_near = e_near and _world.area_id != before
	assert_true(e_near, "nearby entrance reaches existing enter behaviour")
	_row("ENTRANCE", e_ok, e_far, e_near)
	await _free()
	_VRunner.end(_adv)


func _test_puzzle() -> void:
	_PRunner.set_puzzle("pz_06")
	_world = load("res://client/scenes/overworld.tscn").instantiate()
	_world.test_mode = true
	root.add_child(_world)
	for _i in 8:
		await process_frame
	var lever := ""
	for e in _world.area.get("entities", []):
		if str(e.get("kind", "")) == "logs" and e.has("puzzle_eid"):
			lever = str(e.get("id", ""))
			break
	var key := _key_for(lever)
	var ok: bool = lever != "" and key != ""
	var before: Dictionary = _PRunner.kit_state().get("flags", {})
	var far := await _distant_observes(key, lever) if ok else false
	var unchanged: bool = str(_PRunner.kit_state().get("flags", {})) == str(before)
	assert_true(unchanged, "distant mechanism observation does not pull it")
	var near := false
	if ok:
		_collapse(key)
		_stand_near(lever)
		_world.ui_tap_semantic(key)
		await _choose_when_ready("Pull")
		for _i in 8:
			await process_frame
		var flags: Dictionary = _PRunner.kit_state().get("flags", {})
		var levers: Dictionary = _PRunner.kit_state().get("levers", {})
		near = bool(flags.get("gate_open", false)) or not levers.is_empty()
	assert_true(near, "nearby mechanism reaches the existing pull")
	_row("PUZZLE/MECHANISM", ok, far and unchanged, near)
	await _free()
	if _PRunner.is_active():
		_PRunner.end(_adv)
	else:
		_PRunner.clear()


func _object_row(name: String, kind: String, id: String) -> void:
	var key := _key_for(id)
	var ok: bool = key != ""
	var area_before := str(_world.area_id)
	var far := await _distant_observes(key, id) if ok else false
	if ok and kind == "pickup":
		assert_true(not _adv.progression.knows(0), "distant pickup tap does not grant")
	if ok and kind == "fire":
		assert_true(_world.ui_entity_exists(id), "distant fire tap does not douse")
	var near := false
	if ok:
		_collapse(key)
		_stand_near(id)
		_world.ui_tap_semantic(key)
		await _drain_box(16)
		if kind == "pickup":
			near = _adv.progression.knows(0)
		elif kind == "fire":
			near = _world.ui_entity_exists(id) and _saw_speech(key)
		else:
			near = _saw_speech(key) and _world.area_id == area_before
		assert_true(not _world.ui_dialogue_panel_visible(), "%s result is not the old dialogue panel" % name)
		assert_true(not _world.ui_action_button_visible(), "%s does not require the Action button" % name)
	_row(name, ok, far, near)


func _enemy_row() -> void:
	var id := "fly_road1"
	var key := _key_for(id)
	var ok: bool = key != ""
	var far := await _distant_observes(key, id) if ok else false
	assert_true(_adv.pending_battle.is_empty(), "distant enemy observation does not start combat")
	var near := false
	if ok:
		_collapse(key)
		_stand_near(id)
		_world.ui_tap_semantic(key)
		near = await _choose_when_ready("Walk away")
		await process_frame
		near = near and _adv.pending_battle.is_empty()
		assert_true(not _world.ui_dialogue_panel_visible(), "enemy choice is not the old dialogue panel")
	_row("WORLD ENEMY", ok, far, near)


func _campaign_npc(id: String) -> bool:
	var key := _key_for(id)
	if key == "":
		return false
	_collapse(key)
	_stand_near(id)
	_world.ui_tap_semantic(key)
	await _drain_box(8)
	return _saw_speech(key) and not _world.ui_dialogue_panel_visible() and not _world.ui_action_button_visible()


func _distant_observes(key: String, id: String) -> bool:
	if key == "" or id == "":
		return false
	_collapse(key)
	_stand_away(id)
	_world.ui_tap_semantic(key)
	await process_frame
	return str(_entry(key).get("state", "")) == "OBSERVATION" and not _world.ui_action_button_visible()


func _near_npc_speaks(key: String, id: String) -> bool:
	if key == "":
		return false
	_collapse(key)
	_stand_near(id)
	_world.ui_tap_semantic(key)
	await process_frame
	return str(_entry(key).get("state", "")) == "SPEECH" and not _world.ui_dialogue_open() and not _world.ui_action_button_visible()


func _near_inspects(key: String, id: String) -> bool:
	if key == "":
		return false
	_collapse(key)
	_stand_near(id)
	_world.ui_tap_semantic(key)
	await _drain_box(6)
	return _saw_speech(key) and not _world.ui_dialogue_panel_visible() and not _world.ui_action_button_visible()


func _choose_when_ready(label: String) -> bool:
	for _i in 40:
		if _world.ui_dialogue_waiting_choice():
			_world.ui_dialogue_choose(label)
			return true
		if _world.ui_dialogue_open():
			_world.ui_dialogue_advance()
		await process_frame
	return false


func _drain_box(lines: int) -> void:
	for _i in lines * 4:
		if _world.ui_dialogue_waiting_choice():
			return
		if _world.ui_dialogue_open():
			_world.ui_dialogue_advance()
		await process_frame


func _saw_speech(key: String) -> bool:
	var text := str(_entry(key).get("text", ""))
	return text != "" and str(_entry(key).get("state", "")) in ["SPEECH", "LABEL", "OBSERVATION"]


func _collapse(key: String) -> void:
	var lbl = _world.ui_semantic_label(key)
	if lbl != null:
		lbl.collapse()


func _stand_near(id: String) -> void:
	_stand(id, Vector2i(0, 1))


func _stand_away(id: String) -> void:
	_stand(id, Vector2i(0, 3))


func _stand(id: String, offset: Vector2i) -> void:
	var pos := Vector2i.ZERO
	for e in _world._entities:
		if str(e.get("id", "")) == id:
			pos = Vector2i(int(e["pos"][0]), int(e["pos"][1]))
			break
	_world._john_pos = pos + offset
	_world._john_facing = "up"
	_world._moving = false
	_world._john.position = Vector2(_world._john_pos) * 64


func _boot_e17a() -> void:
	_adv.new_game()
	_VRunner.set_profile("E17A")
	_world = load("res://client/scenes/overworld.tscn").instantiate()
	_world.test_mode = true
	root.add_child(_world)
	for _i in 12:
		await process_frame


func _boot_campaign(area: String, at: Vector2i) -> void:
	_adv.new_game()
	_adv.set_flag("opening_seen")
	_adv.set_location(area, at.x, at.y, "down")
	_world = load("res://client/scenes/overworld.tscn").instantiate()
	_world.test_mode = true
	root.add_child(_world)
	for _i in 8:
		await process_frame


func _boot_generated(seed: int, nid: int) -> void:
	_adv.new_game()
	_adv.set_flag("opening_seen")
	_VRunner.set_generated(seed, nid)
	_world = load("res://client/scenes/overworld.tscn").instantiate()
	_world.test_mode = true
	root.add_child(_world)
	for _i in 8:
		await process_frame


func _load(area: String, at: Vector2i) -> void:
	_world.load_area(area, at, "down")
	for _i in 4:
		await process_frame


func _free() -> void:
	if _world != null and is_instance_valid(_world):
		_world.queue_free()
		_world = null
	await process_frame


func _entities_of(kind: String) -> Array:
	var out: Array = []
	for e in _world.area.get("entities", []):
		if str(e.get("kind", "")) == kind:
			out.append(e)
	return out


func _first_of(kind: String) -> String:
	var found := _entities_of(kind)
	return str(found[0].get("id", "")) if not found.is_empty() else ""


func _first_building() -> String:
	for e in _world._entities:
		if str(e.get("kind", "")) == "logs" and str(e.get("building", "")) != "":
			return str(e.get("id", ""))
	return ""


func _dungeon_node() -> int:
	var sim = _VRunner.generated_sim()
	if sim == null:
		return -1
	for raw in sim.dungeons.dungeons:
		if raw is Dictionary and int((raw as Dictionary).get("node", -1)) >= 0:
			return int((raw as Dictionary)["node"])
	return -1


func _first_entrance() -> String:
	for e in _world._entities:
		if str(e.get("kind", "")) == "door" and str(e.get("dungeon_id", "")) != "":
			return str(e.get("id", ""))
	return ""


func _key_for(id: String) -> String:
	if id == "":
		return ""
	for raw in _world.ui_semantic_labels():
		if str(raw.get("entity_id", "")) == id:
			return str(raw.get("key", ""))
	return ""


func _entry(key: String) -> Dictionary:
	for raw in _world.ui_semantic_labels():
		if str(raw.get("key", "")) == key:
			return raw
	return {}


func _label_text(key: String) -> String:
	var lbl = _world.ui_semantic_label(key)
	return str(lbl.display_text()) if lbl != null else ""


func _row(name: String, label_ok: bool, far_ok: bool, near_ok: bool) -> void:
	var line := "%s semantic_label=%s distant_observation=%s near_interaction=%s old_action_required=NO" % [
		name,
		"PASS" if label_ok else "FAIL",
		"PASS" if far_ok else "FAIL",
		"PASS" if near_ok else "FAIL",
	]
	_report.append(line)
	print("WU08_REPORT %s" % line)
	if not _world.ui_action_button_visible():
		pass
	else:
		_failures.append("%s still shows the Action button" % name)
	if not (label_ok and far_ok and near_ok):
		_failures.append(line)


func _inside(rect: Rect2, view: Rect2) -> bool:
	return view.encloses(rect)


func _print_report() -> void:
	print("WU08_REPORT_BEGIN")
	for line in _report:
		print(line)
	print("WU08_REPORT_END")


func _finish() -> void:
	if _failures.is_empty():
		print("ALL PASSED")
	else:
		for f in _failures:
			print("FAIL: %s" % f)
		print("%d FAILURES" % _failures.size())
	quit(0 if _failures.is_empty() else 1)


func assert_true(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)


func assert_eq(actual, expected, msg: String) -> void:
	if actual != expected:
		_failures.append("%s expected %s got %s" % [msg, str(expected), str(actual)])
