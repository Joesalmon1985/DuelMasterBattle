class_name DmbColourData
extends RefCounted

## Presentation data for essences (magic ids 0-9) and loci.

const ESSENCE_NAMES := [
	"Flame", "Frost", "Storm", "Stone", "Light",
	"Shadow", "Vine", "Metal", "Spirit", "Arcane",
]

const NAMES := ESSENCE_NAMES

const SYMBOLS := [
	"Fr", "Fs", "St", "Sn", "Li",
	"Sh", "Vi", "Me", "Sp", "Ar",
]

const LOCUS_NAMES := [
	"Roach", "Uzag", "Lieana", "Gyse", "Vorr", "Mael", "Oshen", "Keth",
]

const POINT_NAMES := ["Roach", "Uzag", "Lieana", "Gyse"]

const FEEDBACK_FRACTURE := "Fracture"
const FEEDBACK_ECHO := "Echo"
const FEEDBACK_FADE := "Fade"

const COLOURS := [
	Color("#e6194b"), Color("#4fc3f7"), Color("#9e9e9e"), Color("#795548"), Color("#fff176"),
	Color("#424242"), Color("#66bb6a"), Color("#b0bec5"), Color("#ce93d8"), Color("#7e57c2"),
]


static func locus_name(index: int) -> String:
	if index >= 0 and index < LOCUS_NAMES.size():
		return LOCUS_NAMES[index]
	return "Locus %d" % (index + 1)


static func essence_name(id: int) -> String:
	if id >= 0 and id < ESSENCE_NAMES.size():
		return ESSENCE_NAMES[id]
	return "?"
