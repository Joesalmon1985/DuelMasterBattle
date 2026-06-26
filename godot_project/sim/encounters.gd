class_name DmbEncounters
extends RefCounted

const DEFAULT_ENCOUNTER_ID := "archmage_duel"
const _LOCUS := ["Roach", "Uzag", "Lieana", "Gyse", "Vorr", "Mael", "Oshen", "Keth"]

static var _catalog: Dictionary = {}


static func _build_catalog() -> void:
	if not _catalog.is_empty():
		return
	_register(_make_blue_apprentice())
	_register(_make_thorn_adept())
	_register(_make_mirror_mage())
	_register(_make_archmage_duel())
	_register(_make_eightfold_warden())


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


static func all_encounters_including_boss() -> Array:
	_build_catalog()
	var list := all_encounters()
	if _catalog.has("eightfold_warden"):
		list.append(_catalog["eightfold_warden"])
	return list


static func default_encounter() -> DmbDuelRuleset:
	return get_encounter(DEFAULT_ENCOUNTER_ID)


static func _loci(count: int) -> Array:
	return _LOCUS.slice(0, count)


static func _make_blue_apprentice() -> DmbDuelRuleset:
	return DmbDuelRuleset.new(
		"blue_apprentice", "Blue Apprentice",
		"First tutorial — one locus, three essences.",
		1, _loci(1), [0, 1, 2], [0, 1, 2], 4,
		"Blue Apprentice", "blue_wizard",
		"Blue robes and a hesitant wand grip.", "easy",
		false, 8.0, 24.0, 0, 0.0, {}, {}, {"suppress_auto_cast_warnings": true}
	)


static func _make_thorn_adept() -> DmbDuelRuleset:
	return DmbDuelRuleset.new(
		"thorn_adept", "Thorn Adept",
		"Nature magic — two loci, thorny wards.",
		2, _loci(2), [0, 1, 6, 3], [0, 1, 6, 3], 6,
		"Thorn Adept", "thorn_druid",
		"Thorns and bark woven into their robes.", "normal",
		false, 5.0, 16.0
	)


static func _make_mirror_mage() -> DmbDuelRuleset:
	return DmbDuelRuleset.new(
		"mirror_mage", "Mirror Mage",
		"Reflected power — three loci, repeats allowed.",
		3, _loci(3), [4, 5, 1, 2, 9], [4, 5, 1, 2, 9], 8,
		"Mirror Mage", "mirror_mage",
		"Mirrored robes that shimmer with duplicate spells.", "hard",
		true, 5.0, 16.0
	)


static func _make_archmage_duel() -> DmbDuelRuleset:
	var all_magics: Array = []
	for i in range(DmbConstants.NUM_COLOURS):
		all_magics.append(i)
	return DmbDuelRuleset.new(
		"archmage_duel", "Archmage Duel",
		"The full wizard duel — four loci, ten essences.",
		DmbConstants.CODE_LENGTH, _loci(4), all_magics.duplicate(), all_magics.duplicate(),
		DmbConstants.MAX_GUESSES,
		"Archmage", "archmage",
		"Full duel rules — every essence, every locus.", "expert",
		true, 3.0, 10.0
	)


static func _make_eightfold_warden() -> DmbDuelRuleset:
	var all_magics: Array = []
	for i in range(DmbConstants.NUM_COLOURS):
		all_magics.append(i)
	return DmbDuelRuleset.new(
		"eightfold_warden", "The Eightfold Warden",
		"Boss duel — all eight loci.",
		8, _loci(8), all_magics.duplicate(), all_magics.duplicate(), 18,
		"Eightfold Warden", "eightfold_warden",
		"Eight runes orbit an unstable barrier.", "expert",
		true, 2.0, 8.0, 1, 20.0
	)
