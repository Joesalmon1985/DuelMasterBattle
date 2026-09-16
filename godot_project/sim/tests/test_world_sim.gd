extends DmbTestCase
## Faction AI heuristics and the world orchestrator. Proves:
## * a 200-turn headless run completes, is deterministic and serialisable;
## * Guardian factions treat far more than Corrupting ones;
## * a ruler adjustment measurably shifts a faction's decisions.


func run() -> void:
	_test_weights_and_presets()
	_test_setup()
	_test_long_run_and_stances()
	_test_ruler_adjust_shifts_behaviour()
	_test_determinism_and_round_trip()


func _test_weights_and_presets() -> void:
	var g := DmbFactionAI.preset("guardian")
	var c := DmbFactionAI.preset("corrupting")
	for k in DmbFactionAI.KEYS:
		assert_true(g.has(k), "guardian preset has %s" % k)
		assert_true(c.has(k), "corrupting preset has %s" % k)
	assert_true(g["treat"] > c["treat"], "guardians weight treating higher")
	assert_true(c["roads"] + c["settlements"] > g["roads"] + g["settlements"], "corrupters weight expansion higher")
	var w := DmbWorldSim.new(1)
	w.setup()
	var before: float = w.ai_weights("kilns")["treat"]
	w.ruler_adjust("kilns", "treat", 0.3)
	assert_eq(w.ai_weights("kilns")["treat"], minf(before + 0.3, DmbFactionAI.MAX_WEIGHT), "adjust adds and clamps")
	w.ruler_adjust("kilns", "treat", -99.0)
	assert_eq(w.ai_weights("kilns")["treat"], DmbFactionAI.MIN_WEIGHT, "clamps at minimum")
	assert_true(not w.ruler_adjust("kilns", "nonsense", 1.0), "unknown key rejected")


func _test_setup() -> void:
	var w := DmbWorldSim.new(2)
	w.setup()
	assert_eq(w.factions.size(), 6, "six factions")
	for f in w.factions:
		assert_eq(w.catan.settlement_count(f), 2, "%s has 2 starting settlements" % f)
		assert_eq(w.catan.road_count(f), 2, "%s has 2 starting roads" % f)
		assert_true(w.catan.hand_total(f) > 0, "%s received setup resources" % f)
		assert_true(w.units.champion_of(f) != null, "%s has a champion" % f)
		assert_eq(w.units.champion_of(f)["name"], DmbFactions.get_data(f)["champion"], "champion named")
	assert_eq(w.infection.total_demons(), 18, "Pandemic starting infection")
	assert_eq(w.turn, 0, "turn zero")
	assert_true(w.player_home_node() >= 0, "player home exists")
	assert_eq(w.catan.owner_at(w.player_home_node()), "wardens", "John starts at a Warden settlement")


func _test_long_run_and_stances() -> void:
	var w := DmbWorldSim.new(3)
	w.setup()
	var total_events := 0
	for i in range(200):
		var events := w.advance_turn()
		total_events += events.size()
	assert_eq(w.turn, 200, "200 turns advanced")
	assert_true(total_events > 200, "turns produce events")
	var stats := w.stats
	var g_treats := 0
	var c_treats := 0
	var g_builds := 0
	var c_builds := 0
	for f in w.factions:
		var s: Dictionary = stats[f]
		if DmbFactions.stance_of(f) == "guardian":
			g_treats += s["treats"]
			g_builds += s["roads"] + s["settlements"] + s["cities"]
		else:
			c_treats += s["treats"]
			c_builds += s["roads"] + s["settlements"] + s["cities"]
	assert_true(g_treats > c_treats * 2, "guardians treat > 2x corrupters (%d vs %d)" % [g_treats, c_treats])
	assert_true(c_builds > 0 and g_builds > 0, "everyone builds something")
	var built_any := false
	var traded := false
	for f in w.factions:
		if w.catan.road_count(f) > 2 or w.catan.settlement_count(f) > 2 or w.catan.city_count(f) > 0:
			built_any = true
		if stats[f]["trades"] > 0:
			traded = true
	assert_true(built_any, "board developed over 200 turns")
	assert_true(traded, "carts were sent")
	assert_true(w.infection.outbreaks >= 0, "outbreak counter sane")
	assert_true(w.infection.total_demons() <= 57, "demons within board cap")
	for f in w.factions:
		assert_true(w.catan.victory_points(f) >= 2, "VP never drops below the two settlements")
	# Every turn's events are dictionaries with a type and a prose line.
	var evs := w.advance_turn()
	for e in evs:
		assert_true(e.has("type") and e.has("text"), "event has type and text")


func _test_ruler_adjust_shifts_behaviour() -> void:
	var a := DmbWorldSim.new(4)
	a.setup()
	var b := DmbWorldSim.new(4)
	b.setup()
	# Push the Ironmoot from corrupting to zealous treating.
	b.ruler_adjust("ironmoot", "treat", 3.0)
	b.ruler_adjust("ironmoot", "roads", -3.0)
	b.ruler_adjust("ironmoot", "settlements", -3.0)
	for i in range(150):
		a.advance_turn()
		b.advance_turn()
	var ta: int = a.stats["ironmoot"]["treats"]
	var tb: int = b.stats["ironmoot"]["treats"]
	assert_true(tb > ta, "ruler shift raises treats (%d → %d)" % [ta, tb])
	var ba: int = a.stats["ironmoot"]["roads"] + a.stats["ironmoot"]["settlements"]
	var bb: int = b.stats["ironmoot"]["roads"] + b.stats["ironmoot"]["settlements"]
	assert_true(bb <= ba, "ruler shift lowers expansion (%d → %d)" % [ba, bb])


func _test_determinism_and_round_trip() -> void:
	var a := DmbWorldSim.new(5)
	a.setup()
	var b := DmbWorldSim.new(5)
	b.setup()
	for i in range(30):
		a.advance_turn()
		b.advance_turn()
	assert_eq(a.snapshot(), b.snapshot(), "same seed, same world after 30 turns")
	var d := a.to_dict()
	var c := DmbWorldSim.from_dict(d)
	assert_eq(c.snapshot(), a.snapshot(), "round trip preserves the world")
	assert_eq(c.turn, 30, "turn restored")
	# The settlement layer is a pure function of restored state: profiles and
	# projected areas match across the round trip and across same-seed worlds.
	for k in a.catan.settlements:
		var nid := int(k)
		assert_eq(str(DmbSettlementProfile.describe(c, nid)), str(DmbSettlementProfile.describe(a, nid)), "restored profile matches at %d" % nid)
		assert_eq(str(DmbSettlementProfile.describe(b, nid)), str(DmbSettlementProfile.describe(a, nid)), "same-seed profile matches at %d" % nid)
		assert_eq(str(DmbNodeProjection.area_for(c, nid)), str(DmbNodeProjection.area_for(a, nid)), "restored projection matches at %d" % nid)
	var ea := a.advance_turn()
	var ec := c.advance_turn()
	assert_eq(a.snapshot(), c.snapshot(), "restored world continues identically")
	assert_eq(ea.size(), ec.size(), "same events after restore")
	var e := DmbWorldSim.new(6)
	e.setup()
	for i in range(30):
		e.advance_turn()
	assert_true(e.snapshot() != a.snapshot(), "different seed, different world")
