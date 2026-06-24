extends DmbTestCase

func run() -> void:
	var fb := DmbFeedback.score_guess([0, 1, 2, 3], [0, 1, 2, 3])
	assert_eq(fb, Vector2i(4, 0), "all exact")
	fb = DmbFeedback.score_guess([0, 0, 1, 2], [0, 1, 0, 3])
	assert_eq(fb, Vector2i(1, 2), "mixed")
	fb = DmbFeedback.score_guess([0, 0, 1, 2], [0, 0, 0, 0])
	assert_eq(fb, Vector2i(2, 0), "duplicate exact")
