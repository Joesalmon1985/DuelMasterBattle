class_name DmbDifficultyProfiles
extends RefCounted

const _Profile = preload("res://sim/difficulty_profile.gd")

static var _catalog: Dictionary = {}


static func _build() -> void:
	if not _catalog.is_empty():
		return
	# id, name, description, logic, min-mult, max-mult, mistake-rate, solver-cap, think-min, think-max
	#
	# Balance (sim/tools/balance_probe.gd): all three solve ~100% of wards within
	# 10 casts; average casts easy 5.4 / medium 4.6 / hard 4.5. A typical human
	# needs 5–7, so the think band is the main lever: apprentice ~37 s/cast,
	# adept ~23 s/cast, archmage ~15 s/cast.
	_register(_Profile.new(
		"easy", "Apprentice",
		"A slow rival who sometimes forgets what it has learned.",
		"candidate_filter", 1.0, 1.0, 0.4, 0, 26.0, 48.0
	))
	_register(_Profile.new(
		"medium", "Adept",
		"A steady rival that never wastes a cast.",
		"candidate_filter", 1.0, 1.0, 0.0, 0, 16.0, 30.0
	))
	_register(_Profile.new(
		"hard", "Archmage",
		"A fast rival that picks the most revealing spells.",
		"capped_minimax", 1.0, 1.0, 0.0, 60, 10.0, 20.0
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
