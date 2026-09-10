extends RefCounted
class_name DmbSettlementProfile
## Pure description of what a settlement node *is*, derived from world state
## (brief §4; node-map design doc vocabulary). Nothing here renders: it turns
## sim facts into a small dictionary the projection lays out. Adding a new
## building or industry means adding a rule here, not a hand-built map.
##
## Output shape:
##   {"kind": "wild"|"steading"|"town", "owner": fid, "family": "forest"...,
##    "terrains": {terrain: n}, "production": [{"terrain", "building", "worker", "n"}],
##    "processing": [building ids], "housing": n, "civic": [building ids],
##    "roads": [{"to": nid, "owner": fid, "kind": "road"|"track"}],
##    "infection": 0..3 (worst adjacent hex), "mood": "", "dungeon": {} or nearby dungeon,
##    "development": 0..4}

const PRODUCTION := {
	"forest": {"building": "woodcutter_hut", "worker": "woodcutter", "product": "wood"},
	"hills": {"building": "clay_pit", "worker": "brickmaker", "product": "brick"},
	"pasture": {"building": "sheepfold", "worker": "shepherd", "product": "wool"},
	"fields": {"building": "grain_field", "worker": "reaper", "product": "grain"},
	"mountains": {"building": "mine_mouth", "worker": "miner", "product": "ore"},
}
## Processing buildings unlocked by pairs of produced resources (design doc §6).
const PROCESSING := [
	["sawmill", ["wood"], 1],
	["kiln", ["brick", "wood"], 1],
	["weaver", ["wool"], 1],
	["mill", ["grain"], 1],
	["smithy", ["ore", "wood"], 2],
	["charcoal_burner", ["wood"], 2],
	["brewhouse", ["grain", "wool"], 2],
]
const CIVIC_STEADING := ["well", "shrine"]
const CIVIC_TOWN := ["well", "shrine", "hall", "market", "gate_tower"]
const FAMILY_ORDER := ["forest", "hills", "mountains", "pasture", "fields", "desert"]


static func describe(sim: DmbWorldSim, nid: int) -> Dictionary:
	var board: DmbHexBoard = sim.board
	var node: Dictionary = board.nodes[nid]
	var s: Dictionary = sim.catan.settlements.get(nid, {})
	var out := {
		"node": nid, "kind": "wild", "owner": "", "terrains": {}, "production": [], "processing": [],
		"housing": 0, "civic": [], "roads": [], "infection": 0, "mood": "", "dungeon": {}, "development": 0,
		"family": "", "products": [],
	}
	if not s.is_empty():
		out["kind"] = "town" if bool(s.get("city", false)) else "steading"
		out["owner"] = str(s["owner"])
	var worst := 0
	var tokens_total := 0
	for hid in node["hexes"]:
		var h: Dictionary = board.hexes[hid]
		var t := str(h["terrain"])
		out["terrains"][t] = int(out["terrains"].get(t, 0)) + 1
		worst = maxi(worst, int(h["demons"]))
		tokens_total += int(h.get("token", 0))
	out["infection"] = worst
	out["family"] = _family(out["terrains"])
	# Roads to neighbours (design doc §3): kept in the sim; drawn, not walked.
	for other in board.node_neighbors(nid):
		var eid := board.edge_between(nid, other)
		var owner := sim.catan.road_owner(eid)
		out["roads"].append({"to": int(other), "owner": owner, "kind": "road" if owner != "" else "track"})
	if out["kind"] == "wild":
		out["dungeon"] = sim.dungeons.at_node(nid)
		return out
	# Production buildings: one per productive adjacent hex; count scales with
	# token value (production potential) and city status.
	var products := {}
	for hid in node["hexes"]:
		var h: Dictionary = board.hexes[hid]
		var t := str(h["terrain"])
		if not PRODUCTION.has(t):
			continue
		var rule: Dictionary = PRODUCTION[t]
		var n := 1
		if int(h.get("token", 0)) in [6, 8]:
			n = 2
		if out["kind"] == "town":
			n += 1
		if int(h["demons"]) >= 2:
			n = maxi(1, n - 1)   # nothing grows; the works stand half idle
		out["production"].append({"terrain": t, "building": str(rule["building"]), "worker": str(rule["worker"]), "n": n, "hex": int(hid), "idle": int(h["demons"]) >= 2})
		products[str(rule["product"])] = true
	out["products"] = products.keys()
	out["products"].sort()
	# Development level 0..4: settlement 1, city +1, roads owned +1 at ≥2, processing +1.
	var dev := 1
	if out["kind"] == "town":
		dev += 1
	var owned_roads := 0
	for r in out["roads"]:
		if str(r["owner"]) == out["owner"]:
			owned_roads += 1
	if owned_roads >= 2:
		dev += 1
	for rule in PROCESSING:
		var needs: Array = rule[1]
		var ok := true
		for p in needs:
			if not products.has(p):
				ok = false
		if ok and dev >= int(rule[2]):
			out["processing"].append(str(rule[0]))
	if not out["processing"].is_empty():
		dev += 1
	out["development"] = mini(dev, 4)
	# Housing: two per steading, plus one per production building, doubled in towns.
	var houses: int = 2 + out["production"].size()
	if out["kind"] == "town":
		houses *= 2
	out["housing"] = houses
	out["civic"] = (CIVIC_TOWN if out["kind"] == "town" else CIVIC_STEADING).duplicate()
	out["mood"] = str(sim.settlement_moods.get(nid, ""))
	out["dungeon"] = sim.dungeons.by_settlement(nid)
	return out


static func _family(terrains: Dictionary) -> String:
	var best := ""
	var best_n := -1
	for t in FAMILY_ORDER:
		var n := int(terrains.get(t, 0))
		if n > best_n:
			best_n = n
			best = t
	return best


## One-line summary for signposts and tests.
static func summary(p: Dictionary) -> String:
	if p["kind"] == "wild":
		return "Wild %s crossing." % p["family"]
	var bits: Array = []
	for pr in p["production"]:
		bits.append("%d %s" % [int(pr["n"]), str(pr["building"]).replace("_", " ")])
	var line := "%s of %s, level %d. %s." % [p["kind"].capitalize(), DmbFactions.name_of(p["owner"]), int(p["development"]), ", ".join(PackedStringArray(bits))]
	if not p["processing"].is_empty():
		line += " Works: %s." % ", ".join(PackedStringArray(p["processing"]))
	if int(p["infection"]) > 0:
		line += " " + ["", "Uneasy.", "Nothing grows.", "Overrun."][int(p["infection"])]
	if p["mood"] != "":
		line += " The people are %s." % p["mood"]
	return line
