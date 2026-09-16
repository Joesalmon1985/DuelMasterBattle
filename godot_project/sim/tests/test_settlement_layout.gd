extends DmbTestCase
## Phase 2: the production settlement generator. Every settlement/town of a
## seeded world is laid out by DmbSettlementLayout from its canonical
## DmbSettlementProfile, and the result must be large, coherent, deterministic
## and visibly different between settlements — and between steadings and towns.
##
## Reproduce any case with:
##   godot --headless --path godot_project --script res://sim/tools/settlement_report.gd -- <seed> <turns> <node>

## Three contrasting canonical cases (seed, turns, node) — see PHASE 2 report.
const CANON := [
	[5, 30, 22],   # John's home steading (Wardens), forest family
	[5, 30, 8],    # Drover Compact town: 3 products, 4 works, tower, 3 roads
	[5, 30, 16],   # Levy town, infection 3 (overrun): idle works, demons at the gate
]
## Broader deterministic sweep: every settlement of these worlds.
const SWEEP_SEEDS := [5, 7, 11, 23]
const TURNS := 30


func run() -> void:
	for c in CANON:
		_check_case(int(c[0]), int(c[1]), int(c[2]), true)
	var total := 0
	var towns := 0
	var sizes := {}
	for seed in SWEEP_SEEDS:
		var sim := _world(int(seed), TURNS)
		var ids: Array = sim.catan.settlements.keys()
		ids.sort()
		for nid in ids:
			var a := _check_case(int(seed), TURNS, int(nid), false, sim)
			total += 1
			if a["profile"]["kind"] == "town":
				towns += 1
			var key := "%dx%d" % [int(a["layout"]["w"]), int(a["layout"]["h"])]
			sizes[key] = int(sizes.get(key, 0)) + 1
	assert_true(total >= 10, "sweep covers at least 10 generated settlements (%d)" % total)
	assert_true(towns >= 2, "sweep includes towns (%d)" % towns)
	assert_true(sizes.size() >= 3, "map sizes vary with the profile, not one fixed slot layout (%s)" % str(sizes))
	_check_steading_vs_town()
	_check_distinct_layouts()
	_check_core_and_roads()
	_check_production_dressing()
	_check_crossings()


func _world(seed: int, turns: int) -> DmbWorldSim:
	var sim := DmbWorldSim.new(seed)
	sim.setup()
	for i in range(turns):
		sim.advance_turn()
	return sim


## Full structural check of one generated settlement. Returns the area.
func _check_case(seed: int, turns: int, nid: int, canonical: bool, sim: DmbWorldSim = null) -> Dictionary:
	if sim == null:
		sim = _world(seed, turns)
	var tag := "seed %d node %d" % [seed, nid]
	assert_true(sim.catan.settlements.has(nid), "%s is a settlement" % tag)
	var p := DmbSettlementProfile.describe(sim, nid)
	var a := DmbNodeProjection.area_for(sim, nid)
	var rows: Array = a["rows"]
	var lay: Dictionary = a["layout"]
	var w := int(lay["w"])
	var h := int(lay["h"])
	# --- shape: uniform rows, size band by kind, materially bigger than the old 17x13 ---
	assert_eq(rows.size(), h, "%s row count" % tag)
	for r in rows:
		assert_eq(str(r).length(), w, "%s uniform width" % tag)
	var town: bool = p["kind"] == "town"
	var lo: Vector2i = DmbSettlementLayout.MIN_TOWN if town else DmbSettlementLayout.MIN_STEADING
	var hi: Vector2i = DmbSettlementLayout.MAX_TOWN if town else DmbSettlementLayout.MAX_STEADING
	assert_true(w >= lo.x and w <= hi.x and h >= lo.y and h <= hi.y, "%s %s size %dx%d within band %s..%s" % [tag, p["kind"], w, h, str(lo), str(hi)])
	assert_true(w * h >= 2 * DmbSettlementLayout.WILD_W * DmbSettlementLayout.WILD_H, "%s is at least twice the old node footprint" % tag)
	# --- spawn: John stands on open ground, not inside anything, and can reach every entity ---
	var ps: Array = a["player_start"]
	assert_true(_walkable(rows, ps[0], ps[1]), "%s spawn %s on walkable ground" % [tag, str(ps)])
	var reach := _flood(rows, Vector2i(ps[0], ps[1]), a["entities"])
	var by_id := {}
	for e in a["entities"]:
		by_id[str(e["id"])] = e
		var pos := Vector2i(int(e["pos"][0]), int(e["pos"][1]))
		assert_true(pos.x >= 0 and pos.x < w and pos.y >= 0 and pos.y < h, "%s entity %s inside map" % [tag, e["id"]])
		var adjacent_reachable := false
		for dq in [Vector2i(0, 1), Vector2i(0, -1), Vector2i(1, 0), Vector2i(-1, 0)]:
			if reach.has(pos + dq):
				adjacent_reachable = true
		assert_true(adjacent_reachable or reach.has(pos), "%s entity %s (%s) reachable from spawn" % [tag, e["id"], e["kind"]])
	var ids := by_id.keys()
	assert_eq(ids.size(), a["entities"].size(), "%s entity ids unique" % tag)
	# --- profile correspondence ---
	var buildings := {}
	var workers := 0
	var quest_npcs := 0
	var houses := 0
	var exits := 0
	var creatures := 0
	for e in a["entities"]:
		if e.has("building"):
			buildings[str(e["building"])] = int(buildings.get(str(e["building"]), 0)) + 1
		if e.has("worker"):
			workers += 1
			assert_true(by_id.has(str(e["id"])), "worker id")
			var wp: Array = e["workplace"]
			assert_true(absi(int(wp[0]) - int(e["pos"][0])) + absi(int(wp[1]) - int(e["pos"][1])) <= 2, "%s worker %s stands by its workplace" % [tag, e["id"]])
		if e.has("quest_id"):
			quest_npcs += 1
			assert_eq(str(e["quest_id"]), str(DmbQuests.build(sim, nid)["id"]), "%s quest NPC belongs to the node's quest" % tag)
		if str(e["kind"]) == "door" and str(e["id"]).contains("_house"):
			houses += 1
		if str(e["kind"]) == "exit":
			exits += 1
			var to := str(e["to_area"])
			assert_true(to == "jane_placeholder" or sim.board.node_neighbors(nid).has(DmbNodeProjection.node_of(to)), "%s exit leads to a neighbour" % tag)
		if str(e["kind"]) == "creature":
			creatures += 1
	var expected_exits: int = sim.board.node_neighbors(nid).size() + (1 if nid == sim.player_home_node() else 0)
	assert_eq(exits, expected_exits, "%s one exit per neighbour" % tag)
	# Two adjacent hexes of one terrain share a building type: compare totals.
	var expected_prod := {}
	var prod_buildings := 0
	for pr in p["production"]:
		expected_prod[str(pr["building"])] = int(expected_prod.get(str(pr["building"]), 0)) + int(pr["n"])
		prod_buildings += int(pr["n"])
	for bid in expected_prod:
		assert_eq(int(buildings.get(bid, 0)), int(expected_prod[bid]), "%s %d x %s projected" % [tag, int(expected_prod[bid]), bid])
	for bid in p["processing"]:
		assert_eq(int(buildings.get(str(bid), 0)), 1, "%s works %s projected" % [tag, bid])
	for bid in p["civic"]:
		assert_eq(int(buildings.get(str(bid), 0)), 1, "%s civic %s projected" % [tag, bid])
	assert_eq(houses, int(p["housing"]), "%s housing %d projected as house doors" % [tag, int(p["housing"])])
	assert_eq(workers, prod_buildings, "%s one worker per production building" % tag)
	assert_true(quest_npcs >= 2, "%s quest cast present" % tag)
	var infected := 0
	for hid in sim.board.nodes[nid]["hexes"]:
		if int(sim.board.hexes[hid]["demons"]) > 0:
			infected += 1
	assert_eq(creatures, infected, "%s one creature per infected hex" % tag)
	# Terrain dressing reflects the adjacent hexes: forest sectors have trees,
	# fields have fences, hills/mountains rock.
	var flat := "\n".join(PackedStringArray(rows))
	var terr: Dictionary = p["terrains"]
	if terr.has("fields"):
		assert_true(flat.count("f") >= 6, "%s fields draw fenced strips" % tag)
	if terr.has("forest"):
		assert_true(_interior_count(rows, "T") >= 4, "%s forest draws interior trees" % tag)
	if terr.has("hills") or terr.has("mountains"):
		assert_true(flat.count("r") >= 2, "%s hills/mountains draw rocks" % tag)
	if int(p["infection"]) >= 2:
		assert_true(flat.count("a") + flat.count("t") >= 3, "%s infection scorches the ground" % tag)
	# Town: walled, gated; steading: unwalled.
	if town:
		var wall_min: int = w - 8 - (DmbSettlementLayout.HOME_RECT.size.x if nid == sim.player_home_node() else 0)
		assert_true(str(rows[1]).count("#") >= wall_min, "%s town has a north wall" % tag)
		assert_true(buildings.has("gate_tower") and buildings.has("hall") and buildings.has("market"), "%s town has gate, hall and market" % tag)
	else:
		assert_true(not str(rows[1]).contains("#"), "%s steading is unwalled" % tag)
		assert_true(not buildings.has("hall"), "%s steading has no hall" % tag)
	# --- determinism: same seed/turns/node → byte-identical area; snapshot round trip too ---
	if canonical:
		var again := _world(seed, turns)
		assert_eq(str(DmbNodeProjection.area_for(again, nid)), str(a), "%s reproduces byte-identically from seed" % tag)
		var restored := DmbWorldSim.from_dict(sim.to_dict())
		assert_eq(str(DmbNodeProjection.area_for(restored, nid)), str(a), "%s survives snapshot round trip" % tag)
		assert_eq(str(DmbNodeProjection.area_for(sim, nid, {"puzzles": {}})), str(a), "%s adv_state without puzzles does not change the map" % tag)
	return a


## Force the same node into both states and compare: the town must be
## materially larger and richer than the steading it grew from.
func _check_steading_vs_town() -> void:
	var sim := _world(5, TURNS)
	var nid := 22
	sim.catan.settlements[nid]["city"] = false
	var s := DmbNodeProjection.area_for(sim, nid)
	sim.catan.settlements[nid]["city"] = true
	var t := DmbNodeProjection.area_for(sim, nid)
	sim.catan.settlements[nid]["city"] = false
	var sa: int = int(s["layout"]["w"]) * int(s["layout"]["h"])
	var ta: int = int(t["layout"]["w"]) * int(t["layout"]["h"])
	assert_true(ta >= int(sa * 1.5), "town map area %d is at least 1.5x the steading %d" % [ta, sa])
	assert_true(t["entities"].size() >= s["entities"].size() + 8, "town has materially more entities (%d vs %d)" % [t["entities"].size(), s["entities"].size()])
	assert_eq(str(s["profile"]["kind"]), "steading", "before: steading")
	assert_eq(str(t["profile"]["kind"]), "town", "after: town")
	assert_true(int(t["profile"]["housing"]) > int(s["profile"]["housing"]), "town houses more")
	assert_true(str(t["rows"][1]).contains("#") and not str(s["rows"][1]).contains("#"), "only the town is walled")


## Different settlements of one world do not share a layout, and the same
## profile in different worlds is still placed differently (seeded jitter).
func _check_distinct_layouts() -> void:
	var sim := _world(5, TURNS)
	var seen := {}
	var ids: Array = sim.catan.settlements.keys()
	ids.sort()
	for nid in ids:
		var a := DmbNodeProjection.area_for(sim, int(nid))
		var body := "\n".join(PackedStringArray(a["rows"]))
		assert_true(not seen.has(body), "node %d layout is not a copy of another settlement's" % int(nid))
		seen[body] = int(nid)
	# Building positions differ between two steadings of the same size class.
	var a1 := DmbNodeProjection.area_for(sim, int(ids[0]))
	var a2 := DmbNodeProjection.area_for(sim, int(ids[1]))
	assert_true(str(_positions(a1, "well")) != str(_positions(a2, "well")) or str(_positions(a1, "shrine")) != str(_positions(a2, "shrine")), "civic buildings are not pinned to fixed slots")


## Built core versus outer work, and a clear road from each exit to the plaza.
func _check_core_and_roads() -> void:
	var sim := _world(5, TURNS)
	for nid in [22, 8]:
		var a := DmbNodeProjection.area_for(sim, nid)
		var lay: Dictionary = a["layout"]
		var core: Array = lay["core"]
		var outer: Array = lay["outer"]
		assert_eq(core.size(), 4, "core rect identified")
		assert_eq(outer.size(), 4, "outer work rect identified")
		assert_true(int(core[2]) * int(core[3]) < int(outer[2]) * int(outer[3]), "outer landscape is larger than the built core")
		var houses := 0
		var houses_in := 0
		var houses_edge := 0
		var prod := 0
		var prod_out := 0
		var w := int(lay["w"])
		var h := int(lay["h"])
		for e in a["entities"]:
			var px := int(e["pos"][0])
			var py := int(e["pos"][1])
			if str(e.get("building", "")) == "house":
				houses += 1
				if _in_rect(px, py, core, 2):
					houses_in += 1
				if px <= 3 or py <= 3 or px >= w - 4 or py >= h - 4:
					houses_edge += 1
			elif str(e["id"]).contains("_prod"):
				prod += 1
				if _in_rect(px, py, outer, 0) and not _in_rect(px, py, core, 0):
					prod_out += 1
		assert_true(houses >= 2, "houses present")
		assert_true(houses_in * 2 >= houses, "most houses sit in the built core (%d/%d)" % [houses_in, houses])
		assert_true(houses_edge * 4 < houses, "houses are not scattered to the map edge (%d/%d)" % [houses_edge, houses])
		assert_true(prod >= 1 and prod_out * 2 >= prod, "most production sits in the outer work area (%d/%d)" % [prod_out, prod])
		var rows: Array = a["rows"]
		var cx := w / 2
		var cy := h / 2
		assert_true(str(rows[cy])[cx] == ":", "plaza centre is a road")
		var exits := 0
		for e in a["entities"]:
			if str(e["kind"]) != "exit" or str(e["id"]).ends_with("_door"):
				continue
			exits += 1
			var ex := int(e["pos"][0])
			var ey := int(e["pos"][1])
			var inward := Vector2i(ex, ey + (1 if ey == 0 else -1))
			assert_true(str(rows[inward.y])[inward.x] == ":", "exit %s opens onto a road" % e["id"])
			var reach := DmbSettlementLayout.reachable(rows, Vector2i(cx, cy), {})
			assert_true(reach.has("%d,%d" % [inward.x, inward.y]), "exit road reaches the centre")
		assert_true(exits >= 1, "settlement has a main exit")


func _check_production_dressing() -> void:
	var weak_wood := _feature_count("forest", 1, "trees")
	var strong_wood := _feature_count("forest", 3, "trees")
	assert_true(strong_wood > weak_wood, "more wood production draws more trees (%d > %d)" % [strong_wood, weak_wood])
	var weak_grain := _feature_count("fields", 1, "fields")
	var strong_grain := _feature_count("fields", 3, "fields")
	assert_true(strong_grain > weak_grain, "more grain production draws more field (%d > %d)" % [strong_grain, weak_grain])
	var weak_pasture := _feature_count("pasture", 1, "pasture")
	var strong_pasture := _feature_count("pasture", 3, "pasture")
	assert_true(strong_pasture > weak_pasture, "more pasture production draws more fencing (%d > %d)" % [strong_pasture, weak_pasture])
	var weak_ore := _feature_count("mountains", 1, "mines")
	var strong_ore := _feature_count("mountains", 3, "mines")
	assert_true(strong_ore > weak_ore, "stronger mining draws more mine mouths (%d > %d)" % [strong_ore, weak_ore])
	var weak_clay := _feature_count("hills", 1, "clay")
	var strong_clay := _feature_count("hills", 3, "clay")
	assert_true(strong_clay > weak_clay, "stronger clay production draws more pit (%d > %d)" % [strong_clay, weak_clay])
	var camp_weak := _camp_count(1)
	var camp_strong := _camp_count(3)
	assert_true(camp_strong >= 1 and camp_strong >= camp_weak, "strong production gets a worker camp (%d)" % camp_strong)
	assert_eq(_house_count(1), _house_count(3), "camps do not change canonical housing")


func _check_crossings() -> void:
	var terrains := ["forest", "fields", "pasture", "mountains", "hills"]
	var marks := {}
	for t in terrains:
		var lay := _wild_layout(t)
		assert_eq(int(lay["w"]), DmbSettlementLayout.WILD_W, "%s crossing keeps its width" % t)
		assert_eq(int(lay["h"]), DmbSettlementLayout.WILD_H, "%s crossing keeps its height" % t)
		var feat: Dictionary = lay["features"]
		var mark := 0
		match t:
			"forest":
				mark = int(feat["trees"])
			"fields":
				mark = int(feat["fields"])
			"pasture":
				mark = int(feat["pasture"])
			"mountains":
				mark = int(feat["mines"])
			"hills":
				mark = int(feat["clay"])
		assert_true(mark > 0, "%s crossing has its own dressing (%d)" % [t, mark])
		marks[t] = mark
		var rows: Array = lay["rows"]
		var cx := int(lay["w"]) / 2
		var cy := int(lay["h"]) / 2
		assert_true(str(rows[cy])[cx] in [":", ",", "."], "%s crossing plaza stays open" % t)
	assert_true(marks.size() == 5, "five crossing flavours")


func _feature_count(terrain: String, n: int, key: String) -> int:
	var lay := _built_layout(terrain, n, 2)
	return int(lay["features"][key])


func _camp_count(n: int) -> int:
	return int(_built_layout("forest", n, 2)["features"]["camps"])


func _house_count(n: int) -> int:
	var houses := 0
	for b in _built_layout("forest", n, 4)["buildings"]:
		if str(b["kind"]) == "house":
			houses += 1
	return houses


func _built_layout(terrain: String, n: int, housing: int) -> Dictionary:
	var p := {
		"kind": "steading", "family": terrain, "development": 1,
		"production": [{"terrain": terrain, "building": "hut", "worker": "worker", "n": n, "hex": 1}],
		"processing": [], "housing": housing, "civic": ["shrine"], "roads": [],
	}
	return DmbSettlementLayout.build(5, 1, p, 2, false, [1, 2, 3], {1: terrain, 2: "desert", 3: "desert"}, {1: 0, 2: 0, 3: 0})


func _wild_layout(terrain: String) -> Dictionary:
	var p := {
		"kind": "wild", "family": terrain, "development": 0,
		"production": [], "processing": [], "housing": 0, "civic": [], "roads": [],
	}
	return DmbSettlementLayout.build(9, 4, p, 2, false, [1, 2, 3], {1: terrain, 2: "desert", 3: "desert"}, {1: 0, 2: 0, 3: 0})


func _in_rect(x: int, y: int, rect: Array, pad: int) -> bool:
	if rect.size() != 4:
		return false
	return x >= int(rect[0]) - pad and y >= int(rect[1]) - pad and x < int(rect[0]) + int(rect[2]) + pad and y < int(rect[1]) + int(rect[3]) + pad


func _positions(a: Dictionary, building: String) -> Array:
	var out: Array = []
	for e in a["entities"]:
		if str(e.get("building", "")) == building:
			out.append(e["pos"])
	return out


func _walkable(rows: Array, x: int, y: int) -> bool:
	if y < 0 or y >= rows.size() or x < 0 or x >= str(rows[0]).length():
		return false
	return str(rows[y])[x] in [".", ",", ":", "a", "="]


func _interior_count(rows: Array, ch: String) -> int:
	var n := 0
	for y in range(2, rows.size() - 2):
		var r := str(rows[y])
		for x in range(2, r.length() - 2):
			if r[x] == ch:
				n += 1
	return n


## Tiles reachable from `from` over walkable ground; entities block like Overworld.
func _flood(rows: Array, from: Vector2i, entities: Array) -> Dictionary:
	var blocked := {}
	for e in entities:
		blocked[Vector2i(int(e["pos"][0]), int(e["pos"][1]))] = true
	var seen := {from: true}
	var q: Array = [from]
	while not q.is_empty():
		var c: Vector2i = q.pop_front()
		for dq in [Vector2i(0, 1), Vector2i(0, -1), Vector2i(1, 0), Vector2i(-1, 0)]:
			var n: Vector2i = c + dq
			if seen.has(n) or blocked.has(n) or not _walkable(rows, n.x, n.y):
				continue
			seen[n] = true
			q.append(n)
	return seen
