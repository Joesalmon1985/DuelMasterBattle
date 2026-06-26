class_name DmbDifficultyProfiles
extends RefCounted

const _Profile = preload("res://sim/difficulty_profile.gd")

static var _catalog: Dictionary = {}


static func _build() -> void:
	if not _catalog.is_empty():
		return
	_register(_Profile.new(
		"easy", "Easy",
		"Slower rival, simpler attacks.",
		"easy_random", 1.4, 1.4, 0.35, 0
	))
	_register(_Profile.new(
		"medium", "Medium",
		"Balanced duel.",
		"candidate_filter", 1.0, 1.0, 0.05, 100
	))
	_register(_Profile.new(
		"hard", "Hard",
		"Faster rival, sharper deduction.",
		"capped_minimax", 0.75, 0.75, 0.0, 100
	))


static func _register(p) -> void:
	_catalog[p.id] = p


static func get_profile(difficulty_id: String):
	_build()
	assert(_catalog.has(difficulty_id), "unknown difficulty: %s" % difficulty_id)
	return _catalog[difficulty_id]


static func all_profiles() -> Array:
	_build()
	return [_catalog["easy"], _catalog["medium"], _catalog["hard"]]


static func map_legacy_difficulty(encounter_difficulty: String) -> String:
	match encounter_difficulty.to_lower():
		"easy":
			return "easy"
		"normal":
			return "medium"
		"hard", "expert":
			return "hard"
		_:
			return "medium"
