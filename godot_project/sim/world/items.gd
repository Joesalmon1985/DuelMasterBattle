extends RefCounted
class_name DmbItems
## Quest/puzzle item catalogue. Deliberately small: the inventory holds at most
## eight of these and none of them are equipment. Ids are stable save keys.
## Generated items (dungeon sigils, cure fragments) are described by pattern so
## the catalogue never needs an entry per dungeon.

const MAX_SLOTS := 8

const DATA := {
	"iron_key": {"name": "Iron key", "sprite": "ring", "desc": "Heavy, old, and cut for a lock that expects to be respected.", "tags": ["key","small"]},
	"brass_gear": {"name": "Brass gear", "sprite": "ring", "desc": "One tooth short of a full set. Somewhere a machine is missing this.", "tags": ["gear","small"]},
	"clay_idol": {"name": "Clay idol", "sprite": "idol", "desc": "A squat little figure. Its face has been rubbed smooth by thumbs.", "tags": ["heavy","idol"]},
	"grey_stone": {"name": "Grey stone", "sprite": "rock", "desc": "Fist-sized. Exactly as heavy as it needs to be.", "tags": ["heavy","throwable"]},
	"tallow_candle": {"name": "Tallow candle", "sprite": "fire_0", "desc": "Smells of sheep. Burns long enough to matter.", "tags": ["small","candle"]},
	"mirror_shard": {"name": "Mirror shard", "sprite": "mirror", "desc": "Shows the room, mostly. Shows something else at the edges.", "tags": ["small","mirror"]},
	"jane_letter": {"name": "Jane's letter", "sprite": "book_black", "desc": "'Whoever finds this: the tower on the ridge was never empty. — J.'", "tags": ["small","clue"]},
	"black_seed": {"name": "Black seed", "sprite": "seed", "desc": "Warm to the touch. Nothing that grows should be warm.", "tags": ["small","seed"]},
	"cure_note": {"name": "Physician's note", "sprite": "book_red", "desc": "Half a recipe against the sickness in the ground. The other half is elsewhere.", "tags": ["small","clue"]},
	# --- puzzle toolkit items (docs/Duel_Master_Battle_Puzzle_Catalogue.txt) ---
	"copper_coin": {"name": "Copper coin", "sprite": "ring", "desc": "Worn smooth. Worth nothing to a merchant; worth a wish to a fountain.", "tags": ["small", "token"]},
	"iron_weight": {"name": "Iron weight", "sprite": "rock", "desc": "A foundry weight with a ring on top. Heavy enough to hold a plate down.", "tags": ["heavy"]},
	"sandbag": {"name": "Sandbag", "sprite": "box", "desc": "Fat, damp, and about the weight of a man's leg.", "tags": ["heavy"]},
	"silver_key": {"name": "Silver key", "sprite": "ring", "desc": "Bright, sharp-cut, and clearly meant to be missed.", "tags": ["key", "small", "valuable"]},
	"bronze_key": {"name": "Bronze key", "sprite": "ring", "desc": "Dull and plain. Opens something, presumably.", "tags": ["key", "small"]},
	"old_fuse": {"name": "Copper fuse", "sprite": "ring", "desc": "A fat coil of copper in a clay sleeve. Not burnt — yet.", "tags": ["fuse", "small"]},
	"burnt_fuse": {"name": "Burnt fuse", "sprite": "ring", "desc": "Blackened through. Whatever this fed is dead.", "tags": ["small"]},
	"clouded_lens": {"name": "Clouded lens", "sprite": "mirror", "desc": "Milky glass in a brass ring. Everything through it is a blur — in daylight.", "tags": ["small", "lens"]},
	"tuning_fork": {"name": "Tuning fork", "sprite": "staff", "desc": "It hums faintly when you hold it near old stone.", "tags": ["small"]},
	"cold_candle": {"name": "Cold candle", "sprite": "fire_0", "desc": "Will not take a flame. Stubborn, or waiting.", "tags": ["small"]},
	"map_fragment": {"name": "Map fragment", "sprite": "book_black", "desc": "Torn. Surviving labels: '...ARCHIVE — north of the well. ARMOURY — the red door...'", "tags": ["small", "clue"]},
	"ledger_page": {"name": "Ledger page", "sprite": "book_red", "desc": "'Levers to be thrown in this order at shift end: THIRD, FIRST, SECOND. Do not deviate. — Foreman.'", "tags": ["small", "clue"]},
	"golden_idol": {"name": "Golden idol", "sprite": "idol", "desc": "Heavier than it looks, and it looks heavy.", "tags": ["heavy", "valuable"]},
	"lead_shot": {"name": "Bag of lead shot", "sprite": "box", "desc": "Small, dense, throwable. Lands where you point it.", "tags": ["heavy", "throwable"]},
	"raw_meat": {"name": "Raw meat", "sprite": "box", "desc": "A hank of something. Anything with a nose would follow it.", "tags": ["bait", "small"]},
	"glass_bead": {"name": "Glass bead", "sprite": "diamond", "desc": "Pretty, and worthless.", "tags": ["small", "token"]},
}


static func tags_of(id: String) -> Array:
	if DATA.has(id):
		return DATA[id].get("tags", [])
	if id.begins_with("token_"):
		return ["small", "token"]
	return []


## Placeholder colour for a puzzle item drawn as a block (see DmbPuzzleKit).
static func color_of(id: String) -> Color:
	var t := tags_of(id)
	if "key" in t:
		return Color(0.85, 0.85, 0.6)
	if "heavy" in t:
		return Color(0.45, 0.45, 0.5)
	if "bait" in t:
		return Color(0.8, 0.3, 0.3)
	if "fuse" in t:
		return Color(0.85, 0.5, 0.2)
	if "clue" in t:
		return Color(0.9, 0.85, 0.7)
	if "valuable" in t or "token" in t:
		return Color(0.95, 0.8, 0.2)
	return Color(0.6, 0.5, 0.8)


static func glyph_of(id: String) -> String:
	var t := tags_of(id)
	if "key" in t:
		return "⚷"
	if "heavy" in t:
		return "■"
	if "bait" in t:
		return "♨"
	if "clue" in t:
		return "≣"
	if "token" in t:
		return "○"
	return "◆"


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
