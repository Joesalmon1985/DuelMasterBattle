extends DmbTestCase
## WU-08: one semantic contract for every meaningful Overworld kind.
## Authored data wins. Decoration is excluded. No invented lore.

const _Adapter = preload("res://sim/world/semantic_adapter.gd")


func run() -> void:
	_test_authored_wins()
	_test_kinds()
	_test_excluded()
	_test_observation_uses_visible_text_only()


func _test_authored_wins() -> void:
	var authored := {"knowledge_key": "authored", "labels": [{"level": 0, "text": "Named"}], "interaction": "npc"}
	var out: Dictionary = _Adapter.adapt({"kind": "npc", "id": "x", "name": "Other", "semantic": authored}, "area")
	assert_eq(str(out.get("knowledge_key", "")), "authored", "authored semantic replaces the fallback")
	assert_eq(str(out.get("labels", [{}])[0].get("text", "")), "Named", "authored label is kept")


func _test_kinds() -> void:
	_expect("npc", {"kind": "npc", "id": "n", "name": "Sage"}, "Sage", "npc")
	_expect("door", {"kind": "door", "id": "d", "text": "A wooden door reinforced with iron bands."}, "Door", "door")
	_expect("entrance", {"kind": "door", "id": "cave", "dungeon_id": "cave1"}, "Dungeon", "entrance")
	_expect("sign", {"kind": "sign", "id": "s", "text": "FORGE"}, "Forge", "sign")
	_expect("pickup", {"kind": "pickup", "id": "p", "sprite": "pendant"}, "Pendant", "pickup")
	_expect("object", {"kind": "logs", "id": "bag"}, "Object", "object")
	_expect("logs", {"kind": "logs", "id": "heap", "text": "A stack of cut timber."}, "Object", "object")
	_expect("corpse", {"kind": "corpse", "id": "body"}, "Body", "object")
	_expect("fire", {"kind": "fire", "id": "f"}, "Fire", "fire")
	_expect("mechanism", {"kind": "logs", "id": "lev", "puzzle_action": {"kind": "pull"}}, "Mechanism", "puzzle")
	_expect("puzzle object", {"kind": "pickup", "id": "bead", "sprite": "glass_bead", "puzzle_eid": "bead"}, "Glass Bead", "puzzle")
	_expect("readable", {"kind": "sign", "id": "clue", "text": "North: the old road."}, "North: the old road.", "sign")
	_expect("building", {"kind": "logs", "id": "mill", "building": "mill"}, "Mill", "building")
	_expect("creature", {"kind": "creature", "id": "fly", "enemy_id": "giant_fly"}, "Giant Fly", "enemy")
	_expect("exit door", {"kind": "exit", "id": "house_door", "to_area": "lane"}, "Door", "entrance")


func _test_excluded() -> void:
	assert_true(_Adapter.adapt({"kind": "deco", "id": "plate", "name": "Plate"}, "a").is_empty(), "decoration is excluded")
	assert_true(_Adapter.adapt({"kind": "trigger", "id": "t", "name": "Start"}, "a").is_empty(), "internal trigger is excluded")
	assert_true(_Adapter.adapt({"kind": "burnt", "id": "ash"}, "a").is_empty(), "burnt state art is excluded")
	assert_true(_Adapter.adapt({"kind": "exit", "id": "mouth"}, "a").is_empty(), "bare exit is not a second object")
	var gate := {"kind": "deco", "id": "gate", "puzzle_room": "pz_01"}
	assert_true(_Adapter.adapt(gate, "a").is_empty(), "puzzle visual-state decoration is excluded")


func _test_observation_uses_visible_text_only() -> void:
	var door: Dictionary = _Adapter.adapt({"kind": "door", "id": "d", "text": "A wooden door reinforced with iron bands."}, "a")
	assert_eq(str(door.get("observe_far", "")), "A wooden door reinforced with iron bands.", "authored visible text is the observation")
	var bare: Dictionary = _Adapter.adapt({"kind": "door", "id": "d2"}, "a")
	assert_eq(str(bare.get("observe_far", "")), "A door.", "fallback observation names only the visible thing")
	assert_true(not str(bare.get("observe_far", "")).contains("King"), "fallback invents no lore")


func _expect(tag: String, entity: Dictionary, label: String, interaction: String) -> void:
	var out: Dictionary = _Adapter.adapt(entity, "sample")
	assert_eq(str(out.get("interaction", "")), interaction, "%s interaction" % tag)
	assert_eq(str(out.get("labels", [{}])[0].get("text", "")), label, "%s label" % tag)
	assert_true(str(out.get("knowledge_key", "")) != "", "%s has a stable key" % tag)
	assert_true(bool(out.get("dismiss_on_move", false)), "%s dismisses on move" % tag)
