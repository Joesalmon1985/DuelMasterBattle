extends SceneTree

## Balance + performance probe for the rival AI on the core duel.
## godot --headless --path godot_project --script res://sim/tools/balance_probe.gd

const _SolverBot = preload("res://sim/solver_bot.gd")
const _BotFactory = preload("res://sim/bot_factory.gd")
const _Encounters = preload("res://sim/encounters.gd")
const _DifficultyProfiles = preload("res://sim/difficulty_profiles.gd")
const _RealtimeSim = preload("res://sim/realtime_duel_sim.gd")


func _init() -> void:
	var rs := _Encounters.get_encounter("core_duel")
	var all := DmbCandidateGen.generate_candidate_codes(rs)
	for diff_id in ["easy", "medium", "hard"]:
		var diff = _DifficultyProfiles.get_profile(diff_id)
		var solved := 0
		var total := 0
		var hist: Dictionary = {}
		var n := 0
		var worst_think_usec := 0
		for i in range(0, all.size(), 9):
			var bot = _BotFactory.make_bot(rs, diff, i)
			var secret: Array = all[i]
			var count := 0
			var ok := false
			for _g in range(10):
				bot.begin_planning()
				var t0 := Time.get_ticks_usec()
				var frames := 0
				while not bot.think(3.0):
					frames += 1
				worst_think_usec = maxi(worst_think_usec, Time.get_ticks_usec() - t0)
				var g: Array = bot.planned_guess()
				count += 1
				var fb := DmbFeedback.score_guess(secret, g)
				if fb.x == 4:
					ok = true
					break
				bot.register_feedback(g, fb.x, fb.y)
			n += 1
			if ok:
				solved += 1
				total += count
				hist[count] = hist.get(count, 0) + 1
		var avg := float(total) / maxf(solved, 1)
		print("%-6s solved %d/%d (%.0f%%)  avg casts %.2f  worst plan %.1f ms  dist %s" % [
			diff_id, solved, n, 100.0 * solved / n, avg, worst_think_usec / 1000.0, str(hist)])
	# Per-frame think budget on the worst case (hard, after opening feedback).
	var bot2 = _SolverBot.new(rs, _SolverBot.STRATEGY_MINIMAX, 3, 60)
	bot2.make_guess()
	bot2.register_feedback([0, 0, 1, 1], 0, 1)
	bot2.begin_planning()
	var slices: Array = []
	while not bot2.think(3.0):
		slices.append(1)
	print("hard replan split over %d frames of <=3 ms" % (slices.size() + 1))
	quit(0)
