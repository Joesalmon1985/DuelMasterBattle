class_name DmbDuelRuleset
extends RefCounted

var id: String = ""
var display_name: String = ""
var description: String = ""
var slot_count: int = 4
var point_names: Array = []
var secret_magic_pool: Array = []
var attack_magic_pool: Array = []
var max_attacks_per_player: int = 12
var enemy_name: String = ""
var enemy_archetype: String = ""
var enemy_visual_hint: String = ""
var enemy_difficulty: String = "expert"
var player_modifiers: Dictionary = {}
var enemy_modifiers: Dictionary = {}
var counterspell_seconds: float = 0.0
var allow_repeats: bool = true
var mode: String = "alternating"
var allow_hidden_secret_types: bool = false


func _init(
	p_id: String = "",
	p_display_name: String = "",
	p_description: String = "",
	p_slot_count: int = 4,
	p_point_names: Array = [],
	p_secret_pool: Array = [],
	p_attack_pool: Array = [],
	p_max_attacks: int = 12,
	p_enemy_name: String = "",
	p_enemy_archetype: String = "",
	p_enemy_hint: String = "",
	p_difficulty: String = "expert",
	p_allow_repeats: bool = true
) -> void:
	id = p_id
	display_name = p_display_name
	description = p_description
	slot_count = p_slot_count
	point_names = p_point_names
	secret_magic_pool = p_secret_pool
	attack_magic_pool = p_attack_pool
	max_attacks_per_player = p_max_attacks
	enemy_name = p_enemy_name
	enemy_archetype = p_enemy_archetype
	enemy_visual_hint = p_enemy_hint
	enemy_difficulty = p_difficulty
	allow_repeats = p_allow_repeats
	validate()


func validate() -> void:
	assert(slot_count >= 1 and slot_count <= 4, "slot_count must be 1-4")
	assert(point_names.size() == slot_count, "point_names length must match slot_count")
	validate_pools()


func validate_pools() -> void:
	if allow_hidden_secret_types:
		return
	for s in secret_magic_pool:
		var found := false
		for a in attack_magic_pool:
			if int(s) == int(a):
				found = true
				break
		assert(found, "secret_magic_pool must be subset of attack_magic_pool")


func effective_max_attacks() -> int:
	return max_attacks_per_player + int(player_modifiers.get("extra_attacks", 0))


func bot_delay_multiplier() -> float:
	return float(enemy_modifiers.get("bot_attack_delay_multiplier", 1.0))


func is_solved(exact_hits: int) -> bool:
	return exact_hits == slot_count
