class_name DmbEncounters
extends RefCounted

const DEFAULT_ENCOUNTER_ID := "archmage_duel"

static var _catalog: Dictionary = {}


static func _build_catalog() -> void:
	if not _catalog.is_empty():
		return
	_register(_make_blue_apprentice())
	_register(_make_thorn_adept())
	_register(_make_mirror_mage())
	_register(_make_archmage_duel())


static func _register(rs: DmbDuelRuleset) -> void:
	_catalog[rs.id] = rs


static func get_encounter(encounter_id: String) -> DmbDuelRuleset:
	_build_catalog()
	assert(_catalog.has(encounter_id), "unknown encounter: %s" % encounter_id)
	return _catalog[encounter_id]


static func all_encounters() -> Array:
	_build_catalog()
	return [
		_catalog["blue_apprentice"],
		_catalog["thorn_adept"],
		_catalog["mirror_mage"],
		_catalog["archmage_duel"],
	]


static func default_encounter() -> DmbDuelRuleset:
	return get_encounter(DEFAULT_ENCOUNTER_ID)


static func _make_blue_apprentice() -> DmbDuelRuleset:
	return DmbDuelRuleset.new(
		"blue_apprentice", "Blue Apprentice",
		"A novice duelist — one point, limited magics.",
		1, ["Shield"], [1, 2, 9], [0, 1, 2, 9], 4,
		"Blue Apprentice", "blue_wizard",
		"Blue robes and a hesitant wand grip.", "easy"
	)


static func _make_thorn_adept() -> DmbDuelRuleset:
	var rs := DmbDuelRuleset.new(
		"thorn_adept", "Thorn Adept",
		"Nature magic — two points, thorny defences.",
		2, ["Shield", "Body"], [6, 3, 0, 7], [6, 3, 0, 7, 1], 6,
		"Thorn Adept", "thorn_druid",
		"Thorns and bark woven into their robes.", "normal",
		false
	)
	return rs


static func _make_mirror_mage() -> DmbDuelRuleset:
	return DmbDuelRuleset.new(
		"mirror_mage", "Mirror Mage",
		"Reflected power — three points, repeats allowed.",
		3, ["Shield", "Body", "Staff"], [4, 5, 8, 9], [4, 5, 8, 9], 8,
		"Mirror Mage", "mirror_mage",
		"Mirrored robes that shimmer with duplicate spells.", "hard"
	)


static func _make_archmage_duel() -> DmbDuelRuleset:
	var all_magics: Array = []
	for i in range(DmbConstants.NUM_COLOURS):
		all_magics.append(i)
	return DmbDuelRuleset.new(
		"archmage_duel", "Archmage Duel",
		"The full wizard duel — classic Mastermind rules.",
		DmbConstants.CODE_LENGTH, DmbColourData.POINT_NAMES.duplicate(),
		all_magics.duplicate(), all_magics.duplicate(), DmbConstants.MAX_GUESSES,
		"Archmage", "archmage",
		"Full duel rules — every magic, every point.", "expert"
	)
