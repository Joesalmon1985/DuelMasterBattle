class_name DmbFactionAI
extends RefCounted
## Weighted-heuristic decision making for one faction per world turn.
## Weights are a plain Dictionary so rulers (and tests) can nudge them.
## Each turn a faction gets ACTIONS_PER_TURN picks; every candidate action is
## scored weight × situational multiplier and the best is taken.

const KEYS := ["roads", "settlements", "cities", "dev", "longest_road", "trade", "treat", "fight"]
const MIN_WEIGHT := 0.0
const MAX_WEIGHT := 5.0
const ACTIONS_PER_TURN := 2

const PRESETS := {
	"guardian": {"roads": 0.8, "settlements": 1.0, "cities": 0.8, "dev": 0.6, "longest_road": 0.3, "trade": 0.8, "treat": 2.5, "fight": 1.5},
	"corrupting": {"roads": 1.6, "settlements": 1.6, "cities": 1.2, "dev": 1.0, "longest_road": 1.0, "trade": 1.0, "treat": 0.2, "fight": 0.3},
}


static func preset(stance: String) -> Dictionary:
	return PRESETS.get(stance, PRESETS["guardian"]).duplicate()


static func adjust(weights: Dictionary, key: String, delta: float) -> bool:
	if not (key in KEYS):
		return false
	weights[key] = clampf(float(weights.get(key, 1.0)) + delta, MIN_WEIGHT, MAX_WEIGHT)
	return true


## Take one faction's turn. Mutates the world through its subsystems and
## appends {type, faction, ...} entries to `events`. Returns action names taken.
static func take_turn(fid: String, weights: Dictionary, w: DmbWorldSim, events: Array) -> Array:
	var taken := []
	for i in range(ACTIONS_PER_TURN):
		var choice := _best_action(fid, weights, w)
		if choice.is_empty():
			break
		_execute(fid, choice, w, events)
		taken.append(choice["action"])
	# Units act every turn regardless (they're on the board anyway).
	_move_units(fid, weights, w, events)
	return taken


static func _best_action(fid: String, weights: Dictionary, w: DmbWorldSim) -> Dictionary:
	var catan := w.catan
	var best := {}
	var best_score := 0.0
	var rng := w.rng
	# Build options.
	if catan.can_afford(fid, "city") and not catan.legal_city_nodes(fid).is_empty():
		var s: float = weights["cities"] * 1.2
		if s > best_score:
			best_score = s
			best = {"action": "city", "node": catan.legal_city_nodes(fid)[0]}
	if catan.can_afford(fid, "settlement") and not catan.legal_settlement_nodes(fid, false).is_empty():
		var nodes := catan.legal_settlement_nodes(fid, false)
		var s: float = weights["settlements"] * 1.1
		if s > best_score:
			best_score = s
			best = {"action": "settlement", "node": _pick_best_node(nodes, w)}
	if (catan.can_afford(fid, "road") or catan.free_roads(fid) > 0) and not catan.legal_road_edges(fid).is_empty():
		var edges := catan.legal_road_edges(fid)
		var s: float = weights["roads"] + weights["longest_road"] * 0.5
		if catan.legal_settlement_nodes(fid, false).is_empty():
			s *= 1.3	# roads unlock settlement spots
		if s > best_score:
			best_score = s
			best = {"action": "road", "edge": edges[rng.randi_range(0, edges.size() - 1)]}
	if catan.can_afford(fid, "dev") and not catan.dev_deck.is_empty():
		var s: float = weights["dev"] * 0.9
		if s > best_score:
			best_score = s
			best = {"action": "dev"}
	# Play a held knight → hero.
	if "knight" in catan.dev_hand(fid):
		var s: float = weights["fight"] + weights["treat"] * 0.5
		if s > best_score:
			best_score = s
			best = {"action": "knight"}
	# Trade: give our most plentiful resource for the one we lack most.
	var t := _trade_offer(fid, w)
	if not t.is_empty():
		var s: float = weights["trade"] * 0.9
		if s > best_score:
			best_score = s
			best = t
	return best


static func _pick_best_node(nodes: Array, w: DmbWorldSim) -> int:
	var best: int = nodes[0]
	var best_pips := -1
	for nid in nodes:
		var pips := 0
		for hid in w.board.nodes[nid]["hexes"]:
			pips += DmbHexBoard.token_pips(w.board.hexes[hid]["token"])
		pips -= 3 * w.board.node_infection(nid)
		if pips > best_pips:
			best_pips = pips
			best = nid
	return best


static func _trade_offer(fid: String, w: DmbWorldSim) -> Dictionary:
	var catan := w.catan
	var hand := catan.hand(fid)
	var most := ""
	var least := ""
	for r in DmbHexBoard.RESOURCES:
		if most == "" or hand[r] > hand[most]:
			most = r
		if least == "" or hand[r] < hand[least]:
			least = r
	if hand[most] < 3 or hand[least] > 0:
		return {}
	for other in w.factions:
		if other == fid or catan.hand(other)[least] < 1:
			continue
		if catan.hand(other)[most] > catan.hand(other)[least]:
			continue
		return {"action": "trade", "partner": other, "give": {most: 2}, "receive": {least: 1}}
	return {}


static func _execute(fid: String, choice: Dictionary, w: DmbWorldSim, events: Array) -> void:
	var catan := w.catan
	var st: Dictionary = w.stats[fid]
	match choice["action"]:
		"city":
			if catan.build_city(fid, choice["node"]):
				st["cities"] += 1
				events.append({"type": "city", "faction": fid, "node": choice["node"]})
		"settlement":
			if catan.build_settlement(fid, choice["node"]):
				st["settlements"] += 1
				events.append({"type": "settlement", "faction": fid, "node": choice["node"]})
		"road":
			if catan.build_road(fid, choice["edge"]):
				st["roads"] += 1
				events.append({"type": "road", "faction": fid, "edge": choice["edge"]})
		"dev":
			if catan.buy_dev_card(fid):
				st["dev"] += 1
		"knight":
			var r := catan.play_dev_card(fid, "knight")
			if not r.is_empty():
				var hero = w.units.spawn_hero(fid)
				if hero != null:
					events.append({"type": "hero", "faction": fid, "unit": hero["id"], "node": hero["node"]})
		"trade":
			var made := w.carts.trade(fid, choice["partner"], choice["give"], choice["receive"])
			if not made.is_empty():
				st["trades"] += 1
				events.append({"type": "trade", "faction": fid, "partner": choice["partner"], "carts": made.size()})


## Champion + heroes: treat if standing by demons, else fight if strong, else
## walk toward the nearest infected hex (guardian) or toward home (corrupter).
static func _move_units(fid: String, weights: Dictionary, w: DmbWorldSim, events: Array) -> void:
	var st: Dictionary = w.stats[fid]
	var care: float = weights["treat"] + weights["fight"]
	for u in w.units.units_of(fid):
		if u["recovering"] > 0:
			continue
		var adjacent := w.units.treatable_hexes(u["id"])
		if not adjacent.is_empty():
			# Roll against apathy: corrupters mostly ignore what's at their feet.
			if w.rng.randf() * DmbFactionAI.MAX_WEIGHT > care:
				continue
			var hid: int = adjacent[0]
			var demons: int = w.board.hexes[hid]["demons"]
			if weights["fight"] >= weights["treat"] and demons <= w.units.weave_size(u):
				var r := w.units.fight(u["id"], hid)
				st["fights"] += 1
				events.append({"type": "fight", "faction": fid, "unit": u["id"], "hex": hid, "outcome": r["outcome"], "demon_id": r.get("demon_id", "")})
			else:
				if w.units.treat(u["id"], hid):
					st["treats"] += 1
					events.append({"type": "treat", "faction": fid, "unit": u["id"], "hex": hid})
			continue
		# Move.
		var target := -1
		if w.rng.randf() * DmbFactionAI.MAX_WEIGHT <= care:
			target = _nearest_infected_node(u["node"], w)
		if target < 0:
			target = w.units.home_node(fid)
		if target >= 0 and target != u["node"]:
			w.units.step_toward(u["id"], target)


static func _nearest_infected_node(from: int, w: DmbWorldSim) -> int:
	var best := -1
	var best_len := 1 << 30
	for n in w.board.nodes:
		if w.board.node_infection(n["id"]) <= 0:
			continue
		var p := w.board.shortest_path(from, n["id"])
		if not p.is_empty() and p.size() < best_len:
			best_len = p.size()
			best = n["id"]
	return best
