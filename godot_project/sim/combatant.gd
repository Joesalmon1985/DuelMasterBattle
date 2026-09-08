class_name DmbCombatant
extends RefCounted

## One side of a battle: what they can attack with, what protects them, how many
## simultaneous spell attempts (weave slots) they hold, and how they think.
##
## Attack magic and Ward magic are deliberately separate: a Flame creature may only
## cast RED while hiding behind a BLUE Ward.

var id: String = ""
var display_name: String = ""
var archetype: String = ""          # art key (see client/scripts/art.gd)
var kind: String = "wizard"         # "player" | "creature" | "wizard"
var description: String = ""

var weave_size: int = 4             # simultaneous spell attempts per cast
var attack_pool: Array = []         # spells this side may cast
var ward_size: int = 4              # loci in this side's Ward
var ward_pool: Array = []           # spells this side may hide behind
var allow_repeats: bool = true
var fixed_ward: Array = []          # non-empty → always this Ward (tutorial creatures)

var max_casts: int = 10
var min_cast_seconds: float = 5.0
var max_cast_seconds: float = 60.0

# AI (ignored for the human)
var bot_logic: String = "candidate_filter"   # "candidate_filter" | "capped_minimax" | "random"
var bot_solver_cap: int = 60
var bot_mistake_rate: float = 0.0
var think_min_seconds: float = 14.0
var think_max_seconds: float = 26.0


static func make(data: Dictionary) -> DmbCombatant:
	var c := DmbCombatant.new()
	for k in data.keys():
		if k in c:
			c.set(k, data[k])
	if c.ward_pool.is_empty():
		c.ward_pool = c.attack_pool.duplicate()
	c.validate()
	return c


func duplicate_combatant() -> DmbCombatant:
	var c := DmbCombatant.new()
	for p in get_property_list():
		if p["usage"] & PROPERTY_USAGE_SCRIPT_VARIABLE:
			var v = get(p["name"])
			c.set(p["name"], v.duplicate() if v is Array else v)
	return c


func validate() -> void:
	assert(weave_size >= 1 and weave_size <= 8, "weave_size 1-8")
	assert(ward_size >= 1 and ward_size <= 8, "ward_size 1-8")
	assert(not attack_pool.is_empty(), "attack_pool required")
	assert(not ward_pool.is_empty(), "ward_pool required")
	if not allow_repeats:
		assert(ward_pool.size() >= ward_size, "ward_pool too small for no-repeat ward")
	if not fixed_ward.is_empty():
		assert(fixed_ward.size() == ward_size, "fixed_ward must match ward_size")


func to_dict() -> Dictionary:
	var d := {}
	for p in get_property_list():
		if p["usage"] & PROPERTY_USAGE_SCRIPT_VARIABLE:
			d[p["name"]] = get(p["name"])
	return d
