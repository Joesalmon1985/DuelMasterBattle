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
		var wall_min: int = w - 4 - (DmbSettlementLayout.HOME_RECT.size.x if nid == sim.player_home_node() else 0)
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
