extends RefCounted
class_name DmbDungeonWorldFixture
## Full-board spatial fixture: real DmbWorldSim board + exaggerated dungeon
## candidates + placement metrics. Does not mutate production dungeon behaviour.

const Spec = preload("res://sim/world/wizard_dungeon_spec.gd")
const Emb = preload("res://sim/world/embedded_dungeon.gd")

var seed: int = 507
var sim: DmbWorldSim
var candidates: Array = []          # candidate dicts
var by_node: Dictionary = {}        # nid -> candidate
var settlements: Array = []         # [{faction, node, hexes, neighbours}]
var specimen_node: int = -1
var bg_test_node: int = -1
var report: Dictionary = {}


func setup(p_seed: int = 507) -> void:
	seed = p_seed
	sim = DmbWorldSim.new(seed)
	sim.setup()
	_collect_settlements()
	_build_candidates()
	_pick_specimen_and_bg()
	report = {"seed": seed, "hexes": sim.board.hexes.size(), "nodes": sim.board.nodes.size(),
		"edges": sim.board.edges.size(), "settlements": settlements.size(), "candidates": candidates.size()}


func _collect_settlements() -> void:
	settlements.clear()
	for fid in DmbFactions.ids():
		var nodes: Array = sim.catan.nodes_of(fid)
		assert(not nodes.is_empty())
		var nid: int = int(nodes[0])
		var hexes: Array = sim.board.nodes[nid]["hexes"].duplicate()
		hexes.sort()
		settlements.append({
			"faction": fid,
			"faction_name": DmbFactions.name_of(fid),
			"node": nid,
			"hexes": hexes,
			"neighbours": sim.board.node_neighbors(nid),
		})


## Coastal = topology perimeter (touches fewer than 3 land hexes).
static func is_coastal(board: DmbHexBoard, nid: int) -> bool:
	return board.nodes[nid]["hexes"].size() < 3


static func terrains_at(board: DmbHexBoard, nid: int) -> Array:
	var out: Array = []
	var seen := {}
	for hid in board.nodes[nid]["hexes"]:
		var t := str(board.hexes[hid]["terrain"])
		if not seen.has(t):
			seen[t] = true
			out.append(t)
	return out


static func types_for_node(board: DmbHexBoard, nid: int) -> Array:
	var types: Array = []
	var seen := {}
	for t in terrains_at(board, nid):
		for code in Spec.TERRAIN_TO_TYPES.get(t, []):
			if not seen.has(code):
				seen[code] = true
				types.append(code)
	if is_coastal(board, nid) and not seen.has("UB"):
		types.append("UB")
	return types


func _build_candidates() -> void:
	candidates.clear()
	by_node.clear()
	for s in settlements:
		var snid: int = int(s["node"])
		var touch_hexes: Array = s["hexes"].duplicate()
		# All nodes belonging to hexes that touch the settlement node.
		var related := {}
		for hid in touch_hexes:
			for nid in sim.board.hexes[hid]["nodes"]:
				related[int(nid)] = true
		# Also include production dungeon reservation near this settlement if any.
		for d in sim.dungeons.dungeons:
			if int(d["settlement"]) == snid:
				related[int(d["node"])] = true
		var nids: Array = related.keys()
		nids.sort()
		for nid in nids:
			if int(nid) == snid:
				continue  # settlement centre itself is not a dungeon site in production sense;
				# still allow if it has qualifying terrain for spatial comparison? Spec wants
				# candidates near settlements — include settlement node only if multi-type demo.
			var types := types_for_node(sim.board, int(nid))
			if types.is_empty():
				continue
			var terrains := terrains_at(sim.board, int(nid))
			var reasons: Array = []
			for code in types:
				match code:
					"GW":
						reasons.append("touches forest hex")
					"BR":
						reasons.append("touches hills/brick hex")
					"WB":
						reasons.append("touches mountains/ore hex")
					"UB":
						reasons.append("coastal node (hexes=%d < 3)" % sim.board.nodes[nid]["hexes"].size())
			var cand := {
				"node": int(nid),
				"settlement": snid,
				"faction": str(s["faction"]),
				"faction_name": str(s["faction_name"]),
				"touching_hexes": touch_hexes.duplicate(),
				"node_hexes": sim.board.nodes[nid]["hexes"].duplicate(),
				"terrains": terrains,
				"types": types,
				"reasons": reasons,
				"coastal": is_coastal(sim.board, int(nid)),
				"production_dungeon": sim.dungeons.at_node(int(nid)),
			}
			# Merge if same node already listed from another settlement view.
			if by_node.has(int(nid)):
				var prev: Dictionary = by_node[int(nid)]
				for code in types:
					if not prev["types"].has(code):
						prev["types"].append(code)
				for r in reasons:
					if not prev["reasons"].has(r):
						prev["reasons"].append(r)
				continue
			candidates.append(cand)
			by_node[int(nid)] = cand
	# Prefer multi-type nodes visible; ensure at least one multi-type if topology allows.
	candidates.sort_custom(func(a, b): return int(a["node"]) < int(b["node"]))


func _pick_specimen_and_bg() -> void:
	specimen_node = -1
	bg_test_node = -1
	# Prefer a wild (non-settlement) GW candidate near wardens home.
	var home := sim.player_home_node()
	var best := -1
	var best_d := 99
	for c in candidates:
		if not c["types"].has("GW"):
			continue
		var nid: int = int(c["node"])
		if sim.catan.settlements.has(nid):
			continue
		var path: Array = sim.board.shortest_path(home, nid)
		var d: int = path.size() if not path.is_empty() else 99
		if d < best_d:
			best_d = d
			best = nid
	if best < 0:
		for c in candidates:
			if c["types"].has("GW"):
				best = int(c["node"])
				break
	if best < 0 and not candidates.is_empty():
		best = int(candidates[0]["node"])
	specimen_node = best
	# BG test node: wild node that is not the specimen.
	for c in candidates:
		var nid: int = int(c["node"])
		if nid == specimen_node:
			continue
		if not sim.catan.settlements.has(nid):
			bg_test_node = nid
			break
	if bg_test_node < 0:
		for n in sim.board.nodes:
			var nid: int = int(n["id"])
			if nid != specimen_node and not sim.catan.settlements.has(nid):
				bg_test_node = nid
				break


func candidate_nodes() -> Array:
	var out: Array = []
	for c in candidates:
		out.append(int(c["node"]))
	return out


func primary_type_for(nid: int) -> String:
	if nid == bg_test_node:
		return "BG"
	var c: Dictionary = by_node.get(nid, {})
	if c.is_empty():
		return ""
	var types: Array = c["types"]
	if types.is_empty():
		return ""
	return str(types[0])


func types_for(nid: int) -> Array:
	if nid == bg_test_node:
		return ["BG"]
	return by_node.get(nid, {}).get("types", [])


## Build a normal node area at an optional forced size, then stamp embedded dungeon.
func project_node(nid: int, size: Vector2i = Vector2i.ZERO, type_code: String = "", interactive: bool = false) -> Dictionary:
	var prev: Vector2i = DmbSettlementLayout.FORCE_DIMS
	if size != Vector2i.ZERO:
		DmbSettlementLayout.FORCE_DIMS = size
	var area: Dictionary = DmbNodeProjection.area_for(sim, nid, {})
	DmbSettlementLayout.FORCE_DIMS = prev
	if size != Vector2i.ZERO:
		# Temporary profile override must not leak into later projections.
		DmbSettlementLayout.FORCE_DIMS = Vector2i.ZERO
	var code: String = type_code
	if code == "":
		code = primary_type_for(nid)
		if code == "" and nid == bg_test_node:
			code = "BG"
	if code == "":
		area["embedded_dungeon"] = {"fit": "NO_DUNGEON_TYPE"}
		return area
	var emb: Dictionary = Emb.stamp(area, code, interactive and nid == specimen_node)
	area["embedded_dungeon"] = emb
	area["dungeon_world_test"] = true
	area["fixture_node"] = nid
	area["fixture_types"] = types_for(nid)
	return area


func metrics_for(area: Dictionary) -> Dictionary:
	var rows: Array = area.get("rows", [])
	var w: int = 0 if rows.is_empty() else str(rows[0]).length()
	var h: int = rows.size()
	var emb: Dictionary = area.get("embedded_dungeon", {})
	var dw: int = Spec.RESERVATION_W
	var dh: int = Spec.RESERVATION_H
	var total := w * h
	var dungeon_tiles := dw * dh
	var fit := str(emb.get("fit", "UNKNOWN"))
	var free := maxi(0, total - dungeon_tiles)
	var pct := 0.0 if total == 0 else 100.0 * float(dungeon_tiles) / float(total)
	var exits := 0
	for e in area.get("entities", []):
		if str(e.get("kind", "")) == "exit":
			exits += 1
	return {
		"w": w, "h": h, "dungeon_w": dw, "dungeon_h": dh,
		"total_tiles": total, "dungeon_tiles": dungeon_tiles, "free_tiles": free,
		"dungeon_pct": pct, "exits": exits, "fit": fit,
		"origin": emb.get("origin", []),
		"approach": emb.get("approach", []),
		"exits_clear": bool(emb.get("exits_clear", false)),
		"rooms_reachable": bool(emb.get("rooms_reachable", false)),
		"path_in": emb.get("path_in_len", -1),
		"path_out": emb.get("path_out_len", -1),
		"settlement_reachable": bool(emb.get("settlement_reachable", true)),
	}


func compare_sizes(nid: int, type_code: String = "") -> Array:
	var out: Array = []
	for sz in Spec.SIZE_PROFILES:
		var area := project_node(nid, sz, type_code, nid == specimen_node)
		out.append({"size": [sz.x, sz.y], "metrics": metrics_for(area)})
	return out


func production_bg_unassigned() -> bool:
	if not Spec.bg_unassigned_in_production():
		return false
	for v in Spec.TERRAIN_TO_TYPES.values():
		if v.has("BG"):
			return false
	return true
