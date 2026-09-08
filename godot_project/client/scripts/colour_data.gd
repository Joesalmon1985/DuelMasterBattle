class_name DmbColourData
extends RefCounted

## Presentation data for essences (spell ids 0-9) and loci.
## Colours here must match tools/generate_essence_icons.py.

const ESSENCE_NAMES := [
	"Flame", "Frost", "Storm", "Stone", "Light",
	"Shadow", "Vine", "Metal", "Spirit", "Arcane",
]

const NAMES := ESSENCE_NAMES

## Short symbol shown alongside colour (accessibility).
const SYMBOLS := [
	"▲", "❄", "⚡", "■", "☀",
	"☾", "●", "⬢", "♦", "★",
]

## Plain-word shape names for hints/tooltips.
const SHAPE_NAMES := [
	"triangle", "snowflake", "bolt", "square", "sun",
	"moon", "leaf", "hexagon", "drop", "star",
]

const LOCUS_NAMES := [
	"Roach", "Uzag", "Lieana", "Gyse", "Vorr", "Mael", "Oshen", "Keth",
]

const POINT_NAMES := ["Roach", "Uzag", "Lieana", "Gyse"]

const FEEDBACK_FRACTURE := "Fracture"
const FEEDBACK_ECHO := "Echo"
const FEEDBACK_FADE := "Fade"

const COLOURS := [
	Color("#e84545"), Color("#3fa9f5"), Color("#8fa3b8"), Color("#e08a2e"), Color("#f5d442"),
	Color("#5b4a7a"), Color("#3ecf6a"), Color("#b8c4cc"), Color("#f2a2d9"), Color("#9b5de5"),
]


static func locus_name(index: int) -> String:
	if index >= 0 and index < LOCUS_NAMES.size():
		return LOCUS_NAMES[index]
	return "Locus %d" % (index + 1)


static func essence_name(id: int) -> String:
	if id >= 0 and id < ESSENCE_NAMES.size():
		return ESSENCE_NAMES[id]
	return "?"


static func essence_colour(id: int) -> Color:
	if id >= 0 and id < COLOURS.size():
		return COLOURS[id]
	return Color.GRAY


static func essence_symbol(id: int) -> String:
	if id >= 0 and id < SYMBOLS.size():
		return SYMBOLS[id]
	return "?"
