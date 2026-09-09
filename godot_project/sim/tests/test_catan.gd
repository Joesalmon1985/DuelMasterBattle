extends DmbTestCase
## Catan layer: hands, legal placement, building costs, production (incl. the
## Pandemic bridge: 2+ demons stops production), dev cards, VP and trades.

const F := ["a", "b", "c", "d", "e", "f"]


func _fresh(seed: int = 5) -> DmbCatanState:
	var board := DmbHexBoard.standard(seed)
	return DmbCatanState.new(board, F, seed)


func _give(s: DmbCatanState, fid: String, res: Dictionary) -> void:
	for k in res:
		s.add_resource(fid, k, res[k])


func run() -> void:
	_test_setup_placement()
	_test_distance_rule_and_roads()
	_test_costs_and_building()
	_test_production_and_demon_block()
	_test_dev_cards()
	_test_victory_points_and_longest_road()
	_test_trade_commit()
	_test_round_trip()


func _test_setup_placement() -> void:
	var s := _fresh()
	assert_eq(s.legal_settlement_nodes("a", true).size(), 54, "all nodes open at setup")
	var n: int = s.legal_settlement_nodes("a", true)[0]
	assert_true(s.place_setup("a", n, s.board.nodes[n]["edges"][0]), "setup placement accepted")
	assert_eq(s.owner_at(n), "a", "node owned")
	assert_eq(s.settlement_count("a"), 1, "one settlement")
	assert_eq(s.road_count("a"), 1, "one road")
	assert_true(not s.place_setup("b", n, s.board.nodes[n]["edges"][1]), "occupied node rejected")
	for nb in s.board.node_neighbors(n):
		assert_true(not (nb in s.legal_settlement_nodes("b", true)), "distance rule at setup")
	assert_eq(s.hand_total("a"), 0, "no resources yet")
	# Second setup settlement grants its adjacent resources.
	var n2: int = s.legal_settlement_nodes("a", true)[5]
	s.place_setup("a", n2, s.board.nodes[n2]["edges"][0], true)
	var expected := 0
	for hid in s.board.nodes[n2]["hexes"]:
		if DmbHexBoard.resource_for(s.board.hexes[hid]["terrain"]) != "":
			expected += 1
	assert_eq(s.hand_total("a"), expected, "second setup settlement pays out")


func _test_distance_rule_and_roads() -> void:
	var s := _fresh()
	var n := 0
	var setup_edge: int = s.board.nodes[n]["edges"][0]
	s.place_setup("a", n, setup_edge)
	# Node 0 is an inner corner (3 edges); its road end also has 3 edges → 2 + 2 legal.
	assert_eq(s.legal_road_edges("a").size(), 4, "roads extend from both ends of the network")
	assert_eq(s.legal_road_edges("b").size(), 0, "no network → no legal roads")
	_give(s, "a", {"wood": 5, "brick": 5, "sheep": 5, "wheat": 5, "ore": 5})
	assert_eq(s.legal_settlement_nodes("a", false).size(), 0, "need a road end two steps out")
	# Build a road from n along a different edge than the setup road.
	var e: int = s.board.nodes[n]["edges"][1]
	assert_true(s.build_road("a", e), "build road")
	var far := s.board.other_end(e, n)
	assert_true(not (far in s.legal_settlement_nodes("a", false)), "adjacent node blocked by distance rule")
	var e2 := -1
	for cand in s.board.nodes[far]["edges"]:
		if cand != e and not (n in s.board.edges[cand]["nodes"]):
			e2 = cand
			break
	assert_true(e2 in s.legal_road_edges("a"), "edge beyond far end is legal")
	assert_true(s.build_road("a", e2), "second road")
	var target := s.board.other_end(e2, far)
	var legal := s.legal_settlement_nodes("a", false)
	assert_true(target in legal, "node two roads out is legal")
	for nid in legal:
		assert_true(s.board.shortest_path(n, nid).size() >= 3, "no legal node adjacent to the settlement")
	assert_true(s.build_settlement("a", target), "build settlement")
	assert_eq(s.hand("a")["wood"], 5 - 2 - 1, "paid wood for 2 roads + settlement")
	# Roads cannot pass through another faction's settlement.
	var s2 := _fresh()
	s2.place_setup("a", 0, s2.board.nodes[0]["edges"][0])
	var other := s2.board.other_end(s2.board.nodes[0]["edges"][0], 0)
	s2.settlements[other] = {"owner": "b", "city": false}
	for cand in s2.legal_road_edges("a"):
		assert_true(not (other in s2.board.edges[cand]["nodes"]) or 0 in s2.board.edges[cand]["nodes"], "cannot extend through enemy settlement")


func _test_costs_and_building() -> void:
	var s := _fresh()
	s.place_setup("a", 0, s.board.nodes[0]["edges"][0])
	assert_true(not s.can_afford("a", "city"), "cannot afford city with empty hand")
	_give(s, "a", {"wheat": 2, "ore": 3})
	assert_true(s.can_afford("a", "city"), "city = 2 wheat 3 ore")
	assert_eq(s.legal_city_nodes("a"), [0], "settlement can be upgraded")
	assert_true(s.build_city("a", 0), "upgrade to city")
	assert_true(s.is_city(0), "node is a city")
	assert_eq(s.hand_total("a"), 0, "city paid")
	assert_eq(s.legal_city_nodes("a").size(), 0, "no more upgrades")
	assert_true(not s.build_city("a", 0), "cannot upgrade a city")
	assert_eq(s.victory_points("a"), 2, "city worth 2")
	assert_eq(DmbCatanState.COST["settlement"], {"wood": 1, "brick": 1, "sheep": 1, "wheat": 1}, "settlement cost")
	assert_eq(DmbCatanState.COST["road"], {"wood": 1, "brick": 1}, "road cost")
	assert_eq(DmbCatanState.COST["dev"], {"sheep": 1, "wheat": 1, "ore": 1}, "dev cost")
	# Piece limits: 5 settlements, 4 cities, 15 roads.
	assert_eq(DmbCatanState.MAX_SETTLEMENTS, 5, "5 settlements")
	assert_eq(DmbCatanState.MAX_CITIES, 4, "4 cities")
	assert_eq(DmbCatanState.MAX_ROADS, 15, "15 roads")


func _test_production_and_demon_block() -> void:
	var s := _fresh()
	# Find a producing hex and put a settlement on one of its corners.
	var hid := -1
	for h in s.board.hexes:
		if h["terrain"] != "desert":
			hid = h["id"]
			break
	var h: Dictionary = s.board.hexes[hid]
	var corner: int = h["nodes"][0]
	s.place_setup("a", corner, s.board.nodes[corner]["edges"][0])
	var res: String = DmbHexBoard.resource_for(h["terrain"])
	var before: int = s.hand("a")[res]
	var log := s.produce(h["token"])
	assert_true(s.hand("a")[res] >= before + 1, "settlement produces 1 on its number")
	assert_true(log.size() >= 1, "production logged")
	# City doubles.
	_give(s, "a", {"wheat": 2, "ore": 3})
	s.build_city("a", corner)
	before = s.hand("a")[res]
	s.produce(h["token"])
	assert_true(s.hand("a")[res] >= before + 2, "city produces 2")
	# Demons block.
	s.board.hexes[hid]["demons"] = 2
	before = s.hand("a")[res]
	var log2 := s.produce(h["token"])
	var produced_here := false
	for entry in log2:
		if entry["hex"] == hid:
			produced_here = true
	assert_true(not produced_here, "2 demons stops production")
	s.board.hexes[hid]["demons"] = 1
	var log3 := s.produce(h["token"])
	produced_here = false
	for entry in log3:
		if entry["hex"] == hid:
			produced_here = true
	assert_true(produced_here, "1 demon still produces")
	# Seven produces nothing.
	assert_eq(s.produce(7).size(), 0, "seven produces nothing")
	# Dice are deterministic per seed.
	var r1 := _fresh(9)
	var r2 := _fresh(9)
	var seq1 := []
	var seq2 := []
	for i in range(10):
		seq1.append(r1.roll_dice())
		seq2.append(r2.roll_dice())
	assert_eq(seq1, seq2, "dice deterministic")
	for v in seq1:
		assert_true(v >= 2 and v <= 12, "2d6 range")


func _test_dev_cards() -> void:
	var s := _fresh()
	assert_eq(s.dev_deck.size(), 25, "25 dev cards")
	var counts := {}
	for c in s.dev_deck:
		counts[c] = counts.get(c, 0) + 1
	assert_eq(counts.get("knight", 0), 14, "14 knights")
	assert_eq(counts.get("victory_point", 0), 5, "5 VP cards")
	assert_eq(counts.get("road_building", 0), 2, "2 road building")
	assert_eq(counts.get("year_of_plenty", 0), 2, "2 year of plenty")
	assert_eq(counts.get("monopoly", 0), 2, "2 monopoly")
	s.place_setup("a", 0, s.board.nodes[0]["edges"][0])
	assert_true(not s.buy_dev_card("a"), "cannot buy with empty hand")
	_give(s, "a", {"sheep": 1, "wheat": 1, "ore": 1})
	assert_true(s.buy_dev_card("a"), "bought a card")
	assert_eq(s.dev_deck.size(), 24, "deck shrinks")
	assert_eq(s.dev_hand("a").size(), 1, "card in hand")
	# Force known cards to test effects.
	s.dev_hands["a"] = ["knight", "year_of_plenty", "monopoly", "road_building", "victory_point"]
	var r := s.play_dev_card("a", "knight")
	assert_eq(r["card"], "knight", "knight played")
	assert_eq(s.knights_played("a"), 1, "army grows")
	r = s.play_dev_card("a", "year_of_plenty", {"pick": ["ore", "ore"]})
	assert_eq(s.hand("a")["ore"], 2, "year of plenty grants two")
	_give(s, "b", {"wood": 3})
	_give(s, "c", {"wood": 2})
	r = s.play_dev_card("a", "monopoly", {"resource": "wood"})
	assert_eq(s.hand("a")["wood"], 5, "monopoly takes all wood")
	assert_eq(s.hand("b")["wood"], 0, "b lost wood")
	r = s.play_dev_card("a", "road_building")
	assert_eq(s.free_roads("a"), 2, "two free roads pending")
	var e: int = s.legal_road_edges("a")[0]
	assert_true(s.build_road("a", e), "free road built with no resources")
	assert_eq(s.free_roads("a"), 1, "one free road left")
	assert_eq(s.victory_points("a"), 2, "settlement + VP card")
	assert_eq(s.dev_hand("a").size(), 1, "played cards leave hand; VP card stays")


func _test_victory_points_and_longest_road() -> void:
	var s := _fresh()
	# Build a chain of 5 roads for "a" from node 0.
	s.place_setup("a", 0, s.board.nodes[0]["edges"][0])
	_give(s, "a", {"wood": 20, "brick": 20})
	var built := 1
	var frontier := 0
	var visited := {0: true}
	while built < 5:
		var progressed := false
		for e in s.legal_road_edges("a"):
			var ns: Array = s.board.edges[e]["nodes"]
			var nxt: int = ns[0] if ns[1] == frontier else ns[1]
			if frontier in ns and not visited.has(nxt):
				s.build_road("a", e)
				visited[nxt] = true
				frontier = nxt
				built += 1
				progressed = true
				break
		if not progressed:
			frontier = visited.keys()[visited.size() - 1]
			break
	assert_true(s.longest_road_length("a") >= 4, "longest road follows the chain")
	if s.longest_road_length("a") >= 5:
		assert_eq(s.longest_road_holder(), "a", "5 roads takes longest road")
		assert_eq(s.victory_points("a"), 3, "settlement 1 + longest road 2")
	# Largest army at 3 knights.
	s.dev_hands["b"] = ["knight", "knight", "knight"]
	for i in range(3):
		s.play_dev_card("b", "knight")
	assert_eq(s.largest_army_holder(), "b", "3 knights takes largest army")
	assert_eq(s.victory_points("b"), 2, "largest army 2 VP")
	assert_true(not s.has_won("b"), "not yet 10")


func _test_trade_commit() -> void:
	var s := _fresh()
	_give(s, "a", {"wood": 2})
	_give(s, "b", {"ore": 1})
	assert_true(not s.can_trade("a", "b", {"wood": 3}, {"ore": 1}), "cannot give more than held")
	assert_true(s.can_trade("a", "b", {"wood": 2}, {"ore": 1}), "legal trade")
	var shipments := s.commit_trade("a", "b", {"wood": 2}, {"ore": 1})
	assert_eq(shipments.size(), 2, "two shipments (one each way)")
	assert_eq(s.hand("a")["wood"], 0, "outgoing removed at commit")
	assert_eq(s.hand("a")["ore"], 0, "incoming not yet delivered")
	assert_eq(s.hand("b")["ore"], 0, "b's outgoing removed")
	var to_b: Dictionary = shipments[0] if shipments[0]["to"] == "b" else shipments[1]
	assert_eq(to_b["from"], "a", "shipment from a")
	assert_eq(to_b["goods"], {"wood": 2}, "shipment carries the goods")
	s.deliver(to_b)
	assert_eq(s.hand("b")["wood"], 2, "delivered on arrival")


func _test_round_trip() -> void:
	var s := _fresh(21)
	s.place_setup("a", 0, s.board.nodes[0]["edges"][0])
	_give(s, "a", {"wood": 3})
	s.dev_hands["a"] = ["knight"]
	var d := s.to_dict()
	var s2 := DmbCatanState.from_dict(d, s.board)
	assert_eq(s2.hand("a")["wood"], 3, "hand survives")
	assert_eq(s2.owner_at(0), "a", "settlement survives")
	assert_eq(s2.road_count("a"), 1, "roads survive")
	assert_eq(s2.dev_hand("a"), ["knight"], "dev hand survives")
	assert_eq(s2.dev_deck.size(), s.dev_deck.size(), "deck survives")
	assert_eq(s2.roll_dice(), s.roll_dice(), "rng state survives")
