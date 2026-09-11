extends DmbTestCase
## pz_01 The Four Offerings: riddle-room data, offering mapping, gate state,
## and projection. All through the generic DmbPuzzleKit / DmbPuzzleProjection
## APIs — no pz_01-specific production logic exists to test.

const Kit = preload("res://sim/world/puzzle_kit.gd")
const Rooms = preload("res://sim/world/puzzle_rooms.gd")
const Items = preload("res://sim/world/items.gd")
const Proj = preload("res://sim/world/puzzle_projection.gd")

const CORRECT := {
	"o1": "mirror_shard",
	"o2": "tallow_candle",
	"o3": "charcoal",
	"o4": "copper_coin",
}
const CANDIDATES := ["mirror_shard", "copper_coin", "charcoal", "tallow_candle", "glass_bead"]
const GATE_POS := Vector2i(6, 2)


func run() -> void:
	_test_data()
	_test_mapping()
	_test_state()
	_test_projection()


func _room() -> Dictionary:
	return Rooms.get_room("pz_01")


func _ent(room: Dictionary, id: String) -> Dictionary:
	return Kit.entity(room, id)


func _ctx(items: Array) -> Dictionary:
	return {"items": items, "spells": []}


func _install(room: Dictionary, st: Dictionary, eid: String, item: String, carried: Array) -> Dictionary:
	return Kit.act(room, st, _ent(room, eid), {"kind": "install", "item": item}, _ctx(carried))


func _recs(room: Dictionary) -> Array:
	var out: Array = []
	for e in room["entities"]:
		if str(e.get("kind", "")) == "receptacle":
			out.append(e)
	return out


func _short(e: Dictionary) -> String:
	# Projection prefixes ids ("puz_pz_01_o1"); the room id is the suffix.
	var parts := str(e.get("puzzle_eid", "")).split("_")
	return parts[-1]


func _test_data() -> void:
	var room := _room()
	assert_true(not room.is_empty(), "pz_01 exists")
	var recs := _recs(room)
	assert_eq(recs.size(), 4, "pz_01 has exactly four riddle receptacles")
	var seen := {}
	for r in recs:
		var t := str(r.get("text", ""))
		assert_true(t != "", "receptacle %s has riddle text" % str(r.get("id", "")))
		assert_true(not seen.has(t), "riddles are all different")
		seen[t] = true
	assert_true(str(_ent(room, "o1").get("text", "")).contains("never move"), "mirror riddle text")
	assert_true(str(_ent(room, "o2").get("text", "")).contains("wind is my enemy"), "candle riddle text")
	assert_true(str(_ent(room, "o3").get("text", "")).contains("pale ash"), "charcoal riddle text")
	assert_true(str(_ent(room, "o4").get("text", "")).contains("no serpent"), "coin riddle text")
	var loose: Array = []
	for e in room["entities"]:
		if str(e.get("kind", "")) == "item":
			loose.append(str(e.get("item", "")))
	assert_eq(loose.size(), 5, "five candidate world items")
	for c in CANDIDATES:
		assert_true(c in loose, "candidate present: " + c)
	assert_true(Items.known("charcoal"), "charcoal is a catalogue item")
	var plaque := _ent(room, "clue")
	assert_true(str(plaque.get("text", "")).contains("One offering has no place here"), "plaque states the rules")


func _test_mapping() -> void:
	var room := _room()
	for eid in CORRECT:
		for item in CANDIDATES:
			var st := Kit.fresh_state(room)
			var r := _install(room, st, eid, item, CANDIDATES.duplicate())
			if item == CORRECT[eid]:
				assert_true(not bool(r.get("rejected", false)), "%s accepts %s" % [eid, item])
				assert_eq(str(st["rec"].get(eid, "")), item, "%s installs %s" % [eid, item])
				assert_true(item in r.get("consume", []), "correct offering leaves inventory")
			else:
				assert_true(bool(r.get("rejected", false)), "%s rejects %s" % [eid, item])
				assert_eq(str(st["rec"].get(eid, "")), "", "wrong offering sets nothing")
				assert_true(r.get("consume", []).is_empty(), "wrong offering is not lost")
				assert_true(str(" ".join(PackedStringArray(r.get("text", [])))).contains("rejects the offering"), "rejection feedback")


func _test_state() -> void:
	var room := _room()
	var gate := _ent(room, "gate")
	# Gate stays shut through 1/4, 2/4, 3/4; opens at 4/4.
	var done: Array = []
	for eid in ["o1", "o2", "o3", "o4"]:
		var st := Kit.fresh_state(room)
		for d in done:
			st["rec"][d] = CORRECT[d]
		st["rec"][eid] = CORRECT[eid]
		done.append(eid)
		var flags := Kit.flags_now(room, st)
		if done.size() < 4:
			assert_true(not Kit.gate_open(gate, flags), "gate closed after %d/4" % done.size())
			assert_true(Kit.blocks(room, st, GATE_POS), "gate tile blocked after %d/4" % done.size())
		else:
			assert_true(Kit.gate_open(gate, flags), "gate opens after 4/4")
			assert_true(not Kit.blocks(room, st, GATE_POS), "gate tile walkable after 4/4")
	# A correct offering sets its flag.
	var st := Kit.fresh_state(room)
	st["rec"]["o3"] = "charcoal"
	assert_true(bool(Kit.flags_now(room, st).get("o3", false)), "charcoal sets o3")


func _test_projection() -> void:
	var room := _room()
	var st := Kit.fresh_state(room)
	var area := Proj.area_for(room, st)
	var alcoves: Array = []
	var alcove_pos := {}
	var overlays: Array = []
	var gate_mark := ""
	for e in area["entities"]:
		if _short(e) in ["o1", "o2", "o3", "o4"] and str(e.get("kind", "")) == "logs":
			alcoves.append(e)
			alcove_pos[e["pos"]] = true
		if _short(e) == "gate" or (str(e.get("kind", "")) == "deco" and not e.has("puzzle_eid") and str(e.get("pos")) == "[6, 2]" and str(e.get("marker", "")).begins_with("puzzle_gate")):
			gate_mark = str(e.get("marker", ""))
			assert_eq(str(e.get("kind", "")), "deco", "gate drawn on its own tile")
	for e in area["entities"]:
		# Installed-item overlays sit on alcove tiles; the goal diamond does not.
		if str(e.get("kind", "")) == "deco" and e.has("puzzle_room") and not e.has("puzzle_eid") and alcove_pos.has(e.get("pos")):
			overlays.append(e)
	assert_eq(alcoves.size(), 4, "four pedestal bases projected")
	for a in alcoves:
		assert_true(str(a.get("marker", "")).begins_with("pedestal_"), "empty receptacle is a pedestal")
	assert_true(overlays.is_empty(), "no installed overlays before solving")
	assert_eq(gate_mark, "puzzle_gate_locked", "unsolved exit projects locked gate")
	assert_true(Kit.blocks(room, st, GATE_POS), "locked state blocked")
	# Solved: each alcove keeps its base and gains its own item overlay.
	for eid in CORRECT:
		st["rec"][eid] = CORRECT[eid]
	var area2 := Proj.area_for(room, st)
	var bases := 0
	var alcove2 := {}
	var marks := {}
	var gate2 := ""
	for e in area2["entities"]:
		if _short(e) in ["o1", "o2", "o3", "o4"] and str(e.get("kind", "")) == "logs":
			bases += 1
			alcove2[e["pos"]] = true
			assert_true(str(e.get("marker", "")).begins_with("pedestal_"), "base remains the pedestal")
		if _short(e) == "gate" or (str(e.get("kind", "")) == "deco" and not e.has("puzzle_eid") and str(e.get("pos")) == "[6, 2]" and str(e.get("marker", "")).begins_with("puzzle_gate")):
			gate2 = str(e.get("marker", ""))
			assert_eq(str(e.get("kind", "")), "deco", "open gate same entity kind/position")
	for e in area2["entities"]:
		if str(e.get("kind", "")) == "deco" and e.has("puzzle_room") and not e.has("puzzle_eid") and alcove2.has(e.get("pos")):
			marks[str(e.get("marker", ""))] = true
			assert_eq(str(e.get("marker_off", "")), "[0, -10]", "installed item floats above its pedestal")
	assert_eq(bases, 4, "four bases after solving")
	assert_eq(marks.size(), 4, "four distinguishable installed items")
	for inst in CORRECT.values():
		assert_true(marks.has(Items.sprite_of(str(inst))), "installed visible: " + str(inst))
	assert_eq(gate2, "puzzle_gate_open", "solved exit projects open gate")
	assert_true(not Kit.blocks(room, st, GATE_POS), "open state walkable")
