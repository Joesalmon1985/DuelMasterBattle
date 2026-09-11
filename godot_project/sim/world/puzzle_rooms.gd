extends RefCounted
class_name DmbPuzzleRooms
## The fifty catalogue puzzles (docs/Duel_Master_Battle_Puzzle_Catalogue.txt)
## as playable test rooms, each built from DmbPuzzleKit's generic vocabulary.
## No room has bespoke code: a room is a grid, a start tile, a starting
## inventory / spell list, and a list of data entities. Every room ends with a
## "goal" tile the player must physically reach; gates in the way are opened by
## the mechanic the catalogue names.
##
## Rooms are keyed "pz_NN". They are standalone: puzzle-test state lives under
## Adventure.puzzle_state("pz_NN") and the launcher never touches campaign saves.

const W := 13
const H := 11


static func ids() -> Array:
	var out: Array = []
	for r in all():
		out.append(str(r["id"]))
	return out


static func get_room(id: String) -> Dictionary:
	for r in all():
		if str(r["id"]) == id:
			return r
	return {}


static func all() -> Array:
	return [
		_r01(), _r02(), _r03(), _r04(), _r05(), _r06(), _r07(), _r08(), _r09(), _r10(),
		_r11(), _r12(), _r13(), _r14(), _r15(), _r16(), _r17(), _r18(), _r19(), _r20(),
		_r21(), _r22(), _r23(), _r24(), _r25(), _r26(), _r27(), _r28(), _r29(), _r30(),
		_r31(), _r32(), _r33(), _r34(), _r35(), _r36(), _r37(), _r38(), _r39(), _r40(),
		_r41(), _r42(), _r43(), _r44(), _r45(), _r46(), _r47(), _r48(), _r49(), _r50(),
	]


# --- grid helpers --------------------------------------------------------------------

static func _open(w: int = W, h: int = H) -> Array:
	var rows: Array = []
	for y in range(h):
		var line := ""
		for x in range(w):
			line += "#" if (x == 0 or y == 0 or x == w - 1 or y == h - 1) else "."
		rows.append(line)
	return rows


static func _fill(rows: Array, x0: int, y0: int, x1: int, y1: int, ch: String = "#") -> void:
	for y in range(y0, y1 + 1):
		var line: String = rows[y]
		for x in range(x0, x1 + 1):
			line = line.substr(0, x) + ch + line.substr(x + 1)
		rows[y] = line


static func _room(num: int, title: String, mech: String, rows: Array, start: Array, ents: Array, extra: Dictionary = {}) -> Dictionary:
	var r := {"id": "pz_%02d" % num, "num": num, "title": title, "mechanics": mech, "rows": rows, "start": start,
		"items": [], "spells": [], "entities": ents, "hint": ""}
	for k in extra:
		r[k] = extra[k]
	return r


static func _goal(x: int, y: int, req = null, text: String = "") -> Dictionary:
	var g := {"kind": "goal", "id": "goal", "pos": [x, y], "text": text if text != "" else "Through. The room has nothing more to ask."}
	if req != null:
		g["requires"] = req
	return g


static func _gate(id: String, x: int, y: int, open_when, look: String = "gate") -> Dictionary:
	return {"kind": "gate", "id": id, "pos": [x, y], "open_when": open_when, "look": look}


static func _plaque(id: String, x: int, y: int, text: String, extra: Dictionary = {}) -> Dictionary:
	var p := {"kind": "plaque", "id": id, "pos": [x, y], "text": text}
	for k in extra:
		p[k] = extra[k]
	return p


static func _item(id: String, item: String, x: int, y: int, extra: Dictionary = {}) -> Dictionary:
	var e := {"kind": "item", "id": id, "item": item, "pos": [x, y]}
	for k in extra:
		e[k] = extra[k]
	return e


static func _lever(id: String, x: int, y: int, flag: String, extra: Dictionary = {}) -> Dictionary:
	var e := {"kind": "lever", "id": id, "pos": [x, y], "flag": flag}
	for k in extra:
		e[k] = extra[k]
	return e


static func _plate(id: String, x: int, y: int, flag: String, accepts: Array = ["player", "item"], tags: Array = ["heavy"]) -> Dictionary:
	return {"kind": "plate", "id": id, "pos": [x, y], "flag": flag, "accepts": accepts, "item_tags": tags}


static func _marker(id: String, x: int, y: int, extra: Dictionary = {}) -> Dictionary:
	var e := {"kind": "marker", "id": id, "pos": [x, y]}
	for k in extra:
		e[k] = extra[k]
	return e


static func _pit(id: String, x: int, y: int, extra: Dictionary = {}) -> Dictionary:
	var e := {"kind": "pit", "id": id, "pos": [x, y]}
	for k in extra:
		e[k] = extra[k]
	return e


# =====================================================================================
# 01–10
# =====================================================================================

static func _r01() -> Dictionary:
	var rows := _open()
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var reject := "The alcove rejects the offering. That is not what the inscription describes."
	var install := "The stone accepts the offering. Something deep inside the wall clicks."
	var riddles := [
		["o1", 2, "mirror_shard", "I turn everything around, yet I never move.\nLook upon me and I show you yourself.\nWhat am I?", "pedestal_1"],
		["o2", 4, "tallow_candle", "Tall when I am young,\nshort when I am old.\nWhile I live I give you light,\nand the wind is my enemy.\nWhat am I?", "pedestal_2"],
		["o3", 8, "charcoal", "Black when you find me,\nred when you use me,\npale ash when my work is done.\nWhat am I?", "pedestal_3"],
		["o4", 10, "copper_coin", "I have a head and I have a tail,\nbut no body lies between them.\nI am no serpent.\nWhat am I?", "pedestal_4"],
	]
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, {"all": ["o1", "o2", "o3", "o4"]}),
		_plaque("clue", 6, 4, "Four pedestals guard the northern door.\n\nEach bears a riddle.\n\nSet upon each one the object its words describe.\n\nOne offering has no place here.")]
	for c in riddles:
		ents.append({"kind": "receptacle", "id": c[0], "pos": [c[1], 4], "flag": c[0], "accepts_items": [c[2]], "removable": false,
			"marker": c[4],
			"reject_text": reject, "install_text": install,
			"occupied_text": "The pedestal is already content. Leave what it holds.",
			"text": c[3]})
	ents.append(_item("i1", "mirror_shard", 2, 8))
	ents.append(_item("i2", "tallow_candle", 4, 7))
	ents.append(_item("i3", "charcoal", 8, 7))
	ents.append(_item("i4", "copper_coin", 10, 8))
	ents.append(_item("i5", "glass_bead", 6, 7))
	return _room(1, "The Four Offerings", "M1, M14, M0", rows, [6, 9], ents,
		{"hint": "Read each alcove's riddle and give it the object its words describe. One of the five objects fits nowhere."})


static func _r02() -> Dictionary:
	var rows := _open()
	_fill(rows, 3, 4, 9, 7)  # central block; row 3 is the top corridor of the loop
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1, {"all": ["clock_done", "anti_done"]}, "Past the gate. The stones are quiet now; the loop is walked."), _gate("gate", 6, 2, {"all": ["clock_done", "anti_done"]}),
		_plaque("sign1", 6, 8, "CLOCKWISE.\n\nFour worn stones sit in the corridor's corners. Something below listens to the order you cross them.", {}),
		_plaque("sign2", 6, 3, "TURN BACK.\n\nThe stone below has changed its mind. Go round the other way.", {"requires": "clock_done"}),
		{"kind": "sequence", "id": "clock", "flag": "clock_done", "steps": ["m_nw", "m_ne", "m_se", "m_sw"],
			"done_text": "A deep click under the floor. The far wall grinds a hand's width — and a second inscription comes up through the dust.",
			"step_text": "A soft click underfoot.", "wrong_text": "A flat thud. The stones go dark; the count starts again."},
		{"kind": "sequence", "id": "anti", "flag": "anti_done", "active_when": "clock_done", "steps": ["m_nw", "m_sw", "m_se", "m_ne"],
			"done_text": "The stones agree. Stone slides on stone, and the gate is open.",
			"step_text": "Click. It is counting the other way now.", "wrong_text": "Thud. Wrong way round — it resets."},
		_marker("m_nw", 1, 3, {"symbol": "grey", "seq": ["clock", "anti"], "label": "◇"}),
		_marker("m_ne", 11, 3, {"symbol": "grey", "seq": ["clock", "anti"], "label": "◇"}),
		_marker("m_se", 11, 9, {"symbol": "grey", "seq": ["clock", "anti"], "label": "◇"}),
		_marker("m_sw", 1, 9, {"symbol": "grey", "seq": ["clock", "anti"], "label": "◇"}),
	]
	# Wall off the top-left/top-right corners from the goal alcove is already done by the y=2 wall.
	return _room(2, "Clockwise / Turn Back", "M8, M15, M0", rows, [6, 9], ents,
		{"hint": "Walk the loop clockwise from the top-left stone (NW, NE, SE, SW). Then read the new inscription and walk it the other way."})


static func _r03() -> Dictionary:
	var rows := _open(13, 12)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1), _plaque("clue", 6, 10, "'The serpent never crosses its own body. Follow where it has worn the floor.'")]
	# Winding safe path (faint markers). Everything else in the y3..y8 band throws you back.
	var path := [[6, 9], [5, 9], [4, 9], [3, 9], [2, 9], [1, 9], [1, 8], [1, 7], [2, 7], [3, 7], [4, 7], [5, 7], [6, 7], [7, 7], [8, 7], [9, 7], [10, 7], [11, 7],
		[11, 6], [11, 5], [10, 5], [9, 5], [8, 5], [7, 5], [6, 5], [5, 5], [4, 5], [3, 5], [2, 5], [1, 5], [1, 4], [1, 3], [2, 3], [3, 3], [4, 3], [5, 3], [6, 3]]
	var safe := {}
	for p in path:
		safe["%d_%d" % [p[0], p[1]]] = true
	var n := 0
	for y in range(3, 10):
		for x in range(1, 12):
			var k := "%d_%d" % [x, y]
			if safe.has(k):
				if y < 9 or x < 6:
					ents.append(_marker("s_%s" % k, x, y, {"symbol": "green", "label": "·"}))
			else:
				n += 1
				ents.append(_marker("u_%s" % k, x, y, {"unsafe_when": true, "invisible": true, "unsafe_text": "Light flares under your boot. The room refuses you — and you are back at the door.", "reset_to": [6, 10]}))
	return _room(3, "The Serpent Path", "M7, M0", rows, [6, 10], ents,
		{"hint": "Stay on the faint green trail. It snakes left, right, left. Any shortcut flashes and returns you to the entrance."})


static func _r04() -> Dictionary:
	var rows := _open(13, 13)
	_fill(rows, 1, 6, 11, 6)  # split into upper (y1-5) and lower (y7-11)
	_fill(rows, 1, 6, 1, 6, ".")  # stair down at the left
	_fill(rows, 4, 1, 8, 1)  # bars alcove header
	_fill(rows, 4, 3, 8, 3)
	var ents: Array = [
		_plaque("clue", 6, 5, "Behind the bars: gold on a grille floor. Beside the bars: a lever whose chain runs under the floor. You are not meant to reach it. You are meant to think."),
		_gate("bars_l", 4, 2, false, "wall"), _gate("bars_r", 8, 2, false, "wall"),
		_gate("bars", 5, 2, false), _gate("bars2", 7, 2, false),
		_pit("grille", 6, 2, {"bridge_when": "!floor_open", "revealed_when": true, "fall_text": ""}),
		_item("idol_up", "golden_idol", 6, 2, {"requires": "!floor_open"}),
		_item("idol_down", "golden_idol", 6, 8, {"requires": "floor_open"}),
		_lever("lever", 10, 2, "floor_open", {"once": true, "on_text": "The chain runs taut. Behind the bars the grille floor swings down — and the idol drops out of sight with a crack.", "stuck_text": "The grille is down and stays down."}),
		_plaque("below", 6, 11, "Ceiling grille above. Whatever was up there is down here now, a little the worse for it."),
		_goal(1, 11, "has_golden_idol", "You leave with the idol, chipped but yours."),
	]
	return _room(4, "Drop It Below", "M0, M15", rows, [10, 5], ents,
		{"hint": "The idol is behind bars on a grille. Pull the lever, take the stair on the left down, pick the idol up below, then reach the mark in the corner."})


static func _r05() -> Dictionary:
	var rows := _open(15, 11)
	_fill(rows, 1, 2, 13, 2)
	_fill(rows, 7, 2, 7, 2, ".")
	_fill(rows, 10, 4, 10, 8)  # wall shielding the east lever alcove
	_fill(rows, 10, 8, 10, 8, ".")
	var ents: Array = [_goal(7, 1),
		_gate("gate", 7, 2, {"all": ["west", "east"]}),
		_plaque("clue", 7, 5, "COUNTERSIGNED.\n\nOne hand is never enough for this door."),
		_lever("l_w", 1, 4, "west", {"on_text": "The great door lifts a finger's width — and stops there, waiting for something else."}),
		_lever("l_e", 12, 4, "east", {"on_text": "Both ends of the hall agree. The door lifts the rest of the way."}),
		{"kind": "guardian", "id": "guard", "pos": [10, 8], "enemy_id": "steam_sprite", "defeated_flag": "guard_down", "text": "It stands in the only gap in the wall."},
	]
	return _room(5, "Two Ends of the Hall", "M0, M5", rows, [7, 9], ents,
		{"hint": "Pull the west lever (door goes ajar). Beat the sprite in the gap on the right, pull the east lever, then walk through."})


static func _r06() -> Dictionary:
	var rows := _open(13, 12)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 11, 2, 11, 2, ".")
	var ents: Array = [_goal(11, 1),
		_gate("gate", 11, 2, "gate_open"),
		_plaque("clue", 6, 10, "The lever lifts the gate. The gate does not stay lifted. Count your steps."),
		_lever("lever", 1, 3, "gate_open", {"timed_steps": 13, "on_text": "The gate rattles up. Chains tick somewhere above: it has started counting."}),
	]
	return _room(6, "Timed Gate Run", "M5, M6", rows, [6, 10], ents,
		{"hint": "Pull the lever in the top-left corner, then run to the gate top-right: 13 steps before it drops. If it drops, pull again."})


static func _r07() -> Dictionary:
	var rows := _open(13, 12)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1),
		_plaque("clue", 6, 10, "Footprints cross this floor in one careful line. Where there are none, the dust has not been disturbed — nor has whatever is under it.\n\nA plate by the door shows the floor as it is. Light would show it for good."),
		_plate("reveal", 1, 9, "pits_shown", ["player"], []),
		{"kind": "magic_target", "id": "lamp", "pos": [11, 9], "look": "basin", "solid_when": true, "text": "An unlit lamp niche.",
			"responses": {"4": {"text": "Light floods the niche and stays. Every false tile in the room shows its edges.", "effects": [{"set": "light_on"}]}},
			"wrong_text": "The niche wants light, not that."},
	]
	var safe := {"6_8": 1, "5_8": 1, "4_8": 1, "4_7": 1, "4_6": 1, "5_6": 1, "6_6": 1, "7_6": 1, "8_6": 1, "8_5": 1, "8_4": 1, "7_4": 1, "6_4": 1, "6_3": 1}
	for y in range(3, 9):
		for x in range(2, 11):
			if safe.has("%d_%d" % [x, y]):
				continue
			ents.append(_pit("p_%d_%d" % [x, y], x, y, {"revealed_when": {"any": ["pits_shown", "light_on"]}, "fall_to": [6, 10],
				"fall_text": "The floor was never there. You drop, land in the dust below, and climb back up the entrance stair."}))
	return _room(7, "Revealed Pits", "M5, M15, M9", rows, [6, 10], ents,
		{"spells": [4], "hint": "Stand on the plate (bottom-left) to see the pits, or cast Light on the lamp niche (bottom-right) to reveal them permanently. Then follow the footprint path."})


static func _r08() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, "s3"),
		_plaque("clue", 6, 9, "Nothing here is a lever. Look for where the wall is cleaner than it should be."),
		{"kind": "button", "id": "b1", "pos": [1, 5], "label": "▫", "symbol": "white", "text": "One brick, cleaner than the rest. It gives under your palm. Across the room, a panel of wall slides aside.", "on_press": [{"set": "s1"}]},
		{"kind": "button", "id": "b2", "pos": [11, 5], "label": "▫", "symbol": "white", "requires": "s1", "text": "A second switch, hidden until now. You press it. Behind you, a scrape of stone: another has appeared.", "on_press": [{"set": "s2"}]},
		{"kind": "button", "id": "b3", "pos": [6, 4], "label": "▫", "symbol": "white", "requires": "s2", "text": "The third. The gate ahead rumbles open.", "on_press": [{"set": "s3"}]},
	]
	return _room(8, "Secret Switch Chain", "M0, M15", rows, [6, 9], ents,
		{"hint": "Press the clean brick on the left wall. A switch appears on the right wall; press it. A third appears in the middle; press it and the gate opens."})


static func _r09() -> Dictionary:
	var rows := _open()
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, "wished"),
		_plaque("clue", 6, 8, "'What is given in hope is never lost.'"),
		{"kind": "receptacle", "id": "fountain", "pos": [6, 5], "flag": "wished", "accepts_items": ["copper_coin"], "consume": true, "removable": false,
			"text": "A dry fountain. A basin with a slot worn in the rim by a thousand thumbs.",
			"install_text": "The coin drops, rings once, and is gone. Water begins to move somewhere under the floor — and the gate with it.",
			"reject_text": "It rattles down the slot and comes straight back out of a drain at your feet. The fountain is particular."},
	]
	return _room(9, "The Old Wish", "M1, M14, M0", rows, [6, 9], ents,
		{"items": ["copper_coin", "glass_bead"], "hint": "Examine the fountain and place the copper coin in it. The glass bead is refused."})


static func _r10() -> Dictionary:
	var rows := _open(15, 12)
	_fill(rows, 1, 2, 13, 2)
	_fill(rows, 7, 2, 7, 2, ".")
	# three cells along the left wall, each shut by a gate
	_fill(rows, 1, 4, 3, 9)
	for y in [4, 6, 8]:
		_fill(rows, 2, y, 2, y, ".")  # cell interior
		_fill(rows, 3, y, 3, y, ".")  # cell gate tile
	var ents: Array = [_goal(7, 1), _gate("exit", 7, 2, "exit_plate"),
		_plaque("clue", 7, 10, "Scratches on the inside of every cell door. Breathing behind them. The weight on the plate is the only thing keeping them shut."),
		_plate("hold", 7, 6, "cells_held", ["item", "player"], ["heavy"]),
		_plate("exit_plate_e", 12, 3, "exit_plate", ["item", "player"], ["heavy"]),
		_item("weight", "iron_weight", 7, 6),
		_gate("c1", 3, 4, "!cells_held"), _gate("c2", 3, 6, "!cells_held"), _gate("c3", 3, 8, "!cells_held"),
		{"kind": "guardian", "id": "g1", "pos": [2, 4], "enemy_id": "steam_sprite", "defeated_flag": "g1_down", "requires": "!cells_held"},
		{"kind": "guardian", "id": "g2", "pos": [2, 6], "enemy_id": "moss_shade", "defeated_flag": "g2_down", "requires": "!cells_held"},
		_item("treasure", "silver_key", 2, 8),
		_plaque("exit_note", 12, 5, "A second plate by the exit door. The door wants weight on it — and the only weight in this room is holding the cells."),
	]
	return _room(10, "Release the Cells", "M4, M5, M15", rows, [7, 10], ents,
		{"hint": "Take the iron weight off the central plate — the cells open and two things come out. Drop or throw the weight onto the plate by the exit (top-right) to open the door. The third cell holds a silver key."})


# =====================================================================================
# 11–20
# =====================================================================================

static func _r11() -> Dictionary:
	var rows := _open()
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, "opened"),
		_plaque("wall", 6, 4, "An inscription — or the ghost of one. The ink has faded to nothing you can read with the naked eye."),
		_plaque("wall_read", 4, 4, "Through the lens the faded ink blazes: 'THE THIRD BRICK FROM THE CORNER'.", {"requires": "lens_in"}),
		{"kind": "receptacle", "id": "stand", "pos": [8, 4], "flag": "lens_in", "accepts_items": ["clouded_lens"], "removable": true,
			"text": "A brass reading-stand with an empty ring, angled at the wall.",
			"install_text": "The clouded glass clears the moment it sits in the ring. The wall beside it fills with writing.",
			"reject_text": "The ring wants glass, not that."},
		{"kind": "button", "id": "brick", "pos": [3, 1], "label": "▫", "symbol": "white", "requires": "lens_in", "text": "The third brick. It gives. The gate opens.", "on_press": [{"set": "opened"}]},
	]
	_fill(rows, 3, 2, 3, 2, ".")
	return _room(11, "The Useless Object", "M1, M15", rows, [6, 9], ents,
		{"items": ["clouded_lens", "tuning_fork"], "hint": "The lens seemed pointless. Place it on the reading-stand; the wall's hidden ink names a brick. Press the third brick (top-left) and the gate opens."})


static func _r12() -> Dictionary:
	var rows := _open(7, 13)
	_fill(rows, 1, 2, 5, 2)
	_fill(rows, 3, 2, 3, 2, ".")
	var ents: Array = [_goal(3, 1),
		_plaque("clue", 3, 11, "A mosaic, floor to far wall. Someone got as far as the third row on the blue tiles — and then the tiles changed their minds. Scorch marks say where."),
	]
	# rows y3..y9, x1..5. Safe: blue in rows 7-9, red in rows 3-6. Each row has exactly one or two safe tiles, connected.
	var pattern := {
		9: ["b", "r", "b", "r", "r"], 8: ["r", "b", "b", "r", "b"], 7: ["b", "b", "r", "r", "b"],
		6: ["r", "r", "b", "b", "b"], 5: ["b", "r", "r", "b", "b"], 4: ["r", "r", "b", "r", "b"], 3: ["b", "b", "r", "b", "b"],
	}
	for y in pattern:
		for i in range(5):
			var sym: String = pattern[y][i]
			var safe := (sym == "b") if y >= 7 else (sym == "r")
			var m := _marker("t_%d_%d" % [i + 1, y], i + 1, y, {"symbol": "blue" if sym == "b" else "red", "label": "●" if sym == "b" else "▲"})
			if not safe:
				m["unsafe_when"] = true
				m["unsafe_text"] = "The tile flares white and the floor throws you back to the doorway."
				m["reset_to"] = [3, 11]
			ents.append(m)
	ents[ents.size() - 1 - 5 * 2 - 3]["scorched"] = true  # a pre-scorched wrong tile in row 6 as the demonstration
	return _room(12, "Mosaic Floor", "M0, M5", rows, [3, 11], ents,
		{"hint": "Bottom three rows: step only on blue circles. From the fourth row on (past the scorch), only red triangles are safe."})


static func _r13() -> Dictionary:
	var rows := _open(13, 13)
	_fill(rows, 1, 6, 11, 6)
	_fill(rows, 1, 2, 11, 2)
	var ents: Array = [
		_plaque("clue", 6, 5, "A fine door with a polished handle. Nobody has touched it in years — there is not a footprint in the dust before it. Which is odd, for a door so inviting."),
		_gate("false_door", 6, 2, false, "door"),
		_pit("trap", 6, 3, {"revealed_when": false, "fall_to": [6, 11], "flag_on_fall": "fell",
			"fall_text": "The flagstone in front of the door drops away. So do you. A slide of rubble, a bruise, and a lower corridor nobody meant you to find."}),
		_plaque("below", 6, 8, "A lower passage. Old, dry, and — unlike the door above — actually going somewhere."),
		_goal(11, 8, null, "The lower route ends in daylight. The false door is still up there, unopened, being admired by nobody."),
	]
	return _room(13, "False Door, Real Drop", "M5, M7", rows, [6, 4], ents,
		{"hint": "The door is a lie; the tile in front of it is the trap. Step on it, fall to the lower passage, and walk right to the mark."})


static func _r14() -> Dictionary:
	var rows := _open()
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, "opened"),
		_plaque("corpse", 6, 7, "A body, long dry, one arm stretched toward the levers. Scratched into the floor beside the hand: a crude arrow pointing RIGHT, and the word NOT."),
		_lever("left", 4, 4, "opened", {"once": true, "on_text": "The left one. Chains clank overhead and the gate lifts without complaint."}),
		_lever("right", 8, 4, "burned", {"on_text": "The right one. A vent above coughs fire down the length of the room.", "on_pull": [{"wound": 1, "reset_to": [6, 9], "text": "You are singed, and back at the door, and the lever has reset."}, {"clear": "burned"}]}),
	]
	return _room(14, "Left Lever / Right Lever", "M0", rows, [6, 9], ents,
		{"hint": "Read the corpse's scratch: NOT the right. Pull the left lever. The right one burns you back to the door."})


static func _r15() -> Dictionary:
	var rows := _open(15, 13)
	_fill(rows, 1, 2, 13, 2)
	# three alcoves along the top wall with doors at (3,2), (7,2), (11,2); the well sits at (7,6)
	for x in [3, 7, 11]:
		_fill(rows, x, 2, x, 2, ".")
	var ents: Array = [
		_plaque("well", 7, 6, "An old well, capped. The map's only readable landmark."),
		_plaque("map_note", 7, 10, "Your map fragment reads: '...ARCHIVE — north of the well. ARMOURY — the red door...' Three doors. One key. Pick right."),
		_gate("d_archive", 7, 2, true, "door"),
		_gate("d_store", 3, 2, true, "door"),
		_gate("d_armoury", 11, 2, "has_bronze_key", "door"),
		_plaque("store", 3, 1, "STOREROOM. Broken crates, damp straw, nothing."),
		_item("key", "bronze_key", 7, 1),
		_goal(11, 1, null, "The armoury. Racks of old iron, and a way on."),
	]
	var g: Dictionary = ents[6]
	g["symbol"] = "red"
	g["label"] = "▮"
	return _room(15, "Damaged Map", "M0, M1", rows, [7, 11], ents,
		{"items": ["map_fragment"], "hint": "The archive is the door directly north of the well: take the bronze key from it. The red door (right) is the armoury; it opens for the key."})


static func _r16() -> Dictionary:
	var rows := _open(13, 13)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 3, 6, 6)  # divider between left and right passages
	_fill(rows, 1, 7, 11, 7)  # floor between upper hall and lower cellar
	_fill(rows, 3, 2, 3, 2, ".")
	_fill(rows, 9, 2, 9, 2, ".")
	_fill(rows, 2, 3, 2, 3)  # funnel: the only way to the left gap is over (3,4)
	_fill(rows, 4, 3, 4, 3)
	var ents: Array = [
		{"kind": "npc", "id": "guide", "pos": [4, 5], "label": "G", "lines": ["Left passage, friend. Right's been bricked up for years — everyone knows that.", "(He does not meet your eye. His boots are muddy, and the mud is dry.)"], "lines_after": ["Left. Trust me."]},
		_gate("right_gate", 9, 2, "cellar_lever"),
		_pit("trap", 3, 4, {"revealed_when": false, "fall_to": [3, 10], "flag_on_fall": "fell",
			"fall_text": "The left passage was never bricked up. It was never floored, either. You drop into a cellar."}),
		_plaque("cellar", 6, 10, "A cellar. A lever on the wall, a ladder in the corner — and something the guide would rather you had not found."),
		_lever("cellar_lever", 9, 10, "cellar_lever", {"once": true, "on_text": "Somewhere overhead a gate rattles open. So that is what the right passage was for."}),
		_item("loot", "silver_key", 1, 10),
		_marker("ladder", 11, 10, {"label": "≡", "symbol": "gold", "on_enter": [{"relocate": [10, 5], "text": "Up the ladder. The guide is still there, and suddenly very interested in the ceiling."}]}),
		_goal(9, 1, null, "The right passage. Never bricked up at all."),
	]
	return _room(16, "The Lying Guide", "M12, M0", rows, [2, 5], ents,
		{"hint": "Talk to the guide, then take the left passage he recommends: you fall into a cellar. Pull the lever there (opens the right gate), take the key, climb the ladder (right), and go through the right passage."})


static func _r17() -> Dictionary:
	var rows := _open()
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1, "has_silver_key"), _gate("gate", 6, 2, "cradle_full"),
		_plaque("clue", 6, 8, "A key rests in a cradle of brass. The cradle sits on a spring. The gate ahead is open — for now."),
		{"kind": "receptacle", "id": "cradle", "pos": [6, 5], "flag": "cradle_full", "installed": "silver_key", "accepts_items": ["silver_key", "iron_weight", "sandbag", "golden_idol"], "accepts_tags": ["heavy"], "removable": true,
			"text": "A brass cradle, sprung.", "remove_text": "You lift the key. The cradle rises a finger's width and the gate drops shut with a boom.",
			"install_text": "The cradle sinks under the weight. Chains rattle, and the gate lifts again.", "reject_text": "Too light. The cradle does not notice.",
			"install_effects_by_item": {"golden_idol": [{"text": "You have just traded gold for silver. The gate approves; a merchant would not."}]}},
		_item("weight", "iron_weight", 2, 7),
	]
	return _room(17, "Fair Exchange", "M1, M14", rows, [6, 9], ents,
		{"hint": "Take the key from the cradle — the gate slams. Pick up the iron weight and place it in the cradle: the gate lifts and you keep the key."})


static func _r18() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 10, 2, 10, 2, ".")
	var ents: Array = [_goal(10, 1),
		_plaque("clue", 6, 8, "The wall to the north is solid. You have pressed every stone. And yet the thief in the corner looks like a man with a way out."),
		_gate("secret", 10, 2, "secret_known", "wall"),
		{"kind": "npc", "id": "thief", "pos": [2, 3], "label": "T", "lines": ["Don't come closer! Fine — watch this."],
			"walk": [[3, 3], [4, 3], [5, 3], [6, 3], [7, 3], [8, 3], [9, 3], [10, 3], [10, 2], [10, 1]],
			"on_reach": {"7": [{"set": "secret_known", "text": "He presses the ninth stone and a section of wall folds inward. So that is how."}]},
			"arrive_text": "Gone. The wall stays open behind him.", "on_arrive": [{"relocate_npc": true}]},
	]
	return _room(18, "Watch How They Escape", "M12, M15", rows, [6, 9], ents,
		{"hint": "Talk to the thief. Step back and watch him run along the north wall — he opens a hidden panel top-right. Follow him through it."})


static func _r19() -> Dictionary:
	var rows := _open()
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, "has_bronze_key", "door"),
		_plaque("clue", 6, 8, "An ornate chest on a dais, lit from above. A dented bucket in the corner, in the damp. The dust on the chest lid is unbroken; the bucket's handle is shiny with use."),
		{"kind": "container", "id": "chest", "pos": [6, 4], "ornate": true, "contains": "glass_bead", "text": "The lid groans open. Inside, on velvet: a glass bead. Someone has been laughing at you for a long time.", "on_open": [{"flash": true}]},
		{"kind": "container", "id": "bucket", "pos": [1, 3], "verb": "Look inside", "contains": "bronze_key", "text": "Under an inch of scummy water, a key."},
	]
	return _room(19, "The False Treasure", "M1, M0", rows, [6, 9], ents,
		{"hint": "The ornate chest holds a worthless bead. The key is in the dented bucket in the top-left corner. It opens the door."})


static func _r20() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, "machine_a"),
		{"kind": "board", "id": "board", "pos": [6, 8], "text": "STATUS", "systems": [{"label": "Door engine", "flag": "machine_a"}, {"label": "Bridge winch", "flag": "machine_b"}]},
		{"kind": "receptacle", "id": "engine", "pos": [6, 4], "flag": "machine_a", "accepts_tags": ["gear"], "removable": true, "text": "The door engine. A socket the size of your fist, empty, teeth all round it waiting for a partner.",
			"install_text": "The gear drops in and the engine turns over. The door begins to lift."},
		{"kind": "receptacle", "id": "winch", "pos": [1, 4], "flag": "machine_b", "installed": "brass_gear", "accepts_tags": ["gear"], "removable": true, "text": "A bridge winch, humming, its one brass gear spinning.",
			"remove_text": "You pull the gear. The winch dies and, across the pit, the bridge folds down out of reach."},
		_pit("moat", 2, 6, {"bridge_when": "machine_b", "revealed_when": true, "fall_to": [6, 9]}),
		_item("prize", "silver_key", 1, 6),
	]
	_fill(rows, 1, 5, 1, 5)
	_fill(rows, 1, 7, 2, 7)
	return _room(20, "Missing Gear", "M1, M14, M13", rows, [6, 9], ents,
		{"hint": "The door engine (centre) lacks a gear; the only gear is in the bridge winch (left). Cross the bridge for the key first if you want it, then take the gear and install it in the door engine."})


# =====================================================================================
# 21–30
# =====================================================================================

static func _r21() -> Dictionary:
	var rows := _open()
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, "plate"),
		_plaque("clue", 6, 8, "A plate in the floor; a gate in the wall; a sandbag in the corner. You can guess the joke before you are told it."),
		_plate("plate", 6, 5, "plate", ["player", "item"], ["heavy"]),
		_item("bag", "sandbag", 1, 7),
	]
	return _room(21, "Hold the Plate with an Object", "M2, M4, M5", rows, [6, 9], ents,
		{"hint": "Stand on the plate — the gate opens; step off — it shuts. Take the sandbag, stand on the plate, use Pockets → Drop to leave it there, then walk through."})


static func _r22() -> Dictionary:
	var rows := _open(13, 12)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1, "has_golden_idol", "Out, and the idol with you."), _gate("gate", 6, 2, true),
		_plaque("clue", 6, 10, "The idol sits on a plate. The plate holds the bridge. You are on the wrong side of the bridge for that to be convenient — unless a thing can be in two places while it flies."),
		_plate("p_near", 6, 8, "near", ["item"], ["heavy"]),
		_plate("p_far", 6, 4, "far", ["item"], ["heavy"]),
		_item("idol", "golden_idol", 6, 8),
	]
	for x in range(1, 12):
		ents.append(_pit("pit_%d" % x, x, 6, {"bridge_when": {"any": ["near", "far"]}, "revealed_when": true, "fall_to": [6, 10],
			"fall_text": "The bridge is gone and so, briefly, are you. A scramble back up to the door."}))
	return _room(22, "The Weapon That Closes the Pit", "M1, M3, M5", rows, [6, 10], ents,
		{"hint": "Take the idol: the bridge retracts. Stand at the pit edge facing north and throw the idol (Pockets → Throw). It lands on the far plate, the bridge returns; cross, take the idol back, and leave."})


static func _r23() -> Dictionary:
	var rows := _open()
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1, {"any": ["has_silver_key", "has_bronze_key"]}), _gate("gate", 6, 2, {"any": ["l_full", "r_full"]}),
		_plaque("clue", 6, 8, "TWO KEYS. ONE RESTS.\n\nTwo cradles, balanced against each other. Empty both and the balance is lost."),
		{"kind": "receptacle", "id": "left", "pos": [4, 5], "flag": "l_full", "installed": "silver_key", "accepts_tags": ["key", "heavy"], "removable": true, "text": "The left cradle.", "remove_text": "You take it. The other cradle dips, and holds."},
		{"kind": "receptacle", "id": "right", "pos": [8, 5], "flag": "r_full", "installed": "bronze_key", "accepts_tags": ["key", "heavy"], "removable": true, "text": "The right cradle.", "remove_text": "You take it. The other cradle dips, and holds."},
		{"kind": "guardian", "id": "trap", "pos": [6, 4], "enemy_id": "cinder_golem", "defeated_flag": "trap_down", "requires": {"all": ["!l_full", "!r_full"]}, "text": "Both cradles empty. The floor opens and something comes up through it."},
	]
	return _room(23, "Take One, Leave One", "M1, M14", rows, [6, 9], ents,
		{"items": ["iron_weight"], "hint": "Take either key and leave. Taking both slams the gate and wakes a golem. To claim both safely, place the iron weight in one cradle first."})


static func _r24() -> Dictionary:
	var rows := _open(15, 7)
	_fill(rows, 1, 1, 13, 1)
	_fill(rows, 1, 5, 13, 5)
	var ents: Array = [_goal(13, 3),
		_plaque("clue", 1, 3, "Three rams cross the gallery. The first is slow and obvious. The others are less polite. Watch, then move."),
		{"kind": "hazard", "id": "ram1", "path": [[4, 2], [4, 3], [4, 4]], "mode": "pingpong", "step_seconds": 0.9, "label": "▮", "hit_text": "The ram takes you in the ribs and throws you back down the gallery."},
		{"kind": "hazard", "id": "ram2", "path": [[7, 4], [7, 3], [7, 2]], "mode": "pingpong", "step_seconds": 0.6, "label": "▮", "hit_text": "Clipped. Back you go."},
		{"kind": "hazard", "id": "ram3", "path": [[10, 2], [10, 3], [10, 4]], "mode": "pingpong", "step_seconds": 0.45, "label": "▮", "hit_text": "The fast one. It does not even slow down."},
	]
	return _room(24, "Ram Gallery", "M6, M11", rows, [2, 3], ents,
		{"hint": "Each ram slides up and down its column. Wait until it is at the top or bottom, then cross its column in one step. Three rams, then the mark."})


static func _r25() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 8, 3, 8, 9)   # wall dividing the ledge (right) from the hall (left)
	_fill(rows, 9, 2, 11, 2, "#")
	var ents: Array = [_goal(10, 5),
		_plaque("clue", 2, 8, "A portal, and three pads lettered A, B, C. The portal's colour tells you where it is pointing right now. The ledge past the wall has no door."),
		{"kind": "teleporter", "id": "portal", "pos": [4, 5], "targets": [[2, 3], [6, 8], [10, 8]], "cycle_seconds": 2.0, "text": "Cold, a fold, and elsewhere."},
		_marker("pad_a", 2, 3, {"symbol": "blue", "label": "A"}),
		_marker("pad_b", 6, 8, {"symbol": "purple", "label": "B"}),
		_marker("pad_c", 10, 8, {"symbol": "green", "label": "C"}),
	]
	return _room(25, "Cycling Teleport Field", "M6, M7, M11", rows, [2, 5], ents,
		{"hint": "The portal cycles A (blue) → B (pink) → C (green). Step in while it shows C to land on the sealed ledge on the right; the mark is there."})


static func _r26() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, "rec_lit"),
		_plaque("clue", 6, 8, "An emitter on the west wall throws a line of light. A mirror stands in its path, on a pivot. The receiver over the gate is dark. The receiver in the corner is not something you want lit."),
		{"kind": "emitter", "id": "em", "pos": [1, 5], "dir": [1, 0], "active_when": true, "text": "A crystal emitter, humming."},
		{"kind": "rotator", "id": "mirror", "pos": [6, 5], "states": 2, "mirror": true, "orientation": 1, "labels": ["╲", "╱"], "text": "The mirror turns a notch on its pivot."},
		{"kind": "receiver", "id": "rec", "pos": [6, 3], "flag": "rec_lit", "text": "A dark crystal above the gate."},
		{"kind": "receiver", "id": "bad", "pos": [6, 9], "flag": "bad_lit", "text": "A crystal by the floor. Wired to something that grinds."},
		{"kind": "hazard", "id": "blade", "path": [[4, 6], [5, 6], [6, 6], [7, 6], [8, 6]], "mode": "pingpong", "step_seconds": 0.4, "label": "▮", "active_when": "bad_lit", "hit_text": "The blade you woke up catches you across the shins."},
	]
	return _room(26, "Redirect the Energy", "M10, M9, M13", rows, [6, 9], ents,
		{"hint": "The beam currently bends down into the floor receiver (which starts a blade). Rotate the mirror once so the beam bends up into the receiver over the gate."})


static func _r27() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	_fill(rows, 1, 6, 11, 6)
	_fill(rows, 3, 6, 3, 6, ".")
	var ents: Array = [_goal(6, 1), _gate("drain", 6, 2, "power", "water"),
		{"kind": "board", "id": "board", "pos": [6, 8], "text": "PUMP HOUSE", "systems": [{"label": "Sump pump", "flag": "power"}]},
		_plaque("clue", 6, 4, "The passage north is flooded to the lintel. The pump beside it is dead. A fuse box on the wall holds a fuse burnt black."),
		{"kind": "receptacle", "id": "fusebox", "pos": [9, 4], "flag": "power", "installed": "burnt_fuse", "accepts_items": ["old_fuse"], "removable": true,
			"text": "A fuse box. Behind the little door, a fuse, black through.", "remove_text": "You pull the dead fuse. The socket is bare.",
			"install_text": "The fuse seats with a click. The pump coughs, catches, and the water begins to fall.", "reject_text": "That does not go in a fuse box."},
		{"kind": "container", "id": "crate", "pos": [10, 9], "verb": "Search", "contains": "old_fuse", "text": "Spare parts, mostly useless. One fat copper fuse in a clay sleeve."},
	]
	return _room(27, "Replace the Burnt Fuse", "M1, M14, M13", rows, [6, 9], ents,
		{"hint": "Search the crate (bottom-right) for a fresh fuse. Take the burnt fuse out of the fuse box (upper room, right) and place the fresh one. The pump drains the passage north."})


static func _r28() -> Dictionary:
	var rows := _open(15, 13)
	_fill(rows, 1, 2, 13, 2)
	_fill(rows, 7, 2, 7, 2, ".")
	var ents: Array = [_goal(7, 1), _gate("gate", 7, 2, {"all": ["furnace", "pump", "generator"]}),
		{"kind": "board", "id": "board", "pos": [7, 11], "text": "FACILITY STATUS", "systems": [{"label": "Furnace", "flag": "furnace"}, {"label": "Pump", "flag": "pump"}, {"label": "Generator", "flag": "generator"}]},
		_lever("furnace_lever", 1, 4, "furnace", {"on_text": "The furnace damper opens. Heat, and a lamp on the board.", "off_text": "The damper closes. The board dims."}),
		{"kind": "receptacle", "id": "pump_box", "pos": [13, 4], "flag": "pump", "accepts_items": ["old_fuse"], "removable": true, "text": "The pump's fuse socket. Empty.", "install_text": "The pump thuds into life."},
		{"kind": "container", "id": "locker", "pos": [13, 10], "verb": "Search", "contains": "old_fuse", "text": "A locker. One good fuse."},
		_plaque("gen_note", 7, 4, "GENERATOR START ORDER: GREEN, RED, BLUE."),
		{"kind": "sequence", "id": "gen_seq", "flag": "generator", "steps": ["g_green", "g_red", "g_blue"], "done_text": "The generator winds up to a steady whine. Third lamp.", "step_text": "A relay clicks over.", "wrong_text": "The relays drop out. Start the sequence again."},
		{"kind": "button", "id": "g_green", "pos": [5, 6], "symbol": "green", "label": "●", "seq": "gen_seq"},
		{"kind": "button", "id": "g_red", "pos": [7, 6], "symbol": "red", "label": "●", "seq": "gen_seq"},
		{"kind": "button", "id": "g_blue", "pos": [9, 6], "symbol": "blue", "label": "●", "seq": "gen_seq"},
	]
	return _room(28, "Bring the Whole Facility Online", "M13, M0", rows, [7, 11], ents,
		{"hint": "Three systems: pull the furnace lever (left), fuse the pump (locker bottom-right → socket top-right), start the generator by pressing green, red, blue. The board shows each lamp; the gate needs all three."})


static func _r29() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, "plate"),
		_plaque("clue", 6, 9, "A plate on an island of floor, ringed by a pit you cannot cross. The gate wants the plate pressed. You have a stone, and an arm."),
		_plate("plate", 6, 4, "plate", ["item"], ["heavy"]),
	]
	for x in range(3, 10):
		for y in [3, 5]:
			ents.append(_pit("pit_%d_%d" % [x, y], x, y, {"revealed_when": true, "fall_to": [6, 9]}))
	for y in [4]:
		for x in [3, 4, 5, 7, 8, 9]:
			ents.append(_pit("pit_%d_%d" % [x, y], x, y, {"revealed_when": true, "fall_to": [6, 9]}))
	return _room(29, "Throw to the Remote Switch", "M3, M4", rows, [6, 9], ents,
		{"items": ["grey_stone"], "hint": "Stand at (6,6) facing north and throw the grey stone (Pockets → Throw). It flies over the pit and lands on the plate; the gate opens."})


static func _r30() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	_fill(rows, 8, 3, 8, 9)  # sealed chamber on the right
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, "plate"),
		_plaque("clue", 3, 8, "A sealed chamber to the east, a plate inside it, and a portal in this room that hums at anything thrown but ignores anyone who walks in."),
		{"kind": "teleporter", "id": "portal", "pos": [3, 4], "targets": [[10, 5]], "items_only": true, "hold_when": true},
		_plate("plate", 10, 5, "plate", ["item"], ["heavy"]),
	]
	return _room(30, "Throw Through the Portal", "M3, M7, M4", rows, [6, 9], ents,
		{"items": ["lead_shot"], "hint": "Stand south of the portal facing north and throw the lead shot into it. It emerges on the plate in the sealed chamber and the gate opens."})


# =====================================================================================
# 31–40
# =====================================================================================

static func _r31() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, "plate"),
		_plaque("clue", 6, 8, "A rat the size of a dog, uninterested in you. A plate it will not stand on for love. You have meat."),
		_plate("plate", 6, 4, "plate", ["critter"], []),
		{"kind": "critter", "id": "rat", "pos": [2, 7], "label": "r", "lure_tag": "bait", "text": "It sniffs the air and ignores you."},
	]
	return _room(31, "Enemy on the Plate", "M4, M3", rows, [6, 9], ents,
		{"items": ["raw_meat"], "hint": "Throw or drop the raw meat onto the plate. Each step you take, the rat moves one tile toward the meat; when it stands on the plate the gate opens. Do not fight it — you cannot."})


static func _r32() -> Dictionary:
	var rows := _open(15, 12)
	_fill(rows, 1, 2, 13, 2)
	_fill(rows, 7, 2, 7, 2, ".")
	var ents: Array = [_goal(7, 1), _gate("gate", 7, 2, {"all": ["s1", "s2", "s3"]}),
		_plaque("clue", 7, 10, "Three seals in the floor. Three animals in the room, each with its own appetite. All three seals lit at once — that is the lock."),
		_plate("seal1", 3, 4, "s1", ["critter"], []), _plate("seal2", 7, 4, "s2", ["critter"], []), _plate("seal3", 11, 4, "s3", ["critter"], []),
		{"kind": "critter", "id": "rat", "pos": [2, 8], "label": "r", "lure_tag": "bait", "text": "A rat. Meat."},
		{"kind": "critter", "id": "cat", "pos": [7, 8], "label": "c", "lure_tag": "bait_fish", "text": "A cat. Fish."},
		{"kind": "critter", "id": "dog", "pos": [12, 8], "label": "d", "lure_tag": "bait_bone", "text": "A dog. Bone."},
	]
	return _room(32, "Four Creature Seals", "M4, M13", rows, [7, 10], ents,
		{"items": ["raw_meat", "fish_scrap", "old_bone"], "hint": "Throw the meat onto the left seal, the fish onto the middle, the bone onto the right. Walk about; each animal makes for its own bait. When all three seals are lit the gate opens."})


static func _r33() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, true),
		_plaque("clue", 6, 9, "A ball of fire circles the room on a fixed loop, corner to corner. It crosses the passage north twice a lap. A shutter lever by the door would stop it — if you can reach the lever."),
		{"kind": "hazard", "id": "fireball", "path": [[2, 3], [3, 3], [4, 3], [5, 3], [6, 3], [7, 3], [8, 3], [9, 3], [10, 3], [10, 4], [10, 5], [10, 6], [10, 7], [9, 7], [8, 7], [7, 7], [6, 7], [5, 7], [4, 7], [3, 7], [2, 7], [2, 6], [2, 5], [2, 4]],
			"mode": "loop", "step_seconds": 0.28, "label": "*", "jammed_when": "shutter", "hit_text": "It goes through you like a hot wind. You are back at the door, smelling of singed wool."},
		_lever("shutter", 6, 5, "shutter", {"on_text": "A shutter drops across the fire's channel. The ball stops dead, guttering."}),
	]
	return _room(33, "Fireball Circuit", "M6, M11, M4", rows, [6, 9], ents,
		{"hint": "Watch the fireball loop. Slip past the lower crossing when it is on the far side, pull the shutter lever in the centre to freeze it, then walk to the gate."})


static func _r34() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1),
		_plaque("clue", 6, 9, "'WHAT YOU CAST HERE, YOU RECEIVE.' A sealed door of mirror-bright metal, and beside it a reflector on a pivot, turned to face you."),
		{"kind": "magic_target", "id": "door", "pos": [6, 2], "look": "wall", "solid_when": "!melted", "rebound": true, "rebound_when": "!turned", "rebound_wound": 1, "reset_to": [6, 9],
			"rebound_text": "The reflector throws your own spell straight back. It stings, and you are at the far end of the room again.",
			"responses": {"0": {"when": "turned", "text": "With the reflector turned away, the fire lands. The mirror-metal sags and runs, and the door is a doorway.", "effects": [{"set": "melted"}]},
				"1": {"when": "turned", "text": "Water sheets off the metal harmlessly. It wants heat.", "effects": []}},
			"text": "A door of polished metal."},
		{"kind": "rotator", "id": "reflector", "pos": [8, 3], "states": 2, "orientation": 0, "labels": ["◐", "◑"], "flag_at": {"1": "turned"}, "text": "The reflector swings on its pivot until it faces the wall."},
	]
	return _room(34, "Magic Rebounds Here", "M9, M10", rows, [6, 9], ents,
		{"spells": [0, 1], "hint": "Casting at the door while the reflector faces you bounces the spell back (harmless test). Rotate the reflector, then cast Fire on the door."})


static func _r35() -> Dictionary:
	var rows := _open(13, 12)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1),
		_plaque("clue", 6, 10, "Something about this room is not right. The bridge ahead looks new. The wall beyond it looks old. Light is honest about such things."),
		{"kind": "magic_target", "id": "air", "pos": [1, 8], "look": "basin", "solid_when": true, "text": "A brazier of cold silver. It asks for light, not fire.",
			"responses": {"4": {"text": "Light washes the room. The bridge ahead is not there — it never was — and the wall to the north has a doorway in it.", "effects": [{"set": "lit"}]}},
			"wrong_text": "The silver stays dark."},
		_gate("false_wall", 6, 2, "lit", "wall"),
	]
	for x in range(4, 9):
		ents.append(_pit("false_bridge_%d" % x, x, 5, {"revealed_when": "lit", "fall_to": [6, 10], "fall_text": "The bridge is paint on air. You fall a short way onto old bones and climb back to the door."}))
	_fill(rows, 1, 5, 3, 5)
	_fill(rows, 9, 5, 11, 5)
	return _room(35, "Light Reveals False Geometry", "M9, M15, M5", rows, [6, 10], ents,
		{"spells": [4, 0], "hint": "Cast Light on the silver brazier (bottom-left). The bridge is revealed as a pit and the north wall as a doorway. The pit still needs crossing — the wall left of the bridge is real; go round... no: there is no way round. Wait for Light and step where the bridge was? No — the passage to the north opens at the left end: see hint in-game."})


static func _r36() -> Dictionary:
	var rows := _open(13, 9)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	_fill(rows, 1, 4, 5, 4)
	_fill(rows, 7, 4, 11, 4)
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, true),
		_plaque("clue", 6, 7, "A crusher slams down across the only gap in the wall, fast enough that you cannot time it. Stone braces. That is what Stone is for."),
		{"kind": "hazard", "id": "crusher", "path": [[6, 4], [6, 3]], "mode": "pingpong", "step_seconds": 0.15, "label": "▼", "jammed_when": "braced", "hit_text": "The crusher comes down on you and flings you back."},
		{"kind": "magic_target", "id": "mech", "pos": [4, 5], "look": "magic", "solid_when": true, "text": "The crusher's drive shaft, spinning.",
			"responses": {"3": {"text": "Stone grips the shaft. The crusher stops halfway down and stays there, quivering.", "effects": [{"set": "braced"}]}, "0": {"text": "The shaft glows and keeps turning.", "effects": []}},
			"wrong_text": "That does not stop a machine."},
	]
	return _room(36, "Stone Jams the Machine", "M9, M11", rows, [6, 7], ents,
		{"spells": [3, 0], "hint": "Cast Stone on the drive shaft (left of the gap). The crusher freezes; walk through the gap."})


static func _r37() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, "has_bronze_key", "door"),
		_plaque("clue", 6, 8, "A dry basin with something glinting at the bottom, too deep to reach. Dry clay tablets on the wall, blank."),
		{"kind": "magic_target", "id": "basin", "pos": [6, 5], "look": "basin", "solid_when": true, "text": "A stone basin, bone dry.",
			"responses": {"1": {"text": "Water fills the basin. The glinting thing rises on the flood and bobs at the lip. Beside you, the wet clay darkens into words.", "effects": [{"set": "full"}]}, "0": {"text": "Heat. The basin stays empty.", "effects": []}}},
		_item("key", "bronze_key", 5, 5, {"requires": "full"}),
		_plaque("tablet", 9, 4, "The wet clay reads: 'The door drinks bronze.'", {"requires": "full"}),
	]
	return _room(37, "Water Changes the Room", "M9, M5", rows, [6, 9], ents,
		{"spells": [1, 0], "hint": "Cast Water on the basin. A key floats to the lip (left of the basin): take it. The door opens for it."})


static func _r38() -> Dictionary:
	var rows := _open(13, 12)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	_fill(rows, 1, 6, 11, 6)
	_fill(rows, 6, 6, 6, 6, ".")
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, {"all": ["b1", "b2", "b3"]}),
		_plaque("clue", 6, 10, "Vines choke the passage north. Beyond, three cold braziers. Fire clears; fire also lights."),
		{"kind": "magic_target", "id": "vines", "pos": [6, 6], "look": "vines", "solid_when": "!burned", "text": "Vines, thick as your arm.",
			"responses": {"0": {"text": "The vines go up like paper. The passage is open, and smells of it.", "effects": [{"set": "burned"}]}, "1": {"text": "The vines drink and thicken.", "effects": []}}},
	]
	var i := 1
	for x in [3, 6, 9]:
		ents.append({"kind": "magic_target", "id": "brazier%d" % i, "pos": [x, 4], "look": "basin", "solid_when": true, "text": "A cold brazier.",
			"states": {"lit": "b%d" % i}, "state_colors": {"lit": "gold"},
			"responses": {"0": {"text": "Flame takes. The brazier burns gold.", "effects": [{"set": "b%d" % i}]}, "1": {"text": "Wet coals.", "effects": [{"clear": "b%d" % i}]}}})
		i += 1
	return _room(38, "Fire Creates the Route", "M9, M15, M13", rows, [6, 10], ents,
		{"spells": [0, 1], "hint": "Cast Fire on the vines to clear the passage, then Fire on each of the three braziers. All three lit opens the gate."})


static func _r39() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	_fill(rows, 6, 4, 6, 8)
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, "plate"),
		_plaque("clue", 3, 9, "A plate on the west side, a gate to the north. Standing on one you cannot reach the other. Your companion can stand on things too."),
		_plate("plate", 2, 4, "plate", ["npc", "player"], []),
		{"kind": "npc", "id": "companion", "pos": [4, 9], "label": "C", "lines": ["The plate? Say no more. I'll hold it — you go."], "lines_after": ["Go on, I've got it."],
			"walk": [[3, 9], [3, 8], [3, 7], [3, 6], [3, 5], [2, 5], [2, 4]], "arrive_text": "She plants both feet on the plate. The gate lifts and stays lifted."},
	]
	return _room(39, "Companion Holds the Other Side", "M12, M4, M5", rows, [8, 9], ents,
		{"hint": "Talk to your companion. She walks to the plate on the left and stands on it; the gate opens. Walk round the right side to the gate."})


static func _r40() -> Dictionary:
	var rows := _open(13, 12)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 10, "has_golden_idol", "Out, with the idol, past everything the room threw at you."), 
		_plaque("clue", 6, 9, "Beyond a pit, on a pedestal, an idol. The pedestal hums. Counterweights, somewhere — the bridge is holding its breath."),
		{"kind": "receptacle", "id": "pedestal", "pos": [6, 3], "flag": "idol_home", "installed": "golden_idol", "accepts_tags": ["heavy"], "removable": true, "text": "The pedestal.",
			"remove_text": "The hum stops. Behind you the bridge folds away into the pit, and something on the east wall begins to move."},
		{"kind": "hazard", "id": "blade", "path": [[10, 4], [10, 5], [10, 6], [10, 7], [10, 8]], "mode": "pingpong", "step_seconds": 0.5, "label": "▮", "active_when": "!idol_home", "hit_text": "The blade catches you and hurls you back to the pedestal."},
	]
	for x in [4, 5, 6, 7, 8]:
		ents.append(_pit("pit_%d" % x, x, 6, {"bridge_when": "idol_home", "revealed_when": true, "fall_to": [6, 9]}))
	_fill(rows, 1, 6, 3, 6)
	_fill(rows, 9, 6, 9, 6)
	# start is on the near side; the only return with the idol is the east corridor past the blade
	var h: Dictionary = ents[3]
	h["reset_to"] = [6, 4]
	return _room(40, "The Room Changes When You Take the Prize", "M1, M13, M5, M6", rows, [6, 9], ents,
		{"hint": "Cross the bridge and take the idol from the pedestal: the bridge retracts and a blade starts in the east corridor. Time the blade, come back down the east side, and reach the mark by the door."})


# =====================================================================================
# 41–50
# =====================================================================================

static func _r41() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, "song"),
		_plaque("clue", 6, 8, "Four bells. A brass plate that, when you touch it, hums a little tune: LOW, HIGH, MID, LOW. You can touch it as often as you like."),
		{"kind": "sequence", "id": "song_seq", "flag": "song", "steps": ["bell_low", "bell_high", "bell_mid", "bell_low"], "done_text": "The fourth note. The chord holds, and the gate opens on it.", "step_text": "The note hangs in the air.", "wrong_text": "A sour clang. The bells fall silent; begin again."},
		{"kind": "button", "id": "bell_low", "pos": [3, 5], "symbol": "blue", "label": "1", "verb": "Ring", "seq": "song_seq", "text": "LOW."},
		{"kind": "button", "id": "bell_mid", "pos": [6, 5], "symbol": "green", "label": "2", "verb": "Ring", "seq": "song_seq", "text": "MID."},
		{"kind": "button", "id": "bell_high", "pos": [9, 5], "symbol": "red", "label": "3", "verb": "Ring", "seq": "song_seq", "text": "HIGH."},
	]
	return _room(41, "Sound Sequence", "M0, M8", rows, [6, 9], ents,
		{"hint": "Ring the bells LOW (left), HIGH (right), MID (middle), LOW (left). A wrong note resets the sequence."})


static func _r42() -> Dictionary:
	var rows := _open(15, 11)
	_fill(rows, 1, 2, 13, 2)
	_fill(rows, 11, 2, 11, 2, ".")
	var ents: Array = [_goal(11, 1),
		_plaque("clue", 7, 9, "Three sets of tracks cross the room. Boots, a paw, and one foot that drags. The one you are following was wounded in the leg."),
		_gate("secret", 11, 2, "tracked", "wall"),
		{"kind": "sequence", "id": "track_seq", "flag": "tracked", "steps": ["d1", "d2", "d3", "d4"], "reset_on_wrong": false, "done_text": "The dragged track ends at blank wall — which is not blank. A panel gives, and the tracks go on beyond it.", "step_text": ""},
	]
	var drag := [[7, 8], [8, 7], [9, 6], [10, 5], [11, 4], [11, 3]]
	var i := 1
	for p in drag:
		var m := _marker("d%d" % i if i <= 4 else "dx%d" % i, p[0], p[1], {"symbol": "purple", "label": ">"})
		if i <= 4:
			m["seq"] = "track_seq"
		ents.append(m)
		i += 1
	for p in [[6, 8], [5, 7], [4, 6], [3, 5], [2, 4], [1, 3]]:
		ents.append(_marker("boot_%d_%d" % [p[0], p[1]], p[0], p[1], {"symbol": "grey", "label": "B"}))
	for p in [[8, 8], [8, 6], [7, 5], [6, 4], [5, 3]]:
		ents.append(_marker("paw_%d_%d" % [p[0], p[1]], p[0], p[1], {"symbol": "green", "label": "P"}))
	return _room(42, "Follow the Footprints", "M0, M15", rows, [7, 9], ents,
		{"hint": "Follow the purple dragging-foot track diagonally up and right, stepping on each mark in order, to the wall top-right. The hidden panel opens."})


static func _r43() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	_fill(rows, 1, 5, 11, 5)
	_fill(rows, 3, 5, 3, 5, ".")
	var ents: Array = [_goal(6, 1), _gate("exit", 6, 2, "cw_b"),
		_plaque("clue", 6, 8, "Through the bars: a door, and a chain running to a cradle full of iron. Take the iron, the door lifts — but there is a second cradle on the other side, and a second door."),
		_gate("inner", 3, 5, "!cw_a"),
		{"kind": "receptacle", "id": "cradle_a", "pos": [9, 8], "flag": "cw_a", "installed": "iron_weight", "accepts_tags": ["heavy"], "removable": true, "text": "Cradle A.", "remove_text": "The chain runs. The inner door rises."},
		{"kind": "receptacle", "id": "cradle_b", "pos": [9, 3], "flag": "cw_b", "accepts_tags": ["heavy"], "removable": true, "text": "Cradle B, empty, its chain slack.", "install_text": "The cradle sinks. The exit lifts."},
	]
	return _room(43, "The Counterweight", "M2, M14, M5", rows, [6, 8], ents,
		{"hint": "Take the iron weight from cradle A (bottom-right): the inner door opens. Go through (left) and place the weight in cradle B (top-right): the exit opens."})


static func _r44() -> Dictionary:
	var rows := _open(13, 12)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	_fill(rows, 1, 6, 11, 6)
	_fill(rows, 2, 6, 2, 6, ".")
	_fill(rows, 10, 6, 10, 6, ".")
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, "has_silver_key", "door"),
		_plaque("clue", 6, 10, "A sluice lever. On the left, a low tunnel; on the right, a high walkway. Flooded, the tunnel drowns and the walkway's raft floats. Drained, the reverse."),
		_lever("sluice", 6, 8, "flooded", {"on_text": "Water roars in. The tunnel fills; the raft on the walkway rises to meet the ledge.", "off_text": "The sluice drains. The tunnel empties; the raft sinks out of reach."}),
		_gate("tunnel", 2, 6, "!flooded", "water"),
		_gate("walkway", 10, 6, "flooded", "water"),
		_item("key", "silver_key", 2, 4),
		_plaque("treasure_note", 10, 4, "The walkway ledge. A view, and a chest long since emptied. Progress was the other way."),
	]
	_fill(rows, 5, 4, 7, 5)  # centre block stops at row 4: row 3 is the top corridor both sides share
	return _room(44, "Drain / Flood Route Swap", "M13, M5", rows, [6, 10], ents,
		{"hint": "Drained (default), the left tunnel is open: fetch the silver key there. Flooded (pull the lever) opens the right walkway instead. Either side reaches the top; the door wants the key."})


static func _r45() -> Dictionary:
	var rows := _open(13, 13)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	_fill(rows, 1, 8, 11, 8)
	_fill(rows, 1, 8, 1, 8, ".")
	var ents: Array = [_goal(6, 1),
		_plaque("clue", 6, 11, "A causeway of old tiles over a drop. Each tile cracks as you stand on it and drops a moment later. Keep moving; do not go back."),
	]
	for y in range(3, 8):
		for x in range(2, 11):
			if x == 6 or (y == 5 and x >= 6 and x <= 9):
				ents.append({"kind": "crumble", "id": "c_%d_%d" % [x, y], "pos": [x, y], "steps": 2, "fall_to": [6, 11], "fall_text": "The tile goes. You drop to the undercroft and trudge back to the start."})
			else:
				ents.append(_pit("v_%d_%d" % [x, y], x, y, {"revealed_when": true, "fall_to": [6, 11]}))
	ents.append(_item("bonus", "silver_key", 10, 4, {}))
	for e in ents:
		if str(e.get("id", "")) == "v_10_4":
			ents.erase(e)
			break
	return _room(45, "One-Way Collapsing Floor", "M6, M5, M7", rows, [6, 11], ents,
		{"hint": "Walk straight north along the middle column without stopping. The side spur at row 5 leads to a key — riskier. Falling drops you to the start."})


static func _r46() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 2, 2, 2, 2, ".")
	_fill(rows, 5, 3, 5, 8)
	var ents: Array = [_goal(2, 1),
		_plaque("clue", 3, 9, "A locked door by the entrance. A long dead-end corridor to the east with a lever at the end of it. Pull it and, apparently, nothing."),
		_gate("door", 2, 2, "behind", "door"),
		_lever("far", 11, 3, "behind", {"once": true, "on_text": "You pull. Nothing here changes. But far behind you — a clunk, and the rattle of a chain."}),
	]
	return _room(46, "The Door That Opens Behind You", "M0, M15", rows, [3, 8], ents,
		{"hint": "Walk round the divider to the lever at the far top-right and pull it. Come back: the door by the entrance (top-left) is now open."})


static func _r47() -> Dictionary:
	var rows := _open(15, 12)
	_fill(rows, 1, 2, 13, 2)
	_fill(rows, 7, 2, 7, 2, ".")
	_fill(rows, 1, 6, 13, 6)
	_fill(rows, 3, 6, 3, 6, ".")
	_fill(rows, 11, 6, 11, 6, ".")
	var ents: Array = [_goal(7, 1),
		_plaque("clue", 7, 10, "A stone face with three mouths. 'I HAVE CITIES BUT NO HOUSES, FORESTS BUT NO TREES, WATER BUT NO FISH.' Two passages north: a short one on the left, a long one on the right."),
		{"kind": "choice", "id": "face", "pos": [7, 8], "text": "The stone face waits.", "options": [
			{"label": "A map", "text": "The face smiles, if stone can. The short passage on the left grinds open.", "effects": [{"set": "answered_right"}]},
			{"label": "A dream", "text": "The face frowns. Water pours from its mouth and floods the short passage to the ceiling.", "effects": [{"set": "flooded"}]},
			{"label": "A king", "text": "The face laughs. Behind you, a grille opens, and something comes out of it.", "effects": [{"set": "guardian_out"}]},
		]},
		_gate("short", 3, 6, {"all": ["answered_right", "!flooded"]}, "water"),
		_gate("long", 11, 6, true),
		{"kind": "guardian", "id": "guard", "pos": [11, 4], "enemy_id": "steam_brute", "defeated_flag": "guard_down", "requires": "guardian_out"},
	]
	return _room(47, "Wrong Answer Changes the Dungeon", "M0, M13", rows, [7, 10], ents,
		{"hint": "Answer 'A map' and the short left passage opens. Wrong answers do not end the room: 'A dream' floods the shortcut, 'A king' releases a brute into the long right passage — which stays open either way."})


static func _r48() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1), _gate("gate", 6, 2, "shift_end"),
		_plaque("clue", 6, 8, "Three levers, numbered. No clue on the walls. The clue is in your pocket — read it."),
		{"kind": "sequence", "id": "shift", "flag": "shift_end", "steps": ["lv3", "lv1", "lv2"], "done_text": "Third, first, second. The foreman would be proud. The gate opens.", "step_text": "A relay holds.", "wrong_text": "Everything drops out with a bang. Start over."},
		{"kind": "button", "id": "lv1", "pos": [3, 5], "symbol": "grey", "label": "1", "verb": "Pull", "seq": "shift"},
		{"kind": "button", "id": "lv2", "pos": [6, 5], "symbol": "grey", "label": "2", "verb": "Pull", "seq": "shift"},
		{"kind": "button", "id": "lv3", "pos": [9, 5], "symbol": "grey", "label": "3", "verb": "Pull", "seq": "shift"},
	]
	return _room(48, "Object as Clue, Not Key", "M1", rows, [6, 9], ents,
		{"items": ["ledger_page"], "hint": "Inspect the ledger page in Pockets: THIRD, FIRST, SECOND. Pull the levers in that order."})


static func _r49() -> Dictionary:
	var rows := _open(13, 11)
	_fill(rows, 1, 2, 11, 2)
	_fill(rows, 6, 2, 6, 2, ".")
	var ents: Array = [_goal(6, 1),
		_plaque("clue", 6, 8, "Roots seal the passage north, thick and dry as rope. Water only makes them grow. You have no fire — yet. Something in the old satchel in the corner smells of ash."),
		{"kind": "magic_target", "id": "roots", "pos": [6, 4], "look": "vines", "solid_when": "!burned", "text": "Dry roots.",
			"responses": {"0": {"text": "The roots catch instantly and are gone in a rush of sparks.", "effects": [{"set": "burned"}]}, "1": {"text": "The roots drink, and thicken, and you learn something about roots.", "effects": []}},
			"wrong_text": "The roots are unmoved."},
		{"kind": "container", "id": "satchel", "pos": [1, 3], "verb": "Open", "teaches_spell": 0, "text": "A scorched page and a taste of cinders. You know Fire now."},
	]
	return _room(49, "Return Later with New Magic", "M9, M15, M5", rows, [6, 9], ents,
		{"spells": [1], "hint": "Try Water on the roots — nothing. Open the satchel (top-left) to learn Fire, then return and cast Fire on the roots."})


static func _r50() -> Dictionary:
	var rows := _open(15, 13)
	_fill(rows, 1, 2, 13, 2)
	_fill(rows, 7, 2, 7, 2, ".")
	_fill(rows, 3, 2, 3, 2, ".")
	var ents: Array = [_goal(7, 1),
		_plaque("clue", 7, 11, "A barred gate. A keyhole beside it. A drive-wheel that could be braced. A wall to the left that does not feel like a wall. And across a pit, a plate nobody is standing on. Any of these will do."),
		_gate("gate", 7, 2, {"any": ["key_used", "braced", "plate"]}),
		_gate("light_way", 3, 2, "lit", "wall"),
		{"kind": "receptacle", "id": "lock", "pos": [9, 3], "flag": "key_used", "accepts_tags": ["key"], "removable": true, "text": "A keyhole in a brass plate.", "install_text": "The key turns. The bars lift."},
		{"kind": "magic_target", "id": "wheel", "pos": [5, 3], "look": "magic", "solid_when": true, "text": "The gate's drive-wheel, turning slowly.",
			"responses": {"3": {"text": "Stone seizes the wheel with the bars halfway up. Good enough.", "effects": [{"set": "braced"}]}, "4": {"text": "Light shows the wheel is just a wheel.", "effects": []}}},
		{"kind": "magic_target", "id": "wall_l", "pos": [2, 3], "look": "wall", "solid_when": true, "text": "A patch of wall that does not echo.",
			"responses": {"4": {"text": "Light passes straight through the wall. There is a passage there.", "effects": [{"set": "lit"}]}, "3": {"text": "Stone on stone. Nothing.", "effects": []}}},
		_plate("plate", 12, 4, "plate", ["item"], ["heavy"]),
		{"kind": "container", "id": "box", "pos": [1, 10], "verb": "Search", "contains": "bronze_key", "text": "A key, under old sacking."},
	]
	for y in [5, 6, 7]:
		for x in [11, 12, 13]:
			ents.append(_pit("pit_%d_%d" % [x, y], x, y, {"revealed_when": true, "fall_to": [7, 11]}))
	return _room(50, "Multi-Solution Room", "M1, M9, M3, M4, M15", rows, [7, 11], ents,
		{"items": ["grey_stone"], "spells": [3, 4], "hint": "Any of: search the box (bottom-left) for a key and use the keyhole; cast Stone on the drive-wheel; throw the grey stone north over the pit onto the plate; or cast Light on the odd wall (left) for a hidden passage to a second exit."})
