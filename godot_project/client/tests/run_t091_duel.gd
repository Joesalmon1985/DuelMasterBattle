extends SceneTree

## T091 duel progression client helper.
## godot --headless --path godot_project --script res://client/tests/run_t091_duel.gd

const Progression = preload("res://client/duel/progression.gd")

var _failures: Array = []


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	var rules := Progression.load_rules()
	_assert(not rules.is_empty(), "rules missing")
	_assert(str(rules.get("engine", "")) == "DmbBattleSim", "engine")
	var fb: Vector2i = Progression.score_guess([0, 0, 1, 2], [0, 1, 0, 3])
	_assert(fb.x == 1 and fb.y == 2, "AABC vs ABAD feedback")
	var pre := Progression.tier_for_era("prehistoric")
	var fut := Progression.tier_for_era("futuristic")
	_assert(int(pre.get("slot_count", 0)) == 4, "prehistoric slots")
	_assert(int(fut.get("slot_count", 0)) == 6, "futuristic slots")
	var caps := Progression.caps()
	_assert(int(caps.get("max_colour_count", 0)) == 8, "colour cap")
	var overflow := Progression.overflow_reward()
	_assert(str(overflow.get("id", "")).begins_with("reward."), "overflow reward")
	if _failures.is_empty():
		print("T091_DUEL_OK")
		quit(0)
	else:
		for f in _failures:
			push_error(str(f))
		print("T091_DUEL_FAIL")
		quit(1)


func _assert(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)
