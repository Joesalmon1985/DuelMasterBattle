extends SceneTree
## Phase 1 developer diagnostic: prints the canonical settlement facts that the
## production path DmbWorldSim -> DmbSettlementProfile -> DmbNodeProjection
## derives for one node, or for every settlement, of a seeded world.
##
## Usage:
##   godot --headless --path godot_project --script res://sim/tools/settlement_report.gd [seed] [turns] [node|settlements|cities|all]
##   defaults: seed=5 turns=30 settlements
##
## Every report is reproducible from (seed, turns, node). Nothing here mutates
## the sim; it only reads the same dictionaries Overworld renders from.


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var seed := int(args[0]) if args.size() > 0 else 5
	var turns := int(args[1]) if args.size() > 1 else 30
	var which := str(args[2]) if args.size() > 2 else "settlements"
	var sim := DmbWorldSim.new(seed)
	sim.setup()
	for i in range(turns):
		sim.advance_turn()
	var nodes: Array = []
	if which == "all":
		nodes = range(sim.board.nodes.size())
	elif which == "settlements" or which == "cities":
		for k in sim.catan.settlements:
			if which == "settlements" or bool(sim.catan.settlements[k]["city"]):
				nodes.append(int(k))
		nodes.sort()
	else:
		nodes = [int(which)]
	print("seed=%d turns=%d home=%d settlements=%d cities=%d demons=%d" % [seed, turns, sim.player_home_node(), sim.catan.settlements.size(), _city_count(sim), sim.infection.total_demons()])
	for nid in nodes:
		print(report(sim, seed, int(nid)))
	quit()


static func _city_count(sim: DmbWorldSim) -> int:
	var n := 0
	for k in sim.catan.settlements:
		if bool(sim.catan.settlements[k]["city"]):
			n += 1
	return n


## Multi-line report for one node. Static so tests can call it directly.
static func report(sim: DmbWorldSim, seed: int, nid: int) -> String:
	var p := DmbSettlementProfile.describe(sim, nid)
	var a := DmbNodeProjection.area_for(sim, nid)
	var lines: PackedStringArray = []
	lines.append("=== seed %d turn %d node %d (%s) — %s ===" % [seed, sim.turn, nid, a["id"], a["name"]])
	lines.append("kind: %s   owner: %s%s   family: %s" % [p["kind"], p["owner"], (" (%s)" % DmbFactions.name_of(p["owner"])) if p["owner"] != "" else "", p["family"]])
	var terr: PackedStringArray = []
	for t in p["terrains"]:
		terr.append("%s x%d" % [t, int(p["terrains"][t])])
	lines.append("terrain: %s   products: %s" % [", ".join(terr), ", ".join(PackedStringArray(p["products"]))])
	var prod: PackedStringArray = []
	for pr in p["production"]:
		prod.append("%dx %s (%s, hex %d%s)" % [int(pr["n"]), pr["building"], pr["worker"], int(pr["hex"]), ", idle" if bool(pr.get("idle", false)) else ""])
	lines.append("production: %s" % (", ".join(prod) if not prod.is_empty() else "-"))
	lines.append("processing: %s" % (", ".join(PackedStringArray(p["processing"])) if not p["processing"].is_empty() else "-"))
	var roads: PackedStringArray = []
	for r in p["roads"]:
		roads.append("%d:%s" % [int(r["to"]), str(r["owner"]) if str(r["owner"]) != "" else "track"])
	lines.append("development: %d   housing: %d   civic: %s   roads: %s" % [int(p["development"]), int(p["housing"]), ", ".join(PackedStringArray(p["civic"])), ", ".join(roads)])
	lines.append("infection: %d   mood: %s   dungeon: %s" % [int(p["infection"]), p["mood"] if p["mood"] != "" else "-", str(p["dungeon"].get("id", "-")) if not p["dungeon"].is_empty() else "-"])
	if p["kind"] != "wild":
		lines.append("quest template: %s" % DmbQuests.pick_template(sim, nid))
	lines.append("summary: %s" % DmbSettlementProfile.summary(p))
	var counts := {}
	var important: PackedStringArray = []
	for e in a["entities"]:
		var kind := str(e["kind"])
		counts[kind] = int(counts.get(kind, 0)) + 1
		if e.has("building"):
			important.append("%s@%s" % [str(e["building"]), str(e["pos"])])
		elif e.has("worker"):
			important.append("worker:%s@%s" % [str(e["worker"]), str(e["pos"])])
		elif e.has("quest_id"):
			important.append("quest:%s/%s@%s" % [str(e["quest_id"]), str(e["quest_npc"]), str(e["pos"])])
		elif e.has("dungeon_id"):
			important.append("dungeon_door:%s@%s" % [str(e["dungeon_id"]), str(e["pos"])])
		elif kind == "creature":
			important.append("creature:%s@%s" % [str(e["enemy_id"]), str(e["pos"])])
		elif kind == "npc":
			important.append("npc:%s@%s" % [str(e["name"]), str(e["pos"])])
	var ck: PackedStringArray = []
	var keys := counts.keys()
	keys.sort()
	for k in keys:
		ck.append("%s=%d" % [k, int(counts[k])])
	lines.append("projected entities: %d (%s)" % [a["entities"].size(), ", ".join(ck)])
	lines.append("important: %s" % ", ".join(important))
	return "\n".join(lines)
