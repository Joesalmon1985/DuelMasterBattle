extends SceneTree

## Exports what the real Ward Duel GDScript (feedback.gd, game_logic.gd, candidate_gen.gd, auto_cast.gd, weave_bot.gd) produces so the
## Python port (wizard_rts/duel/ward.py) can be parity-tested. godot --headless --path godot_project --script res://client/tests/export_ward_parity.gd -- out.json


func _init() -> void:
	var out_path := "user://ward_parity.json"
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		out_path = args[0]
	var rng := RandomNumberGenerator.new()
	rng.seed = 2026
	var data := {"feedback": [], "results": [], "codes": [], "bots": []}
	for i in 500:
		var ws := rng.randi_range(1, 6)
		var as_ := rng.randi_range(1, 8)
		var pool := rng.randi_range(2, 10)
		var ward: Array = []
		var attack: Array = []
		for _j in ws:
			ward.append(rng.randi_range(0, pool - 1))
		for _j in as_:
			attack.append(rng.randi_range(0, pool - 1))
		var r: Dictionary = DmbFeedback.score_attack(ward, attack)
		var entry := {"ward": ward, "attack": attack, "result": _plain(r)}
		if ws == as_:
			var g: Vector2i = DmbFeedback.score_guess(ward, attack)
			entry["guess"] = [g.x, g.y]
		data["feedback"].append(entry)
	for i in 400:
		var hs := rng.randi_range(0, 1) == 1
		var bs := rng.randi_range(0, 1) == 1
		var hc := rng.randi_range(1, 12)
		var bc := rng.randi_range(1, 12)
		var hrec: Array = []
		var brec: Array = []
		var hpy: Array = []
		var bpy: Array = []
		for _j in hc:
			var ex := rng.randi_range(0, 4)
			var co := rng.randi_range(0, 4 - ex)
			var rec := DmbGuessRecord.new([0, 0, 0, 0], ex, co)
			hrec.append(rec)
			hpy.append([rec.exact, rec.colour_only])
		for _j in bc:
			var ex2 := rng.randi_range(0, 4)
			var co2 := rng.randi_range(0, 4 - ex2)
			var rec2 := DmbGuessRecord.new([0, 0, 0, 0], ex2, co2)
			brec.append(rec2)
			bpy.append([rec2.exact, rec2.colour_only])
		var res: DmbGameResult = DmbGameLogic.compute_result(hs, bs, hc, bc, hrec, brec, 12)
		data["results"].append({"hs": hs, "bs": bs, "hc": hc, "bc": bc, "hg": hpy, "bg": bpy, "outcome": res.outcome})
	for cfg in [[[0, 1, 3, 4, 6, 9], 4, true], [[0, 1, 3, 4, 6, 9], 4, false], [[0, 1, 2, 3], 3, true], [[0, 1, 3], 4, true], [[2, 5, 7, 8], 2, false]]:
		var codes: Array = DmbCandidateGen.generate_codes(cfg[0], cfg[1], cfg[2])
		data["codes"].append({"pool": cfg[0], "slots": cfg[1], "repeats": cfg[2], "count": codes.size(), "first": codes.slice(0, 3), "last": codes.slice(codes.size() - 3, codes.size())})
	var configs := [
		{"logic": "candidate_filter", "weave": 4, "ward": 4, "pool": [0, 1, 3, 4, 6, 9], "wpool": [0, 1, 3, 4, 6, 9], "rep": true},
		{"logic": "random", "weave": 4, "ward": 4, "pool": [0, 1, 3, 4, 6, 9], "wpool": [0, 1, 3, 4, 6, 9], "rep": true},
		{"logic": "candidate_filter", "weave": 3, "ward": 4, "pool": [0, 1, 3, 4, 6, 9], "wpool": [0, 1, 3, 4, 6, 9], "rep": false},
		{"logic": "candidate_filter", "weave": 4, "ward": 3, "pool": [0, 1, 2, 3, 4], "wpool": [0, 1, 2, 3, 4], "rep": true},
		{"logic": "candidate_filter", "weave": 5, "ward": 2, "pool": [0, 1, 2, 3], "wpool": [2, 3, 4], "rep": true},
	]
	for ci in configs.size():
		var cfg: Dictionary = configs[ci]
		for seed_value in [1, 7, 42, 1234, 99999]:
			var me := DmbCombatant.make({"id": "bot", "weave_size": cfg["weave"], "attack_pool": cfg["pool"], "ward_size": cfg["ward"], "ward_pool": cfg["wpool"], "allow_repeats": cfg["rep"], "bot_logic": cfg["logic"]})
			var tgt := DmbCombatant.make({"id": "tgt", "weave_size": cfg["weave"], "attack_pool": cfg["pool"], "ward_size": cfg["ward"], "ward_pool": cfg["wpool"], "allow_repeats": cfg["rep"]})
			var bot := DmbWeaveBot.new(me, tgt, seed_value)
			var secret: Array = bot.generate_ward()
			var rounds: Array = []
			for k in 8:
				var g: Array = bot.make_guess()
				var sc: Dictionary = DmbFeedback.score_attack(secret, g)
				bot.register_feedback(g, int(sc["fracture"]), int(sc["echo"]))
				rounds.append({"guess": g, "fracture": sc["fracture"], "echo": sc["echo"], "cands": bot.candidate_count()})
			data["bots"].append({"cfg": ci, "seed": seed_value, "ward": secret, "rounds": rounds, "combatant": {"weave_size": cfg["weave"], "attack_pool": cfg["pool"], "ward_size": cfg["ward"], "ward_pool": cfg["wpool"], "allow_repeats": cfg["rep"], "bot_logic": cfg["logic"]}})
	var f := FileAccess.open(out_path, FileAccess.WRITE)
	f.store_string(JSON.stringify(data, "", true))
	f.close()
	print("WARD_PARITY_EXPORTED %s" % out_path)
	quit(0)


func _plain(v):
	match typeof(v):
		TYPE_DICTIONARY:
			var o := {}
			for k in v:
				o[str(k)] = _plain(v[k])
			return o
		TYPE_ARRAY:
			var a := []
			for x in v:
				a.append(_plain(x))
			return a
		_:
			return v
