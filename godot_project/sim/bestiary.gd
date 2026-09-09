class_name DmbBestiary
extends RefCounted

## Data-driven catalogue of opponents for the adventure. Add an entry, reference
## its id from the world — no bespoke code per creature.
##
## Spell ids (colour_data.gd): 0 Flame(RED) 1 Frost(BLUE/Water) 3 Stone 6 Vine 4 Light 9 Arcane

const RED := 0
const BLUE := 1
const STONE := 3
const VINE := 6

static var _catalog: Dictionary = {}


static func _build() -> void:
	if not _catalog.is_empty():
		return
	# --- Tier 1: teaches the interface. Guaranteed win with BLUE x1. -----------
	_add({
		"id": "flame_wisp", "display_name": "Flame Wisp", "archetype": "flame_wisp", "kind": "creature",
		"description": "A scrap of living fire. It only knows RED, and hides behind a single Water Ward.",
		"weave_size": 1, "attack_pool": [RED], "ward_size": 1, "ward_pool": [BLUE], "fixed_ward": [BLUE],
		"max_casts": 10, "min_cast_seconds": 5.0, "max_cast_seconds": 60.0,
		"bot_logic": "random", "think_min_seconds": 12.0, "think_max_seconds": 20.0,
	})
	_add({
		"id": "flame_imp", "display_name": "Flame Imp", "archetype": "flame_imp", "kind": "creature",
		"description": "Bolder than a wisp. Its Ward may be Water or Fire — you must find out which.",
		"weave_size": 1, "attack_pool": [RED], "ward_size": 1, "ward_pool": [BLUE, RED],
		"max_casts": 10, "min_cast_seconds": 5.0, "max_cast_seconds": 60.0,
		"bot_logic": "random", "think_min_seconds": 10.0, "think_max_seconds": 18.0,
	})
	# --- Tier 2: Red + Blue, two weave slots. Real deduction begins. ------------
	_add({
		"id": "steam_sprite", "display_name": "Steam Sprite", "archetype": "steam_sprite", "kind": "creature",
		"description": "Born where fire met water. One Ward slot, but it could be either.",
		"weave_size": 1, "attack_pool": [RED, BLUE], "ward_size": 1, "ward_pool": [RED, BLUE],
		"max_casts": 10, "min_cast_seconds": 5.0, "max_cast_seconds": 60.0,
		"bot_logic": "candidate_filter", "think_min_seconds": 10.0, "think_max_seconds": 18.0,
	})
	_add({
		"id": "steam_brute", "display_name": "Steam Brute", "archetype": "steam_brute", "kind": "creature",
		"description": "A hulking cloud with a two-slot Ward of Fire and Water.",
		"weave_size": 2, "attack_pool": [RED, BLUE], "ward_size": 2, "ward_pool": [RED, BLUE],
		"max_casts": 10, "min_cast_seconds": 5.0, "max_cast_seconds": 60.0,
		"bot_logic": "candidate_filter", "think_min_seconds": 12.0, "think_max_seconds": 22.0,
	})
	# --- Tier 3: Stone joins. Three slots. -------------------------------------
	_add({
		"id": "cinder_golem", "display_name": "Cinder Golem", "archetype": "cinder_golem", "kind": "creature",
		"description": "Stone bound with embers. It throws Stone, but its two-slot Ward is only Fire and Water.",
		"weave_size": 2, "attack_pool": [RED, STONE], "ward_size": 2, "ward_pool": [RED, BLUE],
		"max_casts": 10, "min_cast_seconds": 5.0, "max_cast_seconds": 60.0,
		"bot_logic": "candidate_filter", "think_min_seconds": 14.0, "think_max_seconds": 24.0,
	})
	_add({
		"id": "moss_shade", "display_name": "Moss Shade", "archetype": "moss_shade", "kind": "creature",
		"description": "Something old that lives under the well. It weaves Vine, but wards with what it has drunk: Fire, Water, Stone.",
		"weave_size": 3, "attack_pool": [VINE, BLUE, STONE], "ward_size": 3, "ward_pool": [RED, BLUE, STONE],
		"max_casts": 10, "min_cast_seconds": 5.0, "max_cast_seconds": 60.0,
		"bot_logic": "candidate_filter", "think_min_seconds": 14.0, "think_max_seconds": 24.0,
	})
	# --- Wizards -----------------------------------------------------------------
	_add({
		"id": "hedge_wizard", "display_name": "Ashby the Hedge Wizard", "archetype": "pyroclast", "kind": "wizard",
		"description": "A village wizard of modest talent. Three slots; casts Fire and Stone, wards with anything.",
		"weave_size": 3, "attack_pool": [RED, STONE], "ward_size": 3, "ward_pool": [RED, STONE, BLUE],
		"max_casts": 10, "min_cast_seconds": 5.0, "max_cast_seconds": 60.0,
		"bot_logic": "candidate_filter", "think_min_seconds": 12.0, "think_max_seconds": 22.0,
	})
	_add({
		"id": "red_wizard", "display_name": "The Red Wizard", "archetype": "arcanist", "kind": "wizard",
		"description": "The one who burned the forest. Four slots; he commands every spell you know.",
		"weave_size": 4, "attack_pool": [RED, BLUE, STONE, VINE], "ward_size": 4, "ward_pool": [RED, BLUE, STONE, VINE],
		"max_casts": 10, "min_cast_seconds": 5.0, "max_cast_seconds": 60.0,
		"bot_logic": "capped_minimax", "bot_solver_cap": 40, "think_min_seconds": 12.0, "think_max_seconds": 22.0,
	})
	# P1: Ashby's teaching Wards + the Trial-road Giant Fly. ----------------------
	_add({
		"id": "ashby_lesson1", "display_name": "Ashby's Practice Ward", "archetype": "hedge_ward", "kind": "wizard",
		"description": "Ashby's teaching Ward: a single slot of Water. Cast what you hold.",
		"weave_size": 1, "attack_pool": [BLUE], "ward_size": 1, "ward_pool": [BLUE], "fixed_ward": [BLUE],
		"max_casts": 10, "min_cast_seconds": 5.0, "max_cast_seconds": 60.0,
		"bot_logic": "random", "think_min_seconds": 10.0, "think_max_seconds": 18.0,
	})
	_add({
		"id": "ashby_lesson2", "display_name": "Ashby's Hidden Ward", "archetype": "hedge_ward", "kind": "wizard",
		"description": "Ashby's second lesson: one Ward slot, Water or Fire. Find out which.",
		"weave_size": 1, "attack_pool": [BLUE], "ward_size": 1, "ward_pool": [BLUE, RED],
		"max_casts": 10, "min_cast_seconds": 5.0, "max_cast_seconds": 60.0,
		"bot_logic": "candidate_filter", "think_min_seconds": 10.0, "think_max_seconds": 18.0,
	})
	_add({
		"id": "giant_fly", "display_name": "Giant Fly", "archetype": "giant_fly", "kind": "creature",
		"description": "A horsefly the size of a hound. Fast, stupid, and easy to walk away from.",
		"weave_size": 1, "attack_pool": [RED], "ward_size": 1, "ward_pool": [BLUE], "fixed_ward": [BLUE],
		"max_casts": 10, "min_cast_seconds": 5.0, "max_cast_seconds": 60.0,
		"bot_logic": "random", "think_min_seconds": 10.0, "think_max_seconds": 18.0,
	})
	# Regression anchor: the MVP 4x6x10 duel expressed as a combatant.
	_add({
		"id": "rival_wizard", "display_name": "Rival Wizard", "archetype": "wizard", "kind": "wizard",
		"description": "Four loci, six spells, ten casts each.",
		"weave_size": 4, "attack_pool": DmbConstants.CORE_SPELL_POOL.duplicate(), "ward_size": 4,
		"ward_pool": DmbConstants.CORE_SPELL_POOL.duplicate(),
		"max_casts": 10, "min_cast_seconds": 5.0, "max_cast_seconds": 60.0,
		"bot_logic": "candidate_filter", "think_min_seconds": 16.0, "think_max_seconds": 30.0,
	})


static func _add(d: Dictionary) -> void:
	_catalog[d["id"]] = d


static func has(id: String) -> bool:
	_build()
	return _catalog.has(id)


static func get_data(id: String) -> Dictionary:
	_build()
	assert(_catalog.has(id), "unknown enemy: %s" % id)
	return _catalog[id].duplicate(true)


static func make(id: String) -> DmbCombatant:
	return DmbCombatant.make(get_data(id))


static func ids() -> Array:
	_build()
	return _catalog.keys()
