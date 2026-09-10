extends RefCounted
class_name DmbItems
## Quest/puzzle item catalogue. Deliberately small: the inventory holds at most
## eight of these and none of them are equipment. Ids are stable save keys.
## Generated items (dungeon sigils, cure fragments) are described by pattern so
## the catalogue never needs an entry per dungeon.

const MAX_SLOTS := 8

const DATA := {
	"iron_key": {"name": "Iron key", "sprite": "ring", "desc": "Heavy, old, and cut for a lock that expects to be respected."},
	"brass_gear": {"name": "Brass gear", "sprite": "ring", "desc": "One tooth short of a full set. Somewhere a machine is missing this."},
	"clay_idol": {"name": "Clay idol", "sprite": "idol", "desc": "A squat little figure. Its face has been rubbed smooth by thumbs."},
	"grey_stone": {"name": "Grey stone", "sprite": "rock", "desc": "Fist-sized. Exactly as heavy as it needs to be."},
	"tallow_candle": {"name": "Tallow candle", "sprite": "fire_0", "desc": "Smells of sheep. Burns long enough to matter."},
	"mirror_shard": {"name": "Mirror shard", "sprite": "mirror", "desc": "Shows the room, mostly. Shows something else at the edges."},
	"jane_letter": {"name": "Jane's letter", "sprite": "book_black", "desc": "'Whoever finds this: the tower on the ridge was never empty. — J.'"},
	"black_seed": {"name": "Black seed", "sprite": "seed", "desc": "Warm to the touch. Nothing that grows should be warm."},
	"cure_note": {"name": "Physician's note", "sprite": "book_red", "desc": "Half a recipe against the sickness in the ground. The other half is elsewhere."},
}


static func known(id: String) -> bool:
	return DATA.has(id) or id.begins_with("sigil_") or id.begins_with("cure_fragment_") or id.begins_with("token_")


static func name_of(id: String) -> String:
	if DATA.has(id):
		return str(DATA[id]["name"])
	if id.begins_with("sigil_"):
		return "Sigil of %s" % id.substr(6).capitalize()
	if id.begins_with("cure_fragment_"):
		return "Cure fragment %s" % id.substr(14)
	if id.begins_with("token_"):
		return "%s token" % id.substr(6).capitalize()
	return id.capitalize()


static func sprite_of(id: String) -> String:
	if DATA.has(id):
		return str(DATA[id]["sprite"])
	if id.begins_with("sigil_"):
		return "diamond"
	if id.begins_with("cure_fragment_"):
		return "book_red"
	return "box"


static func describe(id: String) -> String:
	if DATA.has(id):
		return str(DATA[id]["desc"])
	if id.begins_with("sigil_"):
		return "A carved sigil taken from a tower's heart. Another tower will ask for it."
	if id.begins_with("cure_fragment_"):
		return "Part of an answer to the sickness in the ground. It wants the other parts."
	if id.begins_with("token_"):
		return "A settlement's mark of thanks. Some doors recognise it."
	return "You are not sure what this is for. Yet."
