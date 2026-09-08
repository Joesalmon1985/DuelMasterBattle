class_name DmbDifficultyProfile
extends RefCounted

## Describes how the rival wizard thinks and how quickly it casts.
##
## bot_logic:
##   "easy_random"      — random legal guesses, ignores feedback (legacy; not used by core duel)
##   "candidate_filter" — always guesses a pattern consistent with all feedback so far
##   "capped_minimax"   — consistent guess chosen to split remaining candidates best
##
## bot_think_min/max_seconds: the rival casts at a random moment inside this band
## (clamped to the encounter's cast window). Lower = more pressure on the player.

var id: String = ""
var display_name: String = ""
var description: String = ""
var bot_logic: String = "candidate_filter"
var bot_min_cast_time_multiplier: float = 1.0
var bot_max_cast_time_multiplier: float = 1.0
var bot_mistake_rate: float = 0.0
var bot_solver_cap: int = 100
var bot_think_min_seconds: float = 12.0
var bot_think_max_seconds: float = 24.0


func _init(
	p_id: String = "",
	p_display_name: String = "",
	p_description: String = "",
	p_bot_logic: String = "candidate_filter",
	p_min_mult: float = 1.0,
	p_max_mult: float = 1.0,
	p_mistake_rate: float = 0.0,
	p_solver_cap: int = 100,
	p_think_min: float = 12.0,
	p_think_max: float = 24.0
) -> void:
	id = p_id
	display_name = p_display_name
	description = p_description
	bot_logic = p_bot_logic
	bot_min_cast_time_multiplier = p_min_mult
	bot_max_cast_time_multiplier = p_max_mult
	bot_mistake_rate = p_mistake_rate
	bot_solver_cap = p_solver_cap
	bot_think_min_seconds = p_think_min
	bot_think_max_seconds = p_think_max
