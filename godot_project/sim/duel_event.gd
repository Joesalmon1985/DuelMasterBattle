class_name DmbDuelEvent
extends RefCounted

const CAST_STARTED := "cast_started"
const ATTACK_LAUNCHED := "attack_launched"
const ATTACK_IMPACTED := "attack_impacted"
const FEEDBACK_REVEALED := "feedback_revealed"
const WARD_BROKEN := "ward_broken"
const LAST_STAND_STARTED := "last_stand_started"
const DUEL_FINISHED := "duel_finished"

var type: String = ""
var data: Dictionary = {}


func _init(p_type: String = "", p_data: Dictionary = {}) -> void:
	type = p_type
	data = p_data
