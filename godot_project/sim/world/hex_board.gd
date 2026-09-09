class_name DmbHexBoard
extends RefCounted
## Standard 19-hex Catan board used as the shared Catan/Pandemic world board.
##
## Hexes use axial coordinates (q, r) with radius 2. Nodes are hex corners,
## edges are hex sides. Every entity is a plain Dictionary so the whole board
## serialises with to_dict()/from_dict() and is safe to hand to the client.
##
## Hex:  {id, q, r, terrain, token, demons, nodes[6], edges[6]}
## Node: {id, hexes[1..3], edges[2..3]}
## Edge: {id, nodes[2], hexes[1..2]}

const TERRAIN_POOL := [
	"forest", "forest", "forest", "forest",
	"pasture", "pasture", "pasture", "pasture",
	"fields", "fields", "fields", "fields",
	"hills", "hills", "hills",
	"mountains", "mountains", "mountains",
	"desert",
]
const TOKEN_POOL := [2, 3, 3, 4, 4, 5, 5, 6, 6, 8, 8, 9, 9, 10, 10, 11, 11, 12]
const RESOURCE_FOR := {
	"forest": "wood", "hills": "brick", "pasture": "sheep",
	"fields": "wheat", "mountains": "ore", "desert": "",
}
const RESOURCES := ["wood", "brick", "sheep", "wheat", "ore"]

## Axial neighbour offsets for pointy-top hexes.
const AXIAL_DIRS := [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]]

var hexes: Array = []
var nodes: Array = []
var edges: Array = []
var _hex_index: Dictionary = {}		# "q,r" -> hex id
var _edge_index: Dictionary = {}	# "lo,hi" -> edge id


static func resource_for(terrain: String) -> String:
	return RESOURCE_FOR.get(terrain, "")


## Number of dice combinations that roll this token (probability weight 1..5).
static func token_pips(token: int) -> int:
	if token <= 1 or token >= 13 or token == 7:
		return 0
	return 6 - absi(7 - token)


static func standard(seed: int) -> DmbHexBoard:
	var b := DmbHexBoard.new()
	b._build_topology()
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	var terrains := TERRAIN_POOL.duplicate()
	var tokens := TOKEN_POOL.duplicate()
	_shuffle(terrains, rng)
	_shuffle(tokens, rng)
	var ti := 0
	for h in b.hexes:
		h["terrain"] = terrains[h["id"]]
		if h["terrain"] == "desert":
			h["token"] = 0
		else:
			h["token"] = tokens[ti]
			ti += 1
		h["demons"] = 0
	return b


static func _shuffle(arr: Array, rng: RandomNumberGenerator) -> void:
	for i in range(arr.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var t = arr[i]
		arr[i] = arr[j]
		arr[j] = t


# --- topology ---------------------------------------------------------------

func _build_topology() -> void:
	hexes.clear()
	nodes.clear()
	edges.clear()
	_hex_index.clear()
	_edge_index.clear()
	# Spiral order from centre, radius 2 → 19 hexes.
	var coords: Array = [[0, 0]]
	for ring in range(1, 3):
		# Walk the ring: 6 sides × ring steps.
		var cq := AXIAL_DIRS[4][0] * ring
		var cr := AXIAL_DIRS[4][1] * ring
		for side in range(6):
			for step in range(ring):
				coords.append([cq, cr])
				cq += AXIAL_DIRS[side][0]
				cr += AXIAL_DIRS[side][1]
	for c in coords:
		var h := {"id": hexes.size(), "q": c[0], "r": c[1], "terrain": "", "token": 0, "demons": 0, "nodes": [], "edges": []}
		_hex_index["%d,%d" % [c[0], c[1]]] = h["id"]
		hexes.append(h)
	# Corners: use doubled pixel-ish coords so shared corners collapse to one key.
	var corner_index := {}
	for h in hexes:
		var cx: int = 2 * h["q"] + h["r"]	# x * 2 / sqrt3 scaled
		var cy: int = 3 * h["r"]			# y * 2
		# Six corners for a pointy-top hex, (dx, dy) in the same scaled space.
		var corner_offsets := [[0, -2], [1, -1], [1, 1], [0, 2], [-1, 1], [-1, -1]]
		for co in corner_offsets:
			var key := "%d,%d" % [cx + co[0], cy + co[1]]
			if not corner_index.has(key):
				corner_index[key] = nodes.size()
				nodes.append({"id": nodes.size(), "hexes": [], "edges": []})
			var nid: int = corner_index[key]
			h["nodes"].append(nid)
			nodes[nid]["hexes"].append(h["id"])
	# Edges between consecutive corners.
	for h in hexes:
		for i in range(6):
			var a: int = h["nodes"][i]
			var c: int = h["nodes"][(i + 1) % 6]
			var eid := _edge_key_lookup(a, c)
			if eid < 0:
				eid = edges.size()
				edges.append({"id": eid, "nodes": [mini(a, c), maxi(a, c)], "hexes": []})
				_edge_index[_ekey(a, c)] = eid
				nodes[a]["edges"].append(eid)
				nodes[c]["edges"].append(eid)
			h["edges"].append(eid)
			edges[eid]["hexes"].append(h["id"])


func _ekey(a: int, b: int) -> String:
	return "%d,%d" % [mini(a, b), maxi(a, b)]


func _edge_key_lookup(a: int, b: int) -> int:
	return _edge_index.get(_ekey(a, b), -1)


# --- queries ----------------------------------------------------------------

func hex_at(q: int, r: int) -> int:
	return _hex_index.get("%d,%d" % [q, r], -1)


func hex_neighbors(hid: int) -> Array:
	var h: Dictionary = hexes[hid]
	var out := []
	for d in AXIAL_DIRS:
		var n := hex_at(h["q"] + d[0], h["r"] + d[1])
		if n >= 0:
			out.append(n)
	return out


func node_neighbors(nid: int) -> Array:
	var out := []
	for eid in nodes[nid]["edges"]:
		for other in edges[eid]["nodes"]:
			if other != nid:
				out.append(other)
	return out


func edge_between(a: int, b: int) -> int:
	if a == b:
		return -1
	return _edge_key_lookup(a, b)


func other_end(eid: int, nid: int) -> int:
	var ns: Array = edges[eid]["nodes"]
	return ns[1] if ns[0] == nid else ns[0]


## Maximum demon count on any hex bordering this edge.
func edge_infection(eid: int) -> int:
	var m := 0
	for hid in edges[eid]["hexes"]:
		m = maxi(m, hexes[hid]["demons"])
	return m


## Maximum demon count on any hex touching this node.
func node_infection(nid: int) -> int:
	var m := 0
	for hid in nodes[nid]["hexes"]:
		m = maxi(m, hexes[hid]["demons"])
	return m


## BFS shortest node path avoiding blocked edges. Returns [] if unreachable.
func shortest_path(from: int, to: int, blocked_edges: Dictionary = {}) -> Array:
	if from == to:
		return [from]
	var prev := {from: -1}
	var queue := [from]
	var qi := 0
	while qi < queue.size():
		var cur: int = queue[qi]
		qi += 1
		for eid in nodes[cur]["edges"]:
			if blocked_edges.has(eid):
				continue
			var nxt := other_end(eid, cur)
			if prev.has(nxt):
				continue
			prev[nxt] = cur
			if nxt == to:
				var path := [to]
				var p: int = cur
				while p != -1:
					path.push_front(p)
					p = prev[p]
				return path
			queue.append(nxt)
	return []


# --- serialisation ----------------------------------------------------------

func to_dict() -> Dictionary:
	var hs := []
	for h in hexes:
		hs.append({"terrain": h["terrain"], "token": h["token"], "demons": h["demons"]})
	return {"hexes": hs}


static func from_dict(d: Dictionary) -> DmbHexBoard:
	var b := DmbHexBoard.new()
	b._build_topology()
	var hs: Array = d.get("hexes", [])
	for i in range(mini(hs.size(), b.hexes.size())):
		b.hexes[i]["terrain"] = str(hs[i].get("terrain", ""))
		b.hexes[i]["token"] = int(hs[i].get("token", 0))
		b.hexes[i]["demons"] = int(hs[i].get("demons", 0))
	return b
