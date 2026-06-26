class_name DmbAttackRecord
extends RefCounted

var attacker_id: String = ""
var target_id: String = ""
var attack_number: int = 0
var cast_time: float = 0.0
var was_auto_cast: bool = false
var pattern_by_locus: Array = []
var fracture_count: int = 0
var echo_count: int = 0
var fade_count: int = 0
var broke_ward: bool = false
var triggered_last_stand: bool = false


func to_ui_dict() -> Dictionary:
	return {
		"attacker_id": attacker_id,
		"attack_number": attack_number,
		"cast_time": cast_time,
		"was_auto_cast": was_auto_cast,
		"pattern_by_locus": pattern_by_locus.duplicate(),
		"fracture_count": fracture_count,
		"echo_count": echo_count,
		"fade_count": fade_count,
		"broke_ward": broke_ward,
		"triggered_last_stand": triggered_last_stand,
	}
