extends Node

const _Encounters = preload("res://sim/encounters.gd")
const _DifficultyProfiles = preload("res://sim/difficulty_profiles.gd")

var selected_encounter_id: String = _Encounters.DEFAULT_ENCOUNTER_ID
var selected_difficulty_id: String = "medium"


func get_ruleset() -> DmbDuelRuleset:
	return _Encounters.get_encounter(selected_encounter_id)


func get_difficulty_profile():
	return _DifficultyProfiles.get_profile(selected_difficulty_id)


func set_encounter(encounter_id: String) -> void:
	selected_encounter_id = encounter_id


func set_difficulty(difficulty_id: String) -> void:
	selected_difficulty_id = difficulty_id
