class_name DmbColourData
extends RefCounted

## Wizard-duel presentation for the 10 Mastermind colour ids (0-9).
## Rules remain mechanically identical; only labels/colours change.

const NAMES := [
	"Flame", "Frost", "Storm", "Stone", "Light",
	"Shadow", "Vine", "Metal", "Spirit", "Arcane",
]

const SYMBOLS := [
	"Fr", "Fs", "St", "Sn", "Li",
	"Sh", "Vi", "Me", "Sp", "Ar",
]

const POINT_NAMES := [
	"Shield", "Body", "Staff", "Mind",
]

const COLOURS := [
	Color("#e6194b"), Color("#4fc3f7"), Color("#9e9e9e"), Color("#795548"), Color("#fff176"),
	Color("#424242"), Color("#66bb6a"), Color("#b0bec5"), Color("#ce93d8"), Color("#7e57c2"),
]
