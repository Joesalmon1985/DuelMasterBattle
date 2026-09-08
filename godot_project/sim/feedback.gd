class_name DmbFeedback
extends RefCounted

## Mastermind-style aggregate scoring.
##
## score_guess(secret, guess)  — classic equal-length scoring (Vector2i exact, colour_only).
## score_attack(ward, attack)  — generalised for unequal weave sizes:
##   attack slot j targets ward slot (j mod ward.size()), left-to-right, wrapping.
##   Returns {"fracture", "echo", "fade", "broken", "targets"}.
##   * fracture: attack[j] == ward[target(j)]
##   * echo:     not a fracture, but the spell exists in a ward slot that no attempt
##               fractured (multiset match, each ward slot counted once)
##   * fade:     everything else
##   * broken:   every ward slot received at least one fracturing attempt
## With attack.size() < ward.size() some ward slots are never targeted, so the ward
## can never be broken — that is the intended cost of a smaller weave.


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


static func target_slot(attack_index: int, ward_size: int) -> int:
	return attack_index % maxi(ward_size, 1)


## Which attack indices address each ward slot: Array[Array[int]] sized ward_size.
static func targets_by_ward_slot(attack_size: int, ward_size: int) -> Array:
	var out: Array = []
	for _i in range(ward_size):
		out.append([])
	for j in range(attack_size):
		out[target_slot(j, ward_size)].append(j)
	return out


static func score_attack(ward: Array, attack: Array) -> Dictionary:
	var ws := ward.size()
	var fractured_slot: Array = []
	for _i in range(ws):
		fractured_slot.append(false)
	var fracture := 0
	var non_fracture_attempts: Array = []
	for j in range(attack.size()):
		var t := target_slot(j, ws)
		if ws > 0 and int(attack[j]) == int(ward[t]):
			fracture += 1
			fractured_slot[t] = true
		else:
			non_fracture_attempts.append(int(attack[j]))
	var counts: Dictionary = {}
	for i in range(ws):
		if not fractured_slot[i]:
			var s := int(ward[i])
			counts[s] = counts.get(s, 0) + 1
	var echo := 0
	for g in non_fracture_attempts:
		if counts.get(g, 0) > 0:
			echo += 1
			counts[g] -= 1
	var broken := ws > 0
	for i in range(ws):
		if not fractured_slot[i]:
			broken = false
	return {
		"fracture": fracture,
		"echo": echo,
		"fade": attack.size() - fracture - echo,
		"broken": broken,
		"targets": targets_by_ward_slot(attack.size(), ws),
	}


static func same_result(a: Dictionary, b: Dictionary) -> bool:
	return int(a["fracture"]) == int(b["fracture"]) and int(a["echo"]) == int(b["echo"])
