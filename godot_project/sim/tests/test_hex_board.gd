extends DmbTestCase
## Standard 19-hex Catan board: topology (54 nodes / 72 edges), terrain and
## token distribution, determinism and serialisation.


func run() -> void:
	_test_counts()
	_test_terrain_and_tokens()
	_test_topology()
	_test_determinism()
	_test_round_trip()


func _test_counts() -> void:
	var b := DmbHexBoard.standard(7)
	assert_eq(b.hexes.size(), 19, "19 hexes")
	assert_eq(b.nodes.size(), 54, "54 nodes")
	assert_eq(b.edges.size(), 72, "72 edges")


func _test_terrain_and_tokens() -> void:
	var b := DmbHexBoard.standard(7)
	var counts := {}
	var tokens := []
	for h in b.hexes:
		counts[h["terrain"]] = counts.get(h["terrain"], 0) + 1
		if h["terrain"] == "desert":
			assert_eq(h["token"], 0, "desert has no token")
		else:
			tokens.append(h["token"])
		assert_eq(h["demons"], 0, "board starts clean")
	assert_eq(counts.get("forest", 0), 4, "4 forest")
	assert_eq(counts.get("pasture", 0), 4, "4 pasture")
	assert_eq(counts.get("fields", 0), 4, "4 fields")
	assert_eq(counts.get("hills", 0), 3, "3 hills")
	assert_eq(counts.get("mountains", 0), 3, "3 mountains")
	assert_eq(counts.get("desert", 0), 1, "1 desert")
	tokens.sort()
	assert_eq(tokens, DmbHexBoard.TOKEN_POOL, "standard number tokens")
	assert_eq(DmbHexBoard.resource_for("forest"), "wood", "forest → wood")
	assert_eq(DmbHexBoard.resource_for("desert"), "", "desert → nothing")


func _test_topology() -> void:
	var b := DmbHexBoard.standard(7)
	var by_hex_count := {1: 0, 2: 0, 3: 0}
	for n in b.nodes:
		var hc: int = n["hexes"].size()
		assert_true(hc >= 1 and hc <= 3, "node touches 1..3 hexes")
		by_hex_count[hc] += 1
		var ec: int = n["edges"].size()
		assert_true(ec >= 2 and ec <= 3, "node has 2..3 edges")
		assert_eq(b.node_neighbors(n["id"]).size(), ec, "neighbours == edges")
	assert_eq(by_hex_count[3], 24, "24 inner nodes")
	assert_eq(by_hex_count[2], 12, "12 coast nodes shared by two hexes")
	assert_eq(by_hex_count[1], 18, "18 coast nodes on one hex")
	for h in b.hexes:
		assert_eq(h["nodes"].size(), 6, "hex has 6 corners")
		assert_eq(h["edges"].size(), 6, "hex has 6 sides")
		assert_true(b.hex_neighbors(h["id"]).size() <= 6, "≤ 6 neighbours")
	var centre := b.hex_at(0, 0)
	assert_eq(b.hex_neighbors(centre).size(), 6, "centre hex has 6 neighbours")
	for e in b.edges:
		assert_eq(e["nodes"].size(), 2, "edge joins 2 nodes")
		var a: int = e["nodes"][0]
		var c: int = e["nodes"][1]
		assert_eq(b.edge_between(a, c), e["id"], "edge_between finds the edge")
		assert_true(e["hexes"].size() >= 1 and e["hexes"].size() <= 2, "edge borders 1..2 hexes")
	assert_eq(b.edge_between(0, 0), -1, "no self edge")
	# Every node of a hex touches that hex.
	for h in b.hexes:
		for nid in h["nodes"]:
			assert_true(h["id"] in b.nodes[nid]["hexes"], "corner links back to hex")


func _test_determinism() -> void:
	var a := DmbHexBoard.standard(11)
	var b := DmbHexBoard.standard(11)
	var c := DmbHexBoard.standard(12)
	var same := true
	var differs := false
	for i in range(19):
		if a.hexes[i]["terrain"] != b.hexes[i]["terrain"] or a.hexes[i]["token"] != b.hexes[i]["token"]:
			same = false
		if a.hexes[i]["terrain"] != c.hexes[i]["terrain"] or a.hexes[i]["token"] != c.hexes[i]["token"]:
			differs = true
	assert_true(same, "same seed → same board")
	assert_true(differs, "different seed → different board")


func _test_round_trip() -> void:
	var a := DmbHexBoard.standard(3)
	a.hexes[4]["demons"] = 2
	var b := DmbHexBoard.from_dict(a.to_dict())
	assert_eq(b.hexes.size(), 19, "round trip hexes")
	assert_eq(b.nodes.size(), 54, "round trip nodes")
	assert_eq(b.edges.size(), 72, "round trip edges")
	assert_eq(b.hexes[4]["demons"], 2, "demons survive round trip")
	assert_eq(b.hexes[4]["terrain"], a.hexes[4]["terrain"], "terrain survives round trip")
	assert_eq(b.node_neighbors(10), a.node_neighbors(10), "adjacency survives round trip")
