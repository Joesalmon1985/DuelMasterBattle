extends Node

const _Encounters = preload("res://sim/encounters.gd")

var selected_encounter_id: String = _Encounters.DEFAULT_ENCOUNTER_ID


func get_ruleset() -> DmbDuelRuleset:
	return _Encounters.get_encounter(selected_encounter_id)


func set_encounter(encounter_id: String) -> void:
	selected_encounter_id = encounter_id
