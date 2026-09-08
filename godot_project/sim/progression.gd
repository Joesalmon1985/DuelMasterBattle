class_name DmbProgression
extends RefCounted

## John's magical state: spells known and weave capacity, kept separate so future
## content can grow them independently. Also produces his DmbCombatant.

const PLAYER_MAX_CASTS := 10

var spells_known: Array = []        # ordered by acquisition
var weave_size: int = 0


func has_magic() -> bool:
	return not spells_known.is_empty() and weave_size > 0


func learn_spell(spell_id: int) -> bool:
	if spell_id in spells_known:
		return false
	spells_known.append(spell_id)
	return true


func knows(spell_id: int) -> bool:
	return spell_id in spells_known


func grow_weave(to_size: int) -> bool:
	if to_size <= weave_size:
		return false
	weave_size = to_size
	return true


## John's Ward is the same size as his weave — his capacity is one number.
func ward_size() -> int:
	return weave_size


func to_combatant() -> DmbCombatant:
	assert(has_magic(), "John has no magic yet")
	return DmbCombatant.make({
		"id": "john", "display_name": "John", "archetype": "john", "kind": "player",
		"weave_size": weave_size, "attack_pool": spells_known.duplicate(),
		"ward_size": weave_size, "ward_pool": spells_known.duplicate(),
		"allow_repeats": true, "max_casts": PLAYER_MAX_CASTS,
		"min_cast_seconds": DmbConstants.CORE_MIN_CAST_SECONDS,
		"max_cast_seconds": DmbConstants.CORE_MAX_CAST_SECONDS,
	})


func to_dict() -> Dictionary:
	return {"spells_known": spells_known.duplicate(), "weave_size": weave_size}


static func from_dict(d: Dictionary) -> DmbProgression:
	var p := DmbProgression.new()
	for s in d.get("spells_known", []):
		p.spells_known.append(int(s))
	p.weave_size = int(d.get("weave_size", 0))
	return p
