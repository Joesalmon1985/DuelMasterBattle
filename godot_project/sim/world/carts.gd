class_name DmbCarts
extends RefCounted
## Physical trade shipments. A trade between two factions removes the goods at
## commit and spawns one cart per direction. Carts move one edge per world
## turn along the shortest safe route to the receiving faction's nearest
## settlement, and deliver on arrival. Routes bordering a hex with
## BLOCK_DEMONS+ demons are unsafe: carts wait. An outbreak on a hex destroys
## any cart on an edge bordering it.
##
## Cart: {id, from, to, goods, node, edge, dest, waiting, alive}

const BLOCK_DEMONS := 2

var board: DmbHexBoard
var catan: DmbCatanState
var carts: Array = []
var log: Array = []
var _next_id: int = 1


func _init(p_board: DmbHexBoard = null, p_catan: DmbCatanState = null) -> void:
	board = p_board
	catan = p_catan


func active() -> Array:
	var out := []
	for c in carts:
		if c["alive"]:
			out.append(c)
	return out


func active_ids() -> Array:
	var out := []
	for c in active():
		out.append(c["id"])
	return out


func carts_at_node(nid: int) -> Array:
	var out := []
	for c in active():
		if c["edge"] == -1 and c["node"] == nid:
			out.append(c)
	return out


func carts_on_edge(eid: int) -> Array:
	var out := []
	for c in active():
		if c["edge"] == eid:
			out.append(c)
	return out


## Commit a trade through the Catan layer and spawn carts. Returns the carts.
func trade(from: String, to: String, give: Dictionary, receive: Dictionary) -> Array:
	var shipments := catan.commit_trade(from, to, give, receive)
	var out := []
	for sh in shipments:
		var origin := _nearest_node(sh["from"], -1)
		var dest := _nearest_node(sh["to"], origin)
		if origin < 0 or dest < 0:
			# No physical presence: deliver instantly rather than lose goods.
			catan.deliver(sh)
			continue
		var cart := {
			"id": _next_id, "from": sh["from"], "to": sh["to"], "goods": sh["goods"],
			"node": origin, "edge": -1, "dest": dest, "waiting": 0, "alive": true,
		}
		_next_id += 1
		carts.append(cart)
		out.append(cart)
		log.append({"type": "cart_spawned", "cart": cart["id"], "from": from, "to": to, "goods": sh["goods"]})
	return out


func _nearest_node(fid: String, from_node: int) -> int:
	var owned := catan.nodes_of(fid)
	if owned.is_empty():
		return -1
	if from_node < 0:
		return owned[0]
	var best: int = owned[0]
	var best_len := 1 << 30
	for nid in owned:
		var p := board.shortest_path(from_node, nid)
		if not p.is_empty() and p.size() < best_len:
			best_len = p.size()
			best = nid
	return best


func _blocked_edges() -> Dictionary:
	var blocked := {}
	for e in board.edges:
		if board.edge_infection(e["id"]) >= BLOCK_DEMONS:
			blocked[e["id"]] = true
	return blocked


## Advance every cart one edge. Carts that were on an edge arrive at its far
## node first, then (if at destination) deliver.
func advance() -> void:
	var blocked := _blocked_edges()
	for c in carts:
		if not c["alive"]:
			continue
		if c["node"] == c["dest"]:
			_deliver(c)
			continue
		var path := board.shortest_path(c["node"], c["dest"], blocked)
		if path.size() < 2:
			c["waiting"] += 1
			c["edge"] = -1
			continue
		var nxt: int = path[1]
		c["edge"] = board.edge_between(c["node"], nxt)
		c["node"] = nxt
		if c["node"] == c["dest"]:
			_deliver(c)


func _deliver(c: Dictionary) -> void:
	catan.deliver({"from": c["from"], "to": c["to"], "goods": c["goods"]})
	c["alive"] = false
	c["edge"] = -1
	log.append({"type": "cart_delivered", "cart": c["id"], "to": c["to"], "node": c["dest"], "goods": c["goods"]})


## An outbreak on hex `hid` destroys carts on any edge bordering it. Returns ids.
func on_outbreak(hid: int) -> Array:
	var destroyed := []
	for c in carts:
		if not c["alive"] or c["edge"] < 0:
			continue
		if hid in board.edges[c["edge"]]["hexes"]:
			c["alive"] = false
			destroyed.append(c["id"])
			log.append({"type": "cart_destroyed", "cart": c["id"], "hex": hid, "goods": c["goods"]})
	return destroyed


func prune() -> void:
	carts = active()


func to_dict() -> Dictionary:
	return {"carts": active().duplicate(true), "next_id": _next_id}


static func from_dict(d: Dictionary, p_board: DmbHexBoard, p_catan: DmbCatanState) -> DmbCarts:
	var c := DmbCarts.new(p_board, p_catan)
	for raw in d.get("carts", []):
		var cart := {}
		for k in raw:
			cart[k] = raw[k]
		for k in ["id", "node", "edge", "dest", "waiting"]:
			cart[k] = int(cart.get(k, 0))
		cart["alive"] = true
		c.carts.append(cart)
	c._next_id = int(d.get("next_id", 1))
	return c
