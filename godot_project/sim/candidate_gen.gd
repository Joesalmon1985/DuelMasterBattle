class_name DmbCandidateGen
extends RefCounted


static func opening_guess_for_ruleset(ruleset: DmbDuelRuleset) -> Array:
	var pool: Array = ruleset.attack_magic_pool
	if pool.is_empty():
		return []
	var a := int(pool[0])
	var b := int(pool[1]) if pool.size() > 1 else a
	var pattern: Array = [a, a, b, b]
	return pattern.slice(0, ruleset.slot_count)


static func generate_candidate_codes(ruleset: DmbDuelRuleset) -> Array:
	if ruleset.allow_repeats:
		return _generate_with_repeats(ruleset.attack_magic_pool, ruleset.slot_count)
	return _generate_permutations(ruleset.attack_magic_pool, ruleset.slot_count)


static func candidate_count_for_ruleset(ruleset: DmbDuelRuleset) -> int:
	return generate_candidate_codes(ruleset).size()


static func _generate_with_repeats(pool: Array, slot_count: int) -> Array:
	var codes: Array = [[]]
	for _s in range(slot_count):
		var next: Array = []
		for code in codes:
			for colour in pool:
				var c: Array = code.duplicate()
				c.append(int(colour))
				next.append(c)
		codes = next
	return codes


static func _generate_permutations(pool: Array, slot_count: int) -> Array:
	var result: Array = []
	_permute_helper(pool, slot_count, [], result)
	return result


static func _permute_helper(pool: Array, remaining: int, current: Array, out: Array) -> void:
	if remaining == 0:
		out.append(current.duplicate())
		return
	for i in range(pool.size()):
		var colour := int(pool[i])
		if colour in current:
			continue
		var next: Array = current.duplicate()
		next.append(colour)
		var rest: Array = []
		for j in range(pool.size()):
			if j != i:
				rest.append(pool[j])
		_permute_helper(rest, remaining - 1, next, out)
