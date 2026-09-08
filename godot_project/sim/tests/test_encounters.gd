extends DmbTestCase

func run() -> void:
	var all := DmbEncounters.all_encounters()
	assert_eq(all.size(), 4, "four legacy encounters")
	assert_eq(DmbEncounters.playable_encounters().size(), 1, "one playable encounter for MVP")
	assert_eq(DmbEncounters.default_encounter().id, "core_duel", "core duel default")
	var arch := DmbEncounters.get_encounter("archmage_duel")
	assert_eq(arch.slot_count, DmbConstants.CODE_LENGTH, "archmage slots")
	assert_eq(arch.secret_magic_pool.size(), DmbConstants.NUM_COLOURS, "archmage secret pool")
	assert_eq(arch.attack_magic_pool.size(), DmbConstants.NUM_COLOURS, "archmage attack pool")
	assert_eq(arch.effective_max_attacks(), DmbConstants.MAX_GUESSES, "archmage max attacks")
	assert_eq(arch.enemy_difficulty, "expert", "archmage difficulty")
	var blue := DmbEncounters.get_encounter("blue_apprentice")
	assert_eq(blue.slot_count, 1, "blue apprentice one slot")
	assert_eq(blue.attack_magic_pool.size(), 3, "blue attack pool size")
	assert_eq(blue.allow_repeats, false, "blue apprentice no repeats")
