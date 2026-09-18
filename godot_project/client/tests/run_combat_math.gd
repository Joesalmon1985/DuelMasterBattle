extends SceneTree

## Headless golden-case check for shared combat math (T060).

const CombatMath = preload("res://client/combat/combat_math.gd")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var path := "res://content/fixtures/combat_math.json"
	if not FileAccess.file_exists(path):
		push_error("missing fixture %s" % path)
		quit(1)
		return
	var raw := FileAccess.get_file_as_string(path)
	var data = JSON.parse_string(raw)
	if typeof(data) != TYPE_DICTIONARY:
		push_error("invalid fixture JSON")
		quit(1)
		return
	for case_any in data.get("cases", []):
		var case: Dictionary = case_any
		var got := CombatMath.compute_damage(
			float(case["base_attack"]),
			float(case["era_factor"]),
			float(case.get("attack_modifiers", 1.0)),
			float(case["cover"]),
			float(case.get("armour", 0))
		)
		var expected := int(case["expected_damage"])
		if got != expected:
			push_error("case %s expected %s got %s" % [case.get("id"), expected, got])
			quit(1)
			return
	for tcase_any in data.get("targeting", {}).get("cases", []):
		var tcase: Dictionary = tcase_any
		var got_t = CombatMath.choose_target(tcase["attacker"], tcase["candidates"])
		if str(got_t) != str(tcase["expected_target"]):
			push_error("target %s expected %s got %s" % [tcase.get("id"), tcase["expected_target"], got_t])
			quit(1)
			return
	var sim: Dictionary = data.get("simultaneity", {})
	var units: Dictionary = (sim.get("units", {}) as Dictionary).duplicate(true)
	var step1 = CombatMath.resolve_combat_step(units, int(sim.get("step_ms", 50)))
	if bool(sim.get("expect_both_fire_step1", false)) and step1["fired"].size() != 2:
		push_error("expected both fire step1: %s" % step1)
		quit(1)
		return
	if bool(sim.get("expect_both_dead_after_step1", false)):
		for uid in units.keys():
			if bool(units[uid].get("alive", true)):
				push_error("expected dead %s" % uid)
				quit(1)
				return
	var step2 = CombatMath.resolve_combat_step(units, int(sim.get("step_ms", 50)))
	if bool(sim.get("expect_no_fire_step2", false)) and step2["fired"].size() != 0:
		push_error("dead should not fire: %s" % step2)
		quit(1)
		return
	print("COMBAT_MATH_OK cases=", data.get("cases", []).size())
	quit(0)
