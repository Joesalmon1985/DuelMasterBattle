class_name DmbWorldSim
extends RefCounted
## The shared Catan + Pandemic world. One advance_turn() per node walk.
##
## Turn order:
##   1. Dice → production (hexes with 2+ demons yield nothing).
##   2. Each faction takes its AI turn (build / trade / muster / treat).
##   3. Carts move one edge.
##   4. Infection step (may epidemic / outbreak; outbreaks destroy carts).
##   5. Units recover.
## Every turn returns a list of events {type, text, ...} for prose and tests.

## Infection draws happen once every INFECTION_EVERY world turns (a world turn is
## one node-to-node walk, far faster than a Pandemic round).
const INFECTION_EVERY := 3

var seed: int = 0
var rng := RandomNumberGenerator.new()
var board: DmbHexBoard
var catan: DmbCatanState
var carts: DmbCarts
var infection: DmbInfection
var units: DmbUnits
var factions: Array = []
var weights: Dictionary = {}		# fid -> weight dict
var stats: Dictionary = {}			# fid -> counters
var turn: int = 0
var last_events: Array = []
var _player_home: int = -1


func _init(p_seed: int = 0) -> void:
	seed = p_seed
	rng.seed = p_seed


# --- setup ------------------------------------------------------------------

func setup() -> void:
	factions = DmbFactions.ids()
	board = DmbHexBoard.standard(seed)
	catan = DmbCatanState.new(board, factions, seed + 1)
	carts = DmbCarts.new(board, catan)
	infection = DmbInfection.new(board, seed + 2)
	units = DmbUnits.new(board, catan, infection, seed + 3)
	for f in factions:
		weights[f] = DmbFactionAI.preset(DmbFactions.stance_of(f))
		stats[f] = {"roads": 0, "settlements": 0, "cities": 0, "dev": 0, "trades": 0, "treats": 0, "fights": 0}
	# Catan snake setup: forward then reverse; second placement pays out.
	var order := factions.duplicate()
	order.append_array(factions.duplicate())
	order.reverse()
	var pass_no := 0
	for i in range(order.size()):
		var f: String = order[i]
		var second := i >= factions.size()
		var nodes := catan.legal_settlement_nodes(f, true)
		var nid := _best_setup_node(nodes)
		var eid: int = board.nodes[nid]["edges"][rng.randi_range(0, board.nodes[nid]["edges"].size() - 1)]
		while catan.roads.has(eid):
			eid = board.nodes[nid]["edges"][rng.randi_range(0, board.nodes[nid]["edges"].size() - 1)]
		catan.place_setup(f, nid, eid, second)
	_player_home = catan.nodes_of("wardens")[0]
	infection.initial_infection()
	for f in factions:
		var data := DmbFactions.get_data(f)
		units.spawn_champion(f, data["champion"], data["champion_form"])
	turn = 0


func _best_setup_node(nodes: Array) -> int:
	var best: int = nodes[0]
	var best_score := -1
	for nid in nodes:
		var score := 0
		var seen := {}
		for hid in board.nodes[nid]["hexes"]:
			score += DmbHexBoard.token_pips(board.hexes[hid]["token"])
			seen[DmbHexBoard.resource_for(board.hexes[hid]["terrain"])] = true
		score += seen.size()
		if score > best_score:
			best_score = score
			best = nid
	return best


func player_home_node() -> int:
	return _player_home


func ai_weights(fid: String) -> Dictionary:
	return weights[fid]


func ruler_adjust(fid: String, key: String, delta: float) -> bool:
	if not weights.has(fid):
		return false
	return DmbFactionAI.adjust(weights[fid], key, delta)


# --- turn -------------------------------------------------------------------

func advance_turn() -> Array:
	turn += 1
	var events := []
	# 1. Production.
	var roll := catan.roll_dice()
	var prod := catan.produce(roll)
	events.append({"type": "roll", "roll": roll, "produced": prod.size()})
	# 2. Factions.
	var start := turn % factions.size()
	for i in range(factions.size()):
		var f: String = factions[(start + i) % factions.size()]
		DmbFactionAI.take_turn(f, weights[f], self, events)
	# 3. Carts.
	var before_log := carts.log.size()
	carts.advance()
	for i in range(before_log, carts.log.size()):
		var e: Dictionary = carts.log[i].duplicate()
		events.append(e)
	# 4. Infection (paced).
	var inf_log: Array = infection.infect_step() if turn % INFECTION_EVERY == 0 else []
	for entry in inf_log:
		events.append(entry)
		for hid in entry["outbroke"]:
			var destroyed := carts.on_outbreak(hid)
			events.append({"type": "outbreak", "hex": hid, "carts_destroyed": destroyed})
	carts.prune()
	# 5. Units.
	units.tick()
	for e in events:
		if not e.has("text"):
			e["text"] = describe(e)
	last_events = events
	return events


# --- prose ------------------------------------------------------------------

func hex_name(hid: int) -> String:
	var h: Dictionary = board.hexes[hid]
	var names := {"forest": "the woods", "hills": "the brick hills", "pasture": "the sheepwalks",
		"fields": "the wheat", "mountains": "the ore seams", "desert": "the dead ground"}
	return "%s (%d)" % [names.get(h["terrain"], h["terrain"]), h["token"]] if h["token"] > 0 else names.get(h["terrain"], h["terrain"])


func describe(e: Dictionary) -> String:
	var f := DmbFactions.name_of(e.get("faction", ""))
	match e["type"]:
		"roll":
			return "The dice come up %d." % e["roll"] if e["produced"] > 0 else "The dice come up %d. Nothing moves." % e["roll"]
		"road":
			return "%s lay a road." % f
		"settlement":
			return "%s raise a new settlement." % f
		"city":
			return "%s wall a settlement into a town." % f
		"trade":
			return "%s send carts to %s." % [f, DmbFactions.name_of(e["partner"])]
		"hero":
			return "%s muster a hero." % f
		"treat":
			return "%s drive demons out of %s." % [f, hex_name(e["hex"])]
		"fight":
			var d: String = str(DmbBestiary.get_data(e["demon_id"]).get("display_name", "a demon")) if e.get("demon_id", "") != "" else "a demon"
			return "%s's champion %s against %s in %s." % [f, "prevails" if e["outcome"] == "win" else "is beaten", d, hex_name(e["hex"])]
		"cart_spawned":
			return "A cart leaves for %s." % DmbFactions.name_of(e["to"])
		"cart_delivered":
			return "A cart reaches %s." % DmbFactions.name_of(e["to"])
		"cart_destroyed":
			return "A cart is lost to the outbreak in %s." % hex_name(e["hex"])
		"infect":
			return "Something stirs in %s." % hex_name(e["hex"])
		"epidemic":
			return "Epidemic. %s is overrun." % hex_name(e["hex"])
		"outbreak":
			return "Outbreak in %s. It spreads." % hex_name(e["hex"])
	return str(e["type"])


# --- serialisation ----------------------------------------------------------

## Compact fingerprint for determinism tests.
func snapshot() -> String:
	var parts := [str(turn), str(infection.total_demons()), str(infection.outbreaks), str(carts.active().size()), str(units.alive().size())]
	for f in factions:
		parts.append("%s:%d/%d/%d/%d" % [f, catan.victory_points(f), catan.road_count(f), catan.hand_total(f), units.champion_of(f)["node"]])
	for h in board.hexes:
		parts.append(str(h["demons"]))
	return ",".join(parts)


func to_dict() -> Dictionary:
	return {
		"seed": seed, "turn": turn, "rng": rng.state, "player_home": _player_home,
		"board": board.to_dict(), "catan": catan.to_dict(), "carts": carts.to_dict(),
		"infection": infection.to_dict(), "units": units.to_dict(),
		"weights": weights.duplicate(true), "stats": stats.duplicate(true),
	}


static func from_dict(d: Dictionary) -> DmbWorldSim:
	var w := DmbWorldSim.new(int(d.get("seed", 0)))
	w.turn = int(d.get("turn", 0))
	w.rng.state = int(d.get("rng", 0))
	w._player_home = int(d.get("player_home", -1))
	w.factions = DmbFactions.ids()
	w.board = DmbHexBoard.from_dict(d.get("board", {}))
	w.catan = DmbCatanState.from_dict(d.get("catan", {}), w.board)
	w.carts = DmbCarts.from_dict(d.get("carts", {}), w.board, w.catan)
	w.infection = DmbInfection.from_dict(d.get("infection", {}), w.board)
	w.units = DmbUnits.from_dict(d.get("units", {}), w.board, w.catan, w.infection)
	for f in w.factions:
		w.weights[f] = DmbFactionAI.preset(DmbFactions.stance_of(f))
		for k in d.get("weights", {}).get(f, {}):
			w.weights[f][k] = float(d["weights"][f][k])
		w.stats[f] = {"roads": 0, "settlements": 0, "cities": 0, "dev": 0, "trades": 0, "treats": 0, "fights": 0}
		for k in d.get("stats", {}).get(f, {}):
			w.stats[f][k] = int(d["stats"][f][k])
	return w
