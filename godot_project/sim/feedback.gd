class_name DmbFeedback
extends RefCounted


static func score_guess(secret: Array, guess: Array) -> Vector2i:
	assert(secret.size() == guess.size(), "secret and guess must have equal length")
	DmbCode.validate_code_length(secret, secret.size())
	DmbCode.validate_code_length(guess, guess.size())
	var exact := 0
	var secret_remaining: Array = []
	var guess_remaining: Array = []
	for i in range(secret.size()):
		if int(secret[i]) == int(guess[i]):
			exact += 1
		else:
			secret_remaining.append(int(secret[i]))
			guess_remaining.append(int(guess[i]))
	var counts: Dictionary = {}
	for s in secret_remaining:
		counts[s] = counts.get(s, 0) + 1
	var colour_only := 0
	for g in guess_remaining:
		if counts.get(g, 0) > 0:
			colour_only += 1
			counts[g] -= 1
	return Vector2i(exact, colour_only)
