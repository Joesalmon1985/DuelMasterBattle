extends DmbTestCase
## Trade carts: created by a trade, move one edge per turn along roads/edges
## toward the destination, deliver on arrival, blocked by infected routes,
## destroyed by outbreaks on the edge they occupy.

const F := ["a", "b", "c", "d", "e", "f"]


func _world() -> Dictionary:
	var board := DmbHexBoard.standard(4)
	var catan := DmbCatanState.new(board, F, 4)
	var carts := DmbCarts.new(board, catan)
	return {"board": board, "catan": catan, "carts": carts}


## Pick two nodes a few edges apart and settle them for a / b.
func _settle_pair(w: Dictionary, dist: int) -> Array:
	var board: DmbHexBoard = w["board"]
	var start := 0
	var path := board.shortest_path(start, start)
	var target := -1
	for n in range(board.nodes.size()):
		var p := board.shortest_path(start, n)
		if p.size() - 1 == dist:
			target = n
			break
	w["catan"].place_setup("a", start, board.nodes[start]["edges"][0])
	w["catan"].place_setup("b", target, board.nodes[target]["edges"][0])
	return [start, target]


func run() -> void:
	_test_shortest_path()
	_test_cart_moves_and_delivers()
	_test_blocked_by_infection()
	_test_destroyed_by_outbreak()
	_test_round_trip()


func _test_shortest_path() -> void:
	var board := DmbHexBoard.standard(4)
	assert_eq(board.shortest_path(0, 0), [0], "trivial path")
	var nb: int = board.node_neighbors(0)[0]
	assert_eq(board.shortest_path(0, nb), [0, nb], "one hop")
	var far := board.shortest_path(0, 53)
	assert_true(far.size() >= 2, "path exists across board")
	for i in range(far.size() - 1):
		assert_true(board.edge_between(far[i], far[i + 1]) >= 0, "consecutive path nodes are joined")
	# Blocked edges route around or fail.
	var blocked := {}
	for e in board.nodes[0]["edges"]:
		blocked[e] = true
	assert_eq(board.shortest_path(0, 53, blocked), [], "fully blocked start → no path")


func _test_cart_moves_and_delivers() -> void:
	var w := _world()
	var ends := _settle_pair(w, 3)
	var catan: DmbCatanState = w["catan"]
	var carts: DmbCarts = w["carts"]
	catan.add_resource("a", "wood", 2)
	catan.add_resource("b", "ore", 1)
	var made := carts.trade("a", "b", {"wood": 2}, {"ore": 1})
	assert_eq(made.size(), 2, "trade spawns two carts")
	assert_eq(carts.active().size(), 2, "two carts in flight")
	var cart: Dictionary = made[0] if made[0]["to"] == "b" else made[1]
	assert_eq(cart["node"], ends[0], "cart starts at a's settlement")
	assert_eq(cart["dest"], ends[1], "cart bound for b's settlement")
	assert_eq(catan.hand("b")["wood"], 0, "nothing delivered yet")
	var turns := 0
	while carts.active().size() > 0 and turns < 10:
		carts.advance()
		turns += 1
	assert_eq(turns, 3, "3-edge route takes 3 turns")
	assert_eq(catan.hand("b")["wood"], 2, "wood delivered to b")
	assert_eq(catan.hand("a")["ore"], 1, "ore delivered to a")
	assert_true(carts.log.size() >= 2, "deliveries logged")


func _test_blocked_by_infection() -> void:
	var w := _world()
	var ends := _settle_pair(w, 3)
	var board: DmbHexBoard = w["board"]
	var catan: DmbCatanState = w["catan"]
	var carts: DmbCarts = w["carts"]
	catan.add_resource("a", "wood", 1)
	catan.add_resource("b", "ore", 1)
	var made := carts.trade("a", "b", {"wood": 1}, {"ore": 1})
	var cart: Dictionary = made[0] if made[0]["to"] == "b" else made[1]
	# Infect every hex around the destination heavily so no route is safe.
	for hid in board.nodes[ends[1]]["hexes"]:
		board.hexes[hid]["demons"] = 2
	for e in board.nodes[ends[1]]["edges"]:
		for hid in board.edges[e]["hexes"]:
			board.hexes[hid]["demons"] = 2
	for i in range(6):
		carts.advance()
	assert_true(cart["id"] in carts.active_ids(), "cart still waiting")
	assert_eq(catan.hand("b")["wood"], 0, "blocked cart does not deliver")
	assert_true(cart["waiting"] > 0, "cart records waiting turns")
	# Clear infection and it gets through.
	for h in board.hexes:
		h["demons"] = 0
	for i in range(6):
		carts.advance()
	assert_eq(catan.hand("b")["wood"], 1, "delivered once route clears")


func _test_destroyed_by_outbreak() -> void:
	var w := _world()
	var ends := _settle_pair(w, 3)
	var board: DmbHexBoard = w["board"]
	var catan: DmbCatanState = w["catan"]
	var carts: DmbCarts = w["carts"]
	catan.add_resource("a", "wood", 1)
	catan.add_resource("b", "ore", 1)
	var made := carts.trade("a", "b", {"wood": 1}, {"ore": 1})
	carts.advance()
	var cart: Dictionary = made[0] if made[0]["to"] == "b" else made[1]
	var edge: int = cart["edge"]
	assert_true(edge >= 0, "cart is on an edge after moving")
	var hex_on_route: int = board.edges[edge]["hexes"][0]
	var destroyed := carts.on_outbreak(hex_on_route)
	assert_true(cart["id"] in destroyed, "cart on outbreak route destroyed")
	assert_true(not (cart["id"] in carts.active_ids()), "destroyed cart removed")
	for i in range(6):
		carts.advance()
	assert_eq(catan.hand("b")["wood"], 0, "destroyed goods never arrive")


func _test_round_trip() -> void:
	var w := _world()
	_settle_pair(w, 3)
	var catan: DmbCatanState = w["catan"]
	var carts: DmbCarts = w["carts"]
	catan.add_resource("a", "wood", 1)
	catan.add_resource("b", "ore", 1)
	carts.trade("a", "b", {"wood": 1}, {"ore": 1})
	carts.advance()
	var d := carts.to_dict()
	var c2 := DmbCarts.from_dict(d, w["board"], catan)
	assert_eq(c2.active().size(), 2, "carts survive round trip")
	assert_eq(c2.active()[0]["node"], carts.active()[0]["node"], "position survives")
	for i in range(6):
		c2.advance()
	assert_eq(catan.hand("b")["wood"], 1, "restored carts deliver")
