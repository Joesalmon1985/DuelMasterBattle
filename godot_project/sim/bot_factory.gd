class_name DmbBotFactory
extends RefCounted

const _RandomBot = preload("res://sim/bot.gd")
const _SolverBot = preload("res://sim/solver_bot.gd")
const _DifficultyProfiles = preload("res://sim/difficulty_profiles.gd")

static func make_bot(
	ruleset: DmbDuelRuleset = null,
	difficulty = null,
	seed: int = 42
) -> RefCounted:
	var rs := ruleset if ruleset != null else DmbEncounters.default_encounter()
	var diff = difficulty if difficulty != null else _DifficultyProfiles.get_profile(
		_DifficultyProfiles.map_legacy_difficulty(rs.enemy_difficulty)
	)
	match diff.bot_logic:
		"easy_random":
			return _RandomBot.new(rs, seed)
		"candidate_filter":
			return _SolverBot.new(rs, _SolverBot.STRATEGY_RANDOM, seed)
		"capped_minimax":
			var cap: int = int(diff.bot_solver_cap)
			if cap <= 0:
				cap = _SolverBot.MAX_MINIMAX_POOL_HARD
			return _SolverBot.new(rs, _SolverBot.STRATEGY_MINIMAX, seed, cap)
		_:
			return _SolverBot.new(rs, _SolverBot.STRATEGY_MINIMAX, seed, _SolverBot.MAX_MINIMAX_POOL_EXPERT)
