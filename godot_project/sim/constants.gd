class_name DmbConstants
extends RefCounted

## Global palette size: essences are ids 0..9. Encounters choose a subset.
const NUM_COLOURS := 10
const MIN_COLOUR := 0
const MAX_COLOUR := NUM_COLOURS - 1

## Legacy full-duel numbers (Archmage encounter, sequential prototype).
const CODE_LENGTH := 4
const MAX_GUESSES := 12

## Core duel (MVP) rules.
const CORE_SLOTS := 4
const CORE_MAX_CASTS := 10
const CORE_MIN_CAST_SECONDS := 5.0
const CORE_MAX_CAST_SECONDS := 60.0
## Flame, Frost, Stone, Light, Vine, Arcane — six visually distinct spells.
const CORE_SPELL_POOL := [0, 1, 3, 4, 6, 9]
