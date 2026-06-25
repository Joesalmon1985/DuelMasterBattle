class_name DmbBotFactory
extends RefCounted

const _RandomBot = preload("res://sim/bot.gd")
const _SolverBot = preload("res://sim/solver_bot.gd")


static func make_bot(ruleset: DmbDuelRuleset = null, seed: int = 42) -> RefCounted:
	var rs := ruleset if ruleset != null else DmbEncounters.default_encounter()
	var level := rs.enemy_difficulty.to_lower()
	match level:
		"easy":
			return _RandomBot.new(rs, seed)
		"normal":
			return _SolverBot.new(rs, _SolverBot.STRATEGY_RANDOM, seed)
		"hard":
			return _SolverBot.new(rs, _SolverBot.STRATEGY_MINIMAX, seed, _SolverBot.MAX_MINIMAX_POOL_HARD)
		"expert":
			return _SolverBot.new(rs, _SolverBot.STRATEGY_MINIMAX, seed, _SolverBot.MAX_MINIMAX_POOL_EXPERT)
		_:
			return _SolverBot.new(rs, _SolverBot.STRATEGY_MINIMAX, seed, _SolverBot.MAX_MINIMAX_POOL_EXPERT)
