extends DmbTestCase

func run() -> void:
	assert_true(DmbConstants.CODE_LENGTH == 4)
	assert_true(DmbConstants.NUM_COLOURS == 10)
	assert_true(DmbConstants.MAX_GUESSES == 12)
	assert_true(DmbCode.is_valid_code([0, 1, 2, 3]))
	assert_true(not DmbCode.is_valid_code([0, 1, 2]))
	assert_true(not DmbCode.is_valid_code([-1, 0, 1, 2]))
	var blue := DmbEncounters.get_encounter("blue_apprentice")
	assert_true(DmbCode.is_valid_code_for_ruleset([1], blue, blue.secret_magic_pool))
	assert_true(not DmbCode.is_valid_code_for_ruleset([0], blue, blue.secret_magic_pool))
