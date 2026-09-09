class_name DmbInfection
extends RefCounted
## Pandemic infection core on the hex board.
##
## * One infection card per hex; deck cycles: discard is reshuffled onto the
##   top of the deck after an epidemic (Pandemic "intensify").
## * 0–3 demons per hex. Adding to a hex at 3 triggers an outbreak: every
##   neighbouring hex gains 1. Chain outbreaks never re-hit a hex that already
##   outbroke this step.
## * Epidemic chance rises each quiet step and resets when one fires. An
##   epidemic draws the bottom card, sets that hex to 3, raises the infection
##   rate and intensifies the deck.
##
## No event deck, no cures, no research stations, no roles yet.

const BASE_EPIDEMIC_CHANCE := 0.05
const EPIDEMIC_CHANCE_STEP := 0.04
const MAX_INFECTION_RATE := 4
const MAX_DEMONS := 3

var board: DmbHexBoard
var deck: Array = []
var discard: Array = []
var outbreaks: int = 0
var epidemics: int = 0
var infection_rate: int = 2
var epidemic_chance: float = BASE_EPIDEMIC_CHANCE
var rng := RandomNumberGenerator.new()


func _init(p_board: DmbHexBoard = null, seed: int = 0) -> void:
	board = p_board
	rng.seed = seed
	if board != null:
		deck = range(board.hexes.size())
		DmbHexBoard._shuffle(deck, rng)


# --- queries ----------------------------------------------------------------

func total_demons() -> int:
	var t := 0
	for h in board.hexes:
		t += h["demons"]
	return t


func infected_hexes() -> Array:
	var out := []
	for h in board.hexes:
		if h["demons"] > 0:
			out.append(h["id"])
	return out


# --- placement --------------------------------------------------------------

## Pandemic setup: 3 hexes at 3, 3 at 2, 3 at 1.
func initial_infection() -> Array:
	var log := []
	for level in [3, 2, 1]:
		for i in range(3):
			var hid := _draw()
			board.hexes[hid]["demons"] = level
			log.append({"type": "seed", "hex": hid, "demons": level})
	return log


## Add `n` demons to a hex, outbreaking as needed. Returns the hexes that
## outbroke (in order).
func infect(hid: int, n: int = 1) -> Array:
	var outbroke := []
	_infect_inner(hid, n, {}, outbroke)
	return outbroke


func _infect_inner(hid: int, n: int, protected: Dictionary, outbroke: Array) -> void:
	for i in range(n):
		if protected.has(hid):
			return
		var h: Dictionary = board.hexes[hid]
		if h["demons"] < MAX_DEMONS:
			h["demons"] += 1
			continue
		# Outbreak.
		outbreaks += 1
		protected[hid] = true
		outbroke.append(hid)
		for nb in board.hex_neighbors(hid):
			_infect_inner(nb, 1, protected, outbroke)
		return


func treat(hid: int) -> int:
	var h: Dictionary = board.hexes[hid]
	if h["demons"] <= 0:
		return 0
	h["demons"] -= 1
	return 1


# --- turn step --------------------------------------------------------------

## One infection step. Returns a log of {type, hex, ...} entries.
func infect_step() -> Array:
	var log := []
	if rng.randf() < epidemic_chance:
		epidemics += 1
		infection_rate = mini(MAX_INFECTION_RATE, infection_rate + (1 if epidemics % 2 == 0 else 0))
		epidemic_chance = BASE_EPIDEMIC_CHANCE
		var hid := _draw_bottom()
		var before: int = board.hexes[hid]["demons"]
		var outbroke := infect(hid, MAX_DEMONS - before)
		if before >= MAX_DEMONS:
			outbroke = infect(hid, 1)
		log.append({"type": "epidemic", "hex": hid, "outbroke": outbroke})
		_intensify()
	else:
		epidemic_chance += EPIDEMIC_CHANCE_STEP
	for i in range(infection_rate):
		var hid := _draw()
		var outbroke := infect(hid, 1)
		log.append({"type": "infect", "hex": hid, "outbroke": outbroke})
	return log


func _draw() -> int:
	if deck.is_empty():
		deck = discard
		discard = []
		DmbHexBoard._shuffle(deck, rng)
	var hid: int = deck.pop_back()
	discard.append(hid)
	return hid


func _draw_bottom() -> int:
	if deck.is_empty():
		return _draw()
	var hid: int = deck.pop_front()
	discard.append(hid)
	return hid


func _intensify() -> void:
	DmbHexBoard._shuffle(discard, rng)
	deck.append_array(discard)
	discard = []


# --- serialisation ----------------------------------------------------------

func to_dict() -> Dictionary:
	return {
		"deck": deck.duplicate(), "discard": discard.duplicate(),
		"outbreaks": outbreaks, "epidemics": epidemics,
		"infection_rate": infection_rate, "epidemic_chance": epidemic_chance,
		"rng": rng.state,
	}


static func from_dict(d: Dictionary, p_board: DmbHexBoard) -> DmbInfection:
	var inf := DmbInfection.new(p_board, 0)
	inf.deck = []
	for v in d.get("deck", []):
		inf.deck.append(int(v))
	inf.discard = []
	for v in d.get("discard", []):
		inf.discard.append(int(v))
	inf.outbreaks = int(d.get("outbreaks", 0))
	inf.epidemics = int(d.get("epidemics", 0))
	inf.infection_rate = int(d.get("infection_rate", 2))
	inf.epidemic_chance = float(d.get("epidemic_chance", BASE_EPIDEMIC_CHANCE))
	inf.rng.state = int(d.get("rng", 0))
	return inf
