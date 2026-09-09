extends DmbTestCase
## Pandemic infection core on the hex board: infection deck, 0–3 demons per
## hex, outbreaks with chain protection, escalating epidemic chance.


func _inf(seed: int = 3) -> Dictionary:
	var board := DmbHexBoard.standard(seed)
	var inf := DmbInfection.new(board, seed)
	return {"board": board, "inf": inf}


func run() -> void:
	_test_deck()
	_test_initial_infection()
	_test_infect_and_cap()
	_test_outbreak_spreads_and_protects()
	_test_epidemic_escalation()
	_test_treat()
	_test_round_trip()


func _test_deck() -> void:
	var w := _inf()
	var inf: DmbInfection = w["inf"]
	assert_eq(inf.deck.size() + inf.discard.size(), 19, "one card per hex")
	var sorted := inf.deck.duplicate()
	sorted.sort()
	assert_eq(sorted, range(19), "deck covers every hex once")
	var a: Array = _inf(8)["inf"].deck
	var b: Array = _inf(8)["inf"].deck
	assert_eq(a, b, "deck shuffle deterministic")


func _test_initial_infection() -> void:
	var w := _inf()
	var inf: DmbInfection = w["inf"]
	var board: DmbHexBoard = w["board"]
	var log := inf.initial_infection()
	var total := 0
	var counts := {1: 0, 2: 0, 3: 0}
	for h in board.hexes:
		total += h["demons"]
		if h["demons"] > 0:
			counts[h["demons"]] += 1
	assert_eq(counts[3], 3, "three hexes at 3 demons")
	assert_eq(counts[2], 3, "three hexes at 2 demons")
	assert_eq(counts[1], 3, "three hexes at 1 demon")
	assert_eq(total, 18, "18 demons placed")
	assert_eq(inf.discard.size(), 9, "9 cards in discard")
	assert_eq(log.size(), 9, "logged nine placements")
	assert_eq(inf.outbreaks, 0, "no outbreaks during setup")


func _test_infect_and_cap() -> void:
	var w := _inf()
	var inf: DmbInfection = w["inf"]
	var board: DmbHexBoard = w["board"]
	var hid := board.hex_at(0, 0)
	assert_eq(inf.infect(hid, 1), [], "1 demon, no outbreak")
	assert_eq(board.hexes[hid]["demons"], 1, "placed")
	inf.infect(hid, 2)
	assert_eq(board.hexes[hid]["demons"], 3, "capped at 3")
	assert_eq(inf.outbreaks, 0, "reaching 3 is not an outbreak")


func _test_outbreak_spreads_and_protects() -> void:
	var w := _inf()
	var inf: DmbInfection = w["inf"]
	var board: DmbHexBoard = w["board"]
	var centre := board.hex_at(0, 0)
	board.hexes[centre]["demons"] = 3
	var hit := inf.infect(centre, 1)
	assert_eq(inf.outbreaks, 1, "one outbreak")
	assert_eq(hit, [centre], "outbreak hex reported")
	assert_eq(board.hexes[centre]["demons"], 3, "outbreak hex stays at 3")
	for nb in board.hex_neighbors(centre):
		assert_eq(board.hexes[nb]["demons"], 1, "each of 6 neighbours gains 1")
	# Chain outbreak: neighbour at 3 cascades but never back onto the origin twice.
	var w2 := _inf()
	var inf2: DmbInfection = w2["inf"]
	var b2: DmbHexBoard = w2["board"]
	var c := b2.hex_at(0, 0)
	var n0: int = b2.hex_neighbors(c)[0]
	b2.hexes[c]["demons"] = 3
	b2.hexes[n0]["demons"] = 3
	var hit2 := inf2.infect(c, 1)
	assert_eq(inf2.outbreaks, 2, "chain outbreak counted twice")
	assert_eq(hit2.size(), 2, "two hexes outbroke")
	assert_eq(b2.hexes[c]["demons"], 3, "origin not re-infected by chain (protection)")
	assert_eq(b2.hexes[n0]["demons"], 3, "cascading hex stays at 3")
	# Shared neighbours of c and n0 got 2, others 1.
	for nb in b2.hex_neighbors(c):
		if nb == n0:
			continue
		var expected := 2 if nb in b2.hex_neighbors(n0) else 1
		assert_eq(b2.hexes[nb]["demons"], expected, "neighbour infected once per outbreak")


func _test_epidemic_escalation() -> void:
	var w := _inf()
	var inf: DmbInfection = w["inf"]
	var board: DmbHexBoard = w["board"]
	assert_eq(inf.epidemic_chance, DmbInfection.BASE_EPIDEMIC_CHANCE, "starts at base chance")
	var base: float = inf.epidemic_chance
	inf.infect_step()
	var after_one: float = inf.epidemic_chance
	assert_true(after_one > base or inf.epidemics > 0, "chance rises each quiet step")
	var saw_epidemic := false
	for i in range(60):
		var log := inf.infect_step()
		for entry in log:
			if entry["type"] == "epidemic":
				saw_epidemic = true
				assert_eq(inf.epidemic_chance, DmbInfection.BASE_EPIDEMIC_CHANCE, "epidemic resets chance")
				assert_eq(board.hexes[entry["hex"]]["demons"], 3, "epidemic hex jumps to 3")
	assert_true(saw_epidemic, "an epidemic happened within 60 steps")
	assert_true(inf.epidemics >= 1, "epidemic counted")
	assert_true(inf.infection_rate >= 2, "rate escalates after epidemics")
	# Deck cycles; never runs dry.
	assert_eq(inf.deck.size() + inf.discard.size(), 19, "cards conserved")


func _test_treat() -> void:
	var w := _inf()
	var inf: DmbInfection = w["inf"]
	var board: DmbHexBoard = w["board"]
	var hid := 4
	board.hexes[hid]["demons"] = 2
	assert_eq(inf.treat(hid), 1, "treat removes one")
	assert_eq(board.hexes[hid]["demons"], 1, "one left")
	inf.treat(hid)
	assert_eq(inf.treat(hid), 0, "treating a clean hex does nothing")
	assert_eq(board.hexes[hid]["demons"], 0, "clamped at 0")
	assert_eq(inf.total_demons(), 0, "board clean")


func _test_round_trip() -> void:
	var w := _inf(17)
	var inf: DmbInfection = w["inf"]
	inf.initial_infection()
	inf.infect_step()
	var d := inf.to_dict()
	var board_copy := DmbHexBoard.from_dict(w["board"].to_dict())
	var inf2 := DmbInfection.from_dict(d, board_copy)
	assert_eq(inf2.deck, inf.deck, "deck survives")
	assert_eq(inf2.discard, inf.discard, "discard survives")
	assert_eq(inf2.outbreaks, inf.outbreaks, "outbreak count survives")
	assert_eq(inf2.epidemic_chance, inf.epidemic_chance, "chance survives")
	var l1 := inf.infect_step()
	var l2 := inf2.infect_step()
	assert_eq(l1, l2, "restored infection deterministic")
