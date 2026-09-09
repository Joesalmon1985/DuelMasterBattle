class_name DmbCatanState
extends RefCounted
## Minimal Settlers of Catan rules for six AI factions on a DmbHexBoard.
## Hands, roads, settlements, cities, development cards, victory points,
## legal placement, and trade commit/deliver (carts move the goods).
##
## Pandemic bridge: a hex with 2+ demons does not produce.

const COST := {
	"road": {"wood": 1, "brick": 1},
	"settlement": {"wood": 1, "brick": 1, "sheep": 1, "wheat": 1},
	"city": {"wheat": 2, "ore": 3},
	"dev": {"sheep": 1, "wheat": 1, "ore": 1},
}
const MAX_SETTLEMENTS := 5
const MAX_CITIES := 4
const MAX_ROADS := 15
const WIN_VP := 10
const DEMON_BLOCK := 2
const DEV_DECK := ["knight", "knight", "knight", "knight", "knight", "knight", "knight",
	"knight", "knight", "knight", "knight", "knight", "knight", "knight",
	"victory_point", "victory_point", "victory_point", "victory_point", "victory_point",
	"road_building", "road_building", "year_of_plenty", "year_of_plenty",
	"monopoly", "monopoly"]

var board: DmbHexBoard
var factions: Array = []
var hands: Dictionary = {}			# fid -> {res: n}
var dev_hands: Dictionary = {}		# fid -> [card]
var dev_deck: Array = []
var knights: Dictionary = {}		# fid -> played knights
var free_road_credit: Dictionary = {}
var roads: Dictionary = {}			# edge id -> fid
var settlements: Dictionary = {}	# node id -> {"owner", "city"}
var longest_road_owner: String = ""
var largest_army_owner: String = ""
var rng := RandomNumberGenerator.new()


func _init(p_board: DmbHexBoard = null, p_factions: Array = [], seed: int = 0) -> void:
	board = p_board
	factions = p_factions.duplicate()
	rng.seed = seed
	for f in factions:
		hands[f] = _empty_hand()
		dev_hands[f] = []
		knights[f] = 0
		free_road_credit[f] = 0
	dev_deck = DEV_DECK.duplicate()
	DmbHexBoard._shuffle(dev_deck, rng)


func _empty_hand() -> Dictionary:
	var h := {}
	for r in DmbHexBoard.RESOURCES:
		h[r] = 0
	return h


# --- hands ------------------------------------------------------------------

func hand(fid: String) -> Dictionary:
	return hands[fid]


func hand_total(fid: String) -> int:
	var t := 0
	for r in hands[fid]:
		t += hands[fid][r]
	return t


func add_resource(fid: String, res: String, n: int) -> void:
	if res == "" or not hands.has(fid):
		return
	hands[fid][res] = hands[fid].get(res, 0) + n


func has_resources(fid: String, need: Dictionary) -> bool:
	for r in need:
		if hands[fid].get(r, 0) < need[r]:
			return false
	return true


func can_afford(fid: String, thing: String) -> bool:
	return has_resources(fid, COST[thing])


func _pay(fid: String, need: Dictionary) -> void:
	for r in need:
		hands[fid][r] -= need[r]


# --- ownership --------------------------------------------------------------

func owner_at(nid: int) -> String:
	return settlements.get(nid, {}).get("owner", "")


func is_city(nid: int) -> bool:
	return settlements.get(nid, {}).get("city", false)


func road_owner(eid: int) -> String:
	return roads.get(eid, "")


func settlement_count(fid: String) -> int:
	var c := 0
	for nid in settlements:
		if settlements[nid]["owner"] == fid and not settlements[nid]["city"]:
			c += 1
	return c


func city_count(fid: String) -> int:
	var c := 0
	for nid in settlements:
		if settlements[nid]["owner"] == fid and settlements[nid]["city"]:
			c += 1
	return c


func road_count(fid: String) -> int:
	var c := 0
	for eid in roads:
		if roads[eid] == fid:
			c += 1
	return c


func nodes_of(fid: String) -> Array:
	var out := []
	for nid in settlements:
		if settlements[nid]["owner"] == fid:
			out.append(nid)
	out.sort()
	return out


# --- legality ---------------------------------------------------------------

func _distance_ok(nid: int) -> bool:
	if settlements.has(nid):
		return false
	for nb in board.node_neighbors(nid):
		if settlements.has(nb):
			return false
	return true


func legal_settlement_nodes(fid: String, setup: bool) -> Array:
	var out := []
	if not setup and settlement_count(fid) >= MAX_SETTLEMENTS:
		return out
	for n in board.nodes:
		var nid: int = n["id"]
		if not _distance_ok(nid):
			continue
		if setup:
			out.append(nid)
			continue
		for eid in n["edges"]:
			if roads.get(eid, "") == fid:
				out.append(nid)
				break
	return out


func legal_road_edges(fid: String) -> Array:
	var out := []
	if road_count(fid) >= MAX_ROADS:
		return out
	for e in board.edges:
		var eid: int = e["id"]
		if roads.has(eid):
			continue
		for nid in e["nodes"]:
			# Connect via own settlement at this end...
			if owner_at(nid) == fid:
				out.append(eid)
				break
			# ...or via own road at this end, provided no enemy settlement blocks it.
			if settlements.has(nid) and owner_at(nid) != fid:
				continue
			var linked := false
			for oe in board.nodes[nid]["edges"]:
				if oe != eid and roads.get(oe, "") == fid:
					linked = true
			if linked:
				out.append(eid)
				break
	return out


func legal_city_nodes(fid: String) -> Array:
	var out := []
	if city_count(fid) >= MAX_CITIES:
		return out
	for nid in settlements:
		if settlements[nid]["owner"] == fid and not settlements[nid]["city"]:
			out.append(nid)
	out.sort()
	return out


# --- building ---------------------------------------------------------------

func place_setup(fid: String, nid: int, eid: int, pay_out: bool = false) -> bool:
	if not _distance_ok(nid) or roads.has(eid) or not (nid in board.edges[eid]["nodes"]):
		return false
	settlements[nid] = {"owner": fid, "city": false}
	roads[eid] = fid
	if pay_out:
		for hid in board.nodes[nid]["hexes"]:
			add_resource(fid, DmbHexBoard.resource_for(board.hexes[hid]["terrain"]), 1)
	_update_longest_road()
	return true


func build_road(fid: String, eid: int) -> bool:
	if not (eid in legal_road_edges(fid)):
		return false
	if free_road_credit.get(fid, 0) > 0:
		free_road_credit[fid] -= 1
	elif can_afford(fid, "road"):
		_pay(fid, COST["road"])
	else:
		return false
	roads[eid] = fid
	_update_longest_road()
	return true


func build_settlement(fid: String, nid: int) -> bool:
	if not can_afford(fid, "settlement") or not (nid in legal_settlement_nodes(fid, false)):
		return false
	_pay(fid, COST["settlement"])
	settlements[nid] = {"owner": fid, "city": false}
	_update_longest_road()
	return true


func build_city(fid: String, nid: int) -> bool:
	if not can_afford(fid, "city") or not (nid in legal_city_nodes(fid)):
		return false
	_pay(fid, COST["city"])
	settlements[nid]["city"] = true
	return true


# --- production -------------------------------------------------------------

func roll_dice() -> int:
	return rng.randi_range(1, 6) + rng.randi_range(1, 6)


## Distribute resources for a rolled number. Returns a log of
## {faction, hex, resource, amount}. Hexes with DEMON_BLOCK+ demons yield nothing.
func produce(roll: int) -> Array:
	var log := []
	if roll == 7:
		return log
	for h in board.hexes:
		if h["token"] != roll or h["demons"] >= DEMON_BLOCK:
			continue
		var res: String = DmbHexBoard.resource_for(h["terrain"])
		if res == "":
			continue
		for nid in h["nodes"]:
			if not settlements.has(nid):
				continue
			var s: Dictionary = settlements[nid]
			var amount := 2 if s["city"] else 1
			add_resource(s["owner"], res, amount)
			log.append({"faction": s["owner"], "hex": h["id"], "resource": res, "amount": amount})
	return log


# --- development cards ------------------------------------------------------

func dev_hand(fid: String) -> Array:
	return dev_hands[fid]


func knights_played(fid: String) -> int:
	return knights.get(fid, 0)


func free_roads(fid: String) -> int:
	return free_road_credit.get(fid, 0)


func buy_dev_card(fid: String) -> bool:
	if dev_deck.is_empty() or not can_afford(fid, "dev"):
		return false
	_pay(fid, COST["dev"])
	dev_hands[fid].append(dev_deck.pop_back())
	return true


## Play a card. Returns {card, ...effect details} or {} if not held.
## Knights are "played" as army strength here; unit creation is handled by
## the world sim which listens for the returned card.
func play_dev_card(fid: String, card: String, args: Dictionary = {}) -> Dictionary:
	if card == "victory_point" or not (card in dev_hands[fid]):
		return {}
	dev_hands[fid].erase(card)
	var out := {"card": card, "faction": fid}
	match card:
		"knight":
			knights[fid] = knights.get(fid, 0) + 1
			_update_largest_army()
		"road_building":
			free_road_credit[fid] = free_road_credit.get(fid, 0) + 2
		"year_of_plenty":
			var picks: Array = args.get("pick", ["wood", "brick"])
			for r in picks:
				add_resource(fid, r, 1)
			out["pick"] = picks
		"monopoly":
			var res: String = args.get("resource", "wood")
			var taken := 0
			for other in factions:
				if other == fid:
					continue
				taken += hands[other][res]
				hands[other][res] = 0
			add_resource(fid, res, taken)
			out["resource"] = res
			out["taken"] = taken
	return out


# --- victory points ---------------------------------------------------------

func vp_cards(fid: String) -> int:
	return dev_hands[fid].count("victory_point")


func victory_points(fid: String) -> int:
	var vp := settlement_count(fid) + 2 * city_count(fid) + vp_cards(fid)
	if longest_road_owner == fid:
		vp += 2
	if largest_army_owner == fid:
		vp += 2
	return vp


func has_won(fid: String) -> bool:
	return victory_points(fid) >= WIN_VP


func longest_road_holder() -> String:
	return longest_road_owner


func largest_army_holder() -> String:
	return largest_army_owner


func _update_largest_army() -> void:
	var best: int = int(knights.get(largest_army_owner, 0)) if largest_army_owner != "" else 2
	for f in factions:
		if knights[f] > best and knights[f] >= 3:
			best = knights[f]
			largest_army_owner = f


func _update_longest_road() -> void:
	var best := longest_road_length(longest_road_owner) if longest_road_owner != "" else 4
	for f in factions:
		var l := longest_road_length(f)
		if l > best and l >= 5:
			best = l
			longest_road_owner = f


## Longest simple trail of this faction's roads (edges), broken by enemy settlements.
func longest_road_length(fid: String) -> int:
	if fid == "":
		return 0
	var own := []
	for eid in roads:
		if roads[eid] == fid:
			own.append(eid)
	var best := 0
	for eid in own:
		for start in board.edges[eid]["nodes"]:
			best = maxi(best, _dfs_trail(fid, start, {}))
	return best


func _dfs_trail(fid: String, nid: int, used: Dictionary) -> int:
	var best := 0
	for eid in board.nodes[nid]["edges"]:
		if used.has(eid) or roads.get(eid, "") != fid:
			continue
		var nxt := board.other_end(eid, nid)
		used[eid] = true
		var here := 1
		# Enemy settlement at the far end breaks the trail.
		if not settlements.has(nxt) or owner_at(nxt) == fid:
			here += _dfs_trail(fid, nxt, used)
		used.erase(eid)
		best = maxi(best, here)
	return best


# --- trade ------------------------------------------------------------------

func can_trade(from: String, to: String, give: Dictionary, receive: Dictionary) -> bool:
	if from == to or not hands.has(from) or not hands.has(to):
		return false
	if give.is_empty() or receive.is_empty():
		return false
	return has_resources(from, give) and has_resources(to, receive)


## Commit a trade: both sides' outgoing goods leave their hands now and come
## back as shipment dictionaries {from, to, goods}. Nothing is credited until
## deliver() is called (by the cart layer on arrival).
func commit_trade(from: String, to: String, give: Dictionary, receive: Dictionary) -> Array:
	if not can_trade(from, to, give, receive):
		return []
	_pay(from, give)
	_pay(to, receive)
	return [
		{"from": from, "to": to, "goods": give.duplicate()},
		{"from": to, "to": from, "goods": receive.duplicate()},
	]


func deliver(shipment: Dictionary) -> void:
	for r in shipment["goods"]:
		add_resource(shipment["to"], r, shipment["goods"][r])


# --- serialisation ----------------------------------------------------------

func to_dict() -> Dictionary:
	var rd := {}
	for eid in roads:
		rd[str(eid)] = roads[eid]
	var sd := {}
	for nid in settlements:
		sd[str(nid)] = settlements[nid].duplicate()
	return {
		"factions": factions.duplicate(),
		"hands": hands.duplicate(true),
		"dev_hands": dev_hands.duplicate(true),
		"dev_deck": dev_deck.duplicate(),
		"knights": knights.duplicate(),
		"free_roads": free_road_credit.duplicate(),
		"roads": rd,
		"settlements": sd,
		"longest_road": longest_road_owner,
		"largest_army": largest_army_owner,
		"rng": rng.state,
	}


static func from_dict(d: Dictionary, p_board: DmbHexBoard) -> DmbCatanState:
	var s := DmbCatanState.new(p_board, d.get("factions", []), 0)
	for f in s.factions:
		var h: Dictionary = d.get("hands", {}).get(f, {})
		for r in h:
			s.hands[f][r] = int(h[r])
		s.dev_hands[f] = Array(d.get("dev_hands", {}).get(f, []))
		s.knights[f] = int(d.get("knights", {}).get(f, 0))
		s.free_road_credit[f] = int(d.get("free_roads", {}).get(f, 0))
	s.dev_deck = Array(d.get("dev_deck", []))
	s.roads = {}
	for k in d.get("roads", {}):
		s.roads[int(k)] = d["roads"][k]
	s.settlements = {}
	for k in d.get("settlements", {}):
		var v: Dictionary = d["settlements"][k]
		s.settlements[int(k)] = {"owner": str(v["owner"]), "city": bool(v["city"])}
	s.longest_road_owner = str(d.get("longest_road", ""))
	s.largest_army_owner = str(d.get("largest_army", ""))
	s.rng.state = int(d.get("rng", 0))
	return s
