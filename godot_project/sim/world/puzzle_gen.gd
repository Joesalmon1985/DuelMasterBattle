extends RefCounted
class_name DmbPuzzleGen
## Generates a dungeon's four puzzles from the reusable catalogue vocabulary.
## Every template is a small data record that DmbPuzzleLogic knows how to drive
## and DmbDungeonMap knows how to lay out; adding a template means adding one
## entry here, one branch in the logic, and one room dressing in the map.
##
## Catalogue mapping: offerings (01 The Four Offerings / 20 Missing Gear / 27
## Replace the Burnt Fuse), exchange (17 Fair Exchange / 23 Take One Leave One),
## switch_chain (08 Secret Switch Chain / 41 Sound Sequence), plate_hold (21
## Hold the Plate with an Object), timed_gate (06 Timed Gate Run), mosaic (12
## Mosaic Floor / 03 The Serpent Path), magic_target (37 Water Changes the Room /
## 38 Fire Creates the Route / 36 Stone Jams the Machine), two_levers (14 Left
## Lever / Right Lever + 16 The Lying Guide, wrong answer summons a fight).

const TEMPLATES := ["offerings", "exchange", "switch_chain", "plate_hold", "timed_gate", "mosaic", "magic_target", "two_levers"]
const LOCAL_ITEMS := ["clay_idol", "brass_gear", "tallow_candle", "mirror_shard", "black_seed"]
## Spells every player holds on entering the world (Water, Vine, Fire).
const WORLD_SPELLS := [1, 6, 0]
const SPELL_TARGETS := {
	1: ["a brazier roaring far too hot for the room", "Douse it", "The fire dies with a hiss. Behind the smoke, the way is open."],
	6: ["a chasm too wide to jump", "Bridge it with Vine", "Roots knot across the gap and hold. Mostly."],
	0: ["a wall of old ice", "Melt it", "The ice runs to water and the water runs away. Cold stone, and a door."],
}


static func generate(d: Dictionary) -> Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = int(d["seed"])
	var pool := TEMPLATES.duplicate()
	pool.erase("offerings")
	var picks: Array = []
	for i in range(3):
		var t: String = pool[rng.randi_range(0, pool.size() - 1)]
		pool.erase(t)
		picks.append(t)
	# The dependency room is always an offerings puzzle keyed on the imported item.
	var dep_pos := rng.randi_range(1, 3)
	picks.insert(dep_pos, "offerings")
	var out: Array = []
	for i in range(4):
		out.append(_make(picks[i], "p%d" % (i + 1), rng, d if picks[i] == "offerings" else {}, i))
	return out


static func _make(type: String, pid: String, rng: RandomNumberGenerator, dep: Dictionary, room: int) -> Dictionary:
	var p := {"id": pid, "type": type, "room": room}
	match type:
		"offerings":
			var local: String = LOCAL_ITEMS[rng.randi_range(0, LOCAL_ITEMS.size() - 1)]
			var need := str(dep["needs"]["item"])
			p["title"] = "The Two Offerings"
			# The imported item is *shown* to the niche and kept (several dungeons
			# may depend on the same source — consuming it could block the network).
			p["slots"] = [{"id": pid + "_s0", "item": local}, {"id": pid + "_s1", "item": need, "keep": true}]
			p["items"] = [local]
			p["clue"] = "Two niches, two shapes cut into the stone. One shape is in this room. The other was made somewhere else — %s." % _source_hint(dep)
		"exchange":
			var fodder: String = LOCAL_ITEMS[rng.randi_range(0, LOCAL_ITEMS.size() - 1)]
			p["title"] = "Fair Exchange"
			p["pedestal"] = pid + "_ped"
			p["gives"] = "iron_key"
			p["accepts"] = LOCAL_ITEMS.duplicate()
			p["items"] = [fodder]
			p["clue"] = "The key sits on a plate that hums. Lift it and the door seals. Something else of weight must take its place."
		"switch_chain":
			var n := 3
			var order: Array = [0, 1, 2]
			_shuffle(order, rng)
			p["title"] = "The Switch Chain"
			p["levers"] = [pid + "_l0", pid + "_l1", pid + "_l2"]
			p["order"] = order
			p["clue"] = "Three levers. Scratched beside them: '%s'. A wrong pull resets them all." % _order_words(order)
			p["n"] = n
		"plate_hold":
			p["title"] = "Hold the Plate"
			p["plate"] = pid + "_plate"
			p["items"] = ["grey_stone"]
			p["clue"] = "A plate in the floor. Stand on it and the door grinds open; step off and it slams. Something has to stay behind."
		"timed_gate":
			p["title"] = "The Timed Gate"
			p["lever"] = pid + "_lever"
			p["steps"] = 9
			p["clue"] = "Pull the lever and the gate lifts — and counts. Nine steps, no more. Then it drops."
		"mosaic":
			var order: Array = [0, 1, 2, 3]
			_shuffle(order, rng)
			p["title"] = "The Mosaic Floor"
			p["tiles"] = 4
			p["order"] = order
			p["clue"] = "Four coloured stones set in the floor. The mural says: %s. Tread them so, or start again." % _order_words(order)
		"magic_target":
			var spell: int = WORLD_SPELLS[rng.randi_range(0, WORLD_SPELLS.size() - 1)]
			var t: Array = SPELL_TARGETS[spell]
			p["title"] = "The Room Answers Magic"
			p["target"] = pid + "_target"
			p["spell"] = spell
			p["desc"] = t[0]
			p["prompt"] = t[1]
			p["result"] = t[2]
			p["clue"] = "The way on is blocked by %s. No lever. No key. This room wants a wizard." % t[0]
		"two_levers":
			p["title"] = "Left Lever, Right Lever"
			p["levers"] = [pid + "_left", pid + "_right"]
			p["correct"] = rng.randi_range(0, 1)
			var liar := rng.randi_range(0, 1) == 0
			var said: int = p["correct"] if not liar else 1 - int(p["correct"])
			p["liar"] = liar
			p["clue"] = "A carved face says: 'Pull the %s.' Beneath it, in another hand: '%s'" % [
				"left" if said == 0 else "right", "The face lies." if liar else "The face is honest, for once."]
			p["wrong_enemy"] = "flame_imp"
	return p


static func _source_hint(dep: Dictionary) -> String:
	var need: Dictionary = dep["needs"]
	if str(need["from"]) == "settlement":
		return "the people of the steading that raised this place carry such marks"
	return "carved in the heart of the %s" % str(need["from"]).replace("_", " ")


static func _order_words(order: Array) -> String:
	const WORDS := ["first", "second", "third", "fourth"]
	var bits: Array = []
	for i in order:
		bits.append(WORDS[int(i)])
	return ", then ".join(PackedStringArray(bits))


static func _shuffle(a: Array, rng: RandomNumberGenerator) -> void:
	for i in range(a.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var t = a[i]
		a[i] = a[j]
		a[j] = t
