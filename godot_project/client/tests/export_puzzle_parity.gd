extends SceneTree

## Exports what the real GDScript puzzle code produces, so the Python port (WizardRTSHybrid/wizard_rts/puzzle) can be parity-tested
## against it: RNG probes, generated puzzle records for many seeds, action traces through DmbPuzzleLogic, and DmbDungeonMap layouts.
## Usage: godot --headless --path godot_project --script res://client/tests/export_puzzle_parity.gd -- <out.json>

const ITEMS := ["clay_idol", "brass_gear", "tallow_candle", "mirror_shard", "black_seed", "grey_stone", "iron_key", "sigil_ash", "sigil_vale"]


func _init() -> void:
	var out_path := "user://puzzle_parity.json"
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		out_path = args[0]
	var data := {"rng": [], "puzzles": [], "maps": []}
	for seed_value in [0, 1, 7, 12345, 987654321, 4294967296 + 3]:
		var rng := RandomNumberGenerator.new()
		rng.seed = seed_value
		var probe := {"seed": seed_value, "randi": [], "range_0_1": [], "range_0_2": [], "range_1_3": [], "range_0_5": [], "range_0_8": []}
		for i in 8:
			probe["randi"].append(rng.randi())
		var r2 := RandomNumberGenerator.new()
		r2.seed = seed_value
		for i in 8:
			probe["range_0_1"].append(r2.randi_range(0, 1))
		for i in 8:
			probe["range_0_2"].append(r2.randi_range(0, 2))
		for i in 8:
			probe["range_1_3"].append(r2.randi_range(1, 3))
		for i in 8:
			probe["range_0_5"].append(r2.randi_range(0, 5))
		for i in 8:
			probe["range_0_8"].append(r2.randi_range(0, 8))
		data["rng"].append(probe)
	for s in range(1, 81):
		var need_item: String = "sigil_ash" if s % 2 == 0 else "sigil_vale"
		var d := {"id": "cave_%d" % s, "kind": "cave" if s % 3 else "tower", "faction": "Red", "seed": s * 7919, "provides": "sigil_x%d" % s,
			"needs": {"item": need_item, "from": "settlement" if s % 4 else "cave_%d" % (s + 1)}}
		var puzzles: Array = DmbPuzzleGen.generate(d)
		d["puzzles"] = puzzles
		var traces: Array = []
		for p in puzzles:
			traces.append(_trace(p))
		data["puzzles"].append({"dungeon": d, "traces": traces})
		if s <= 12:
			var area: Dictionary = DmbDungeonMap.area_for(d, {}, "node_1", [3, 4])
			var area2: Dictionary = DmbDungeonMap.area_for(d, _solved_states(d), "node_1", [3, 4])
			data["maps"].append({"dungeon_id": d["id"], "area": _plain(area), "area_solved": _plain(area2)})
	var f := FileAccess.open(out_path, FileAccess.WRITE)
	f.store_string(JSON.stringify(data, "", true))
	f.close()
	print("PUZZLE_PARITY_EXPORTED %s puzzles=%d" % [out_path, data["puzzles"].size() * 4])
	quit(0)


func _solved_states(d: Dictionary) -> Dictionary:
	var states := {}
	for p in d["puzzles"]:
		var st := DmbPuzzleLogic.fresh_state(p)
		st["solved"] = true
		states["%s/%s" % [d["id"], p["id"]]] = st
	return states


## Several action scripts per puzzle: the intended solution, a wrong start, repeated actions, and a stray action of every kind.
func _trace(p: Dictionary) -> Dictionary:
	var scripts: Array = []
	var ctx_full := {"items": ITEMS.duplicate(), "spells": [0, 1, 6]}
	var ctx_none := {"items": [], "spells": []}
	scripts.append({"name": "solution", "ctx": ctx_full, "actions": DmbPuzzleLogic.solution(p)})
	scripts.append({"name": "solution_no_items", "ctx": ctx_none, "actions": DmbPuzzleLogic.solution(p)})
	var stray: Array = [{"kind": "inspect", "slot": "x"}, {"kind": "take"}, {"kind": "pull", "index": 9}, {"kind": "tread", "index": 9}, {"kind": "step_on"},
		{"kind": "step"}, {"kind": "pass"}, {"kind": "cast", "spell": 99}, {"kind": "cast", "spell": 1}, {"kind": "place", "item": "clay_idol", "slot": "none"},
		{"kind": "place", "item": "grey_stone"}, {"kind": "place", "item": "iron_key"}, {"kind": "pull", "index": 0}, {"kind": "pull", "index": 1}, {"kind": "pull", "index": 2},
		{"kind": "tread", "index": 0}, {"kind": "tread", "index": 1}, {"kind": "take"}, {"kind": "pass"}, {"kind": "step"}, {"kind": "step"}]
	scripts.append({"name": "stray", "ctx": ctx_full, "actions": stray})
	var sol: Array = DmbPuzzleLogic.solution(p)
	var twice: Array = sol.duplicate()
	twice.append_array(sol)
	scripts.append({"name": "solution_twice", "ctx": ctx_full, "actions": twice})
	var out: Array = []
	for s in scripts:
		var st := DmbPuzzleLogic.fresh_state(p)
		var results: Array = []
		for a in s["actions"]:
			var r: Dictionary = DmbPuzzleLogic.act(p, st, a, s["ctx"])
			results.append({"result": _plain(r), "state": _plain(st)})
		out.append({"name": s["name"], "ctx": s["ctx"], "actions": s["actions"], "fresh": _plain(DmbPuzzleLogic.fresh_state(p)), "steps": results})
	return {"puzzle": p["id"], "scripts": out}


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
		TYPE_FLOAT:
			return v
		TYPE_VECTOR2, TYPE_VECTOR2I:
			return [v.x, v.y]
		_:
			return v
