class_name DmbAutoCast
extends RefCounted


static func fill_pattern(
	partial: Array,
	locus_count: int,
	attack_pool: Array,
	allow_repeats: bool,
	rng: RandomNumberGenerator
) -> Array:
	var result: Array = []
	for i in range(locus_count):
		if i < partial.size() and partial[i] != null:
			result.append(int(partial[i]))
		else:
			result.append(_pick_essence(result, attack_pool, allow_repeats, rng))
	return result


static func random_pattern(
	locus_count: int,
	attack_pool: Array,
	allow_repeats: bool,
	rng: RandomNumberGenerator
) -> Array:
	return fill_pattern([], locus_count, attack_pool, allow_repeats, rng)


static func _pick_essence(
	existing: Array,
	attack_pool: Array,
	allow_repeats: bool,
	rng: RandomNumberGenerator
) -> int:
	if attack_pool.is_empty():
		return 0
	if allow_repeats:
		return int(attack_pool[rng.randi_range(0, attack_pool.size() - 1)])
	var available: Array = []
	for e in attack_pool:
		var id := int(e)
		if not existing.has(id):
			available.append(id)
	if available.is_empty():
		return int(attack_pool[rng.randi_range(0, attack_pool.size() - 1)])
	return int(available[rng.randi_range(0, available.size() - 1)])
