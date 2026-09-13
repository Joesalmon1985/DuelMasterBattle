extends DmbTestCase
## E17A fixture: visible roles, and the opening talk is not silent.
## Internal ids stay a, b, c — story binding uses those, not the label.


func run() -> void:
	_test_visible_roles()
	_test_opening_talk_has_turns()


func _test_visible_roles() -> void:
	var area := VillageCompositeProjection.project("E17A")
	var by_id := {}
	for e in area["entities"]:
		if str(e.get("kind", "")) == "npc":
			by_id[str(e["id"])] = e
	assert_eq(str(by_id["a"]["id"]), "a", "miner id stays a")
	assert_eq(str(by_id["a"]["name"]), "Miner", "miner visible name")
	assert_eq(str(by_id["b"]["id"]), "b", "distiller id stays b")
	assert_eq(str(by_id["b"]["name"]), "Distiller", "distiller visible name")
	assert_eq(str(by_id["c"]["name"]), "Reeve", "reeve visible name")
	assert_eq(str(by_id["d"]["name"]), "Storekeeper", "storekeeper visible name")
	for id in by_id:
		var name := str(by_id[id]["name"])
		assert_true(name.length() > 1, "npc %s is not labelled with a single letter (%s)" % [id, name])


func _test_opening_talk_has_turns() -> void:
	VillageQuestRunner.begin("E17A")
	var npc := VillageQuestRunner.expected_npc()
	var node := VillageQuestRunner.current_node_id()
	assert_eq(npc, "a", "opening node is the miner")
	assert_eq(node, "scene_01_a", "opening node id")
	var result: Dictionary = VillageQuestRunner.interact_npc(npc)
	assert_true(bool(result.get("success", false)), "opening talk succeeds")
	var turns: Array = result.get("turns", [])
	var spoken := 0
	for raw in turns:
		if raw is Dictionary and str((raw as Dictionary).get("text", "")) != "":
			spoken += 1
	assert_true(spoken > 0, "opening interaction returns non-empty turns (got %d)" % turns.size())
	if str(result.get("type", "")) == "choice":
		var chosen: Dictionary = VillageQuestRunner.make_choice(0)
		var after: Array = chosen.get("turns", [])
		assert_true(after.size() > 0, "choosing still returns the authored dialogue.json turns")
	VillageQuestRunner.clear()
