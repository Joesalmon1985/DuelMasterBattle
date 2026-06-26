class_name DmbDifficultyProfile
extends RefCounted

var id: String = ""
var display_name: String = ""
var description: String = ""
var bot_logic: String = "candidate_filter"
var bot_min_cast_time_multiplier: float = 1.0
var bot_max_cast_time_multiplier: float = 1.0
var bot_mistake_rate: float = 0.0
var bot_solver_cap: int = 100


func _init(
	p_id: String = "",
	p_display_name: String = "",
	p_description: String = "",
	p_bot_logic: String = "candidate_filter",
	p_min_mult: float = 1.0,
	p_max_mult: float = 1.0,
	p_mistake_rate: float = 0.0,
	p_solver_cap: int = 100
) -> void:
	id = p_id
	display_name = p_display_name
	description = p_description
	bot_logic = p_bot_logic
	bot_min_cast_time_multiplier = p_min_mult
	bot_max_cast_time_multiplier = p_max_mult
	bot_mistake_rate = p_mistake_rate
	bot_solver_cap = p_solver_cap
