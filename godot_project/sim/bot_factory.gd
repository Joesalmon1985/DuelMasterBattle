class_name DmbBotFactory
extends RefCounted

const _RandomBot = preload("res://sim/bot.gd")
const _SolverBot = preload("res://sim/solver_bot.gd")


static func make_bot(difficulty: String = "expert", seed: int = 42) -> RefCounted:
	var level := difficulty.to_lower()
	match level:
		"easy":
			return _RandomBot.new(seed)
		"normal":
			return _SolverBot.new(_SolverBot.STRATEGY_RANDOM, seed)
		"hard", "expert":
			return _SolverBot.new(_SolverBot.STRATEGY_MINIMAX, seed)
		_:
			return _SolverBot.new(_SolverBot.STRATEGY_MINIMAX, seed)
