extends DmbTestCase

func run() -> void:
	var all := DmbEncounters.all_encounters()
	assert_eq(all.size(), 4, "four built-in encounters")
	var arch := DmbEncounters.get_encounter("archmage_duel")
	assert_eq(arch.slot_count, DmbConstants.CODE_LENGTH, "archmage slots")
	assert_eq(arch.secret_magic_pool.size(), DmbConstants.NUM_COLOURS, "archmage secret pool")
	assert_eq(arch.attack_magic_pool.size(), DmbConstants.NUM_COLOURS, "archmage attack pool")
	assert_eq(arch.effective_max_attacks(), DmbConstants.MAX_GUESSES, "archmage max attacks")
	assert_eq(arch.enemy_difficulty, "expert", "archmage difficulty")
	var blue := DmbEncounters.get_encounter("blue_apprentice")
	assert_eq(blue.slot_count, 1, "blue apprentice one slot")
	assert_eq(blue.attack_magic_pool.size(), 4, "blue attack pool size")
